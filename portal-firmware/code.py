"""
Resistor Station - Portal M4 Main Entry Point

Controls the 64x32 HUB75 LED matrix, NeoPixel strip, and DAC LED bulb.
Receives measurement packets from the Pi over USB CDC serial.

States
------
  IDLE   -- no packet received in the last 3 s (or never received one)
  ACTIVE -- packets are arriving; run full animations

Packet format (from Pi):
  R:<ohms>,<b1>,<b2>,<b3>,<b4>\\n
  e.g. R:4700.0,yellow,violet,red,gold\\n

V_IN is always 3.3 V (Pi uses a 3.3 V voltage divider).
"""

import time
import digitalio
import board
import pins
from serial_receiver import SerialReceiver
from current_animation import CurrentAnimation
from strip_animation import StripAnimation
from bulb_control import BulbControl

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

V_IN             = 3.3      # volts — fixed supply on this station
_IDLE_TIMEOUT    = 3.0      # seconds without a packet before going IDLE
_BTN_DEBOUNCE    = 0.2      # seconds — ignore button presses within this window
_STATE_IDLE      = 0
_STATE_ACTIVE    = 1

# ---------------------------------------------------------------------------
# Startup banner
# ---------------------------------------------------------------------------

print("=" * 40)
print("  Resistor Station — Portal M4 Firmware")
print("  V_IN = %.1f V" % V_IN)
print("  64x32 HUB75 matrix + NeoPixel strip + DAC bulb")
print("  Waiting for Pi serial packets...")
print("=" * 40)

# ---------------------------------------------------------------------------
# Hardware initialisation
# ---------------------------------------------------------------------------

# Serial receiver — reads R:<ohms>,<b1>,<b2>,<b3>,<b4>\n from Pi
receiver = SerialReceiver()

# Matrix animation (also imports matrix_display at module level, so we do NOT
# import matrix_display here — it is already initialised by current_animation)
anim = CurrentAnimation()

# NeoPixel strip animation
strip = StripAnimation(num_pixels=30)

# DAC-controlled LED bulb
bulb = BulbControl()

# Buttons — active-low with internal pull-up
_btn_up   = digitalio.DigitalInOut(pins.BUTTON_UP)
_btn_up.direction   = digitalio.Direction.INPUT
_btn_up.pull        = digitalio.Pull.UP

_btn_down = digitalio.DigitalInOut(pins.BUTTON_DOWN)
_btn_down.direction = digitalio.Direction.INPUT
_btn_down.pull      = digitalio.Pull.UP

# ---------------------------------------------------------------------------
# Runtime state — all pre-allocated as plain scalars (no dicts/objects here)
# ---------------------------------------------------------------------------

_state          = _STATE_IDLE
_last_packet_t  = 0.0   # time.monotonic() of the last valid packet
_btn_up_last    = 0.0   # last accepted up-button press time
_btn_down_last  = 0.0   # last accepted down-button press time
_strip_is_off   = True  # tracks whether strip.off() has already been called
                        # so we avoid calling it every idle frame

# ---------------------------------------------------------------------------
# Button handling helpers (non-blocking, debounced)
# ---------------------------------------------------------------------------

def _check_button_up(now):
    """Check the UP button; return True once per debounced press."""
    global _btn_up_last
    if not _btn_up.value:                           # active low: pressed
        if now - _btn_up_last >= _BTN_DEBOUNCE:
            _btn_up_last = now
            return True
    return False


def _check_button_down(now):
    """Check the DOWN button; return True once per debounced press."""
    global _btn_down_last
    if not _btn_down.value:                         # active low: pressed
        if now - _btn_down_last >= _BTN_DEBOUNCE:
            _btn_down_last = now
            return True
    return False

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

print("Main loop started.")

while True:
    now = time.monotonic()

    # -- Button polling (non-blocking, debounced) --
    if _check_button_up(now):
        print("Button UP pressed (state=%d)" % _state)
        # Reserved for future mode switching

    if _check_button_down(now):
        print("Button DOWN pressed (state=%d)" % _state)
        # Reserved for future mode switching

    # -- Serial packet polling --
    packet = receiver.read_packet()

    if packet is not None:
        # New measurement from Pi — extract resistance and derive current
        resistance = packet["resistance"]

        # Guard against zero/negative resistance from a bad read
        if resistance < 0.1:
            resistance = 0.1

        current = V_IN / resistance

        # Push values to all output subsystems
        anim.set_params(V_IN, resistance)
        bulb.set_current(current)
        strip.set_current(current)

        _last_packet_t = now

        if _state != _STATE_ACTIVE:
            _state = _STATE_ACTIVE
            _strip_is_off = False
            print("-> ACTIVE  R=%.1f Ohm  I=%.4f A" % (resistance, current))

    # -- State machine --
    if _state == _STATE_ACTIVE:
        # Check whether the Pi has gone silent
        if now - _last_packet_t > _IDLE_TIMEOUT:
            # Transition to IDLE
            _state = _STATE_IDLE
            anim.stop()
            bulb.off()
            strip.off()
            _strip_is_off = True
            print("-> IDLE (no packet for %.1f s)" % _IDLE_TIMEOUT)
        else:
            # Run live animations
            anim.update()
            strip.update()

    else:
        # IDLE state
        anim.idle_animation()

        # Only call strip.off() on the first idle frame, not every iteration
        if not _strip_is_off:
            strip.off()
            _strip_is_off = True
