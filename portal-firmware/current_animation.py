"""
Portal M4 - Electron Flow Animation on LED Matrix

Renders a flowing electron animation: electrons travel left-to-right along a
horizontal wire, slow down and heat up inside a resistor body, then emit heat
particles.  A 'flow indicator' chevron pattern pulses along the wire edges.

All animation state is pre-allocated in __init__; update() is non-blocking.

Public API
----------
    anim = CurrentAnimation()
    anim.set_params(voltage, resistance)   # set V and R directly
    anim.set_current(amps)                 # backward-compat: derives R = V_IN/I
    anim.update()                          # call every main-loop iteration
    anim.idle_animation()                  # call when no resistor connected
    anim.stop()                            # black out display, halt

Palette layout (defined in matrix_display.py, bit_depth=3, 50 entries)
-----------------------------------------------------------------------
  0        : black
  1-10     : electron blue, dim → bright
  11-20    : heated electron orange/red, dim → bright
  21       : resistor body base
  22       : resistor body warmer
  23       : resistor edge
  24       : resistor cap
  25       : lead/terminal
  26-30    : resistor heat glow (increasing warmth)
  31-35    : heat particles (bright → dim)
  36       : wire base (dark blue-grey)
  37       : polarity marker
  38       : trail dim blue
  39       : trail dim orange
  40       : flow indicator (very dim blue)
  41-45    : blended electron colors (blue → orange)
  46-49    : spare black
"""

import math
import time
import random
import matrix_display

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

WIDTH  = 64
HEIGHT = 32

# Resistor geometry
RES_X1 = 20   # resistor body left  (inclusive)
RES_X2 = 43   # resistor body right (inclusive)
RES_Y1 = 4    # resistor body top    (4px margin from edge)
RES_Y2 = 27   # resistor body bottom (4px margin from edge)
WIRE_Y1 = 13  # wire top row
WIRE_Y2 = 18  # wire bottom row

# Reduced counts for SAMD51 memory budget
NUM_ELECTRONS     = 20
MAX_HEAT_PARTICLES = 12
TRAIL_LENGTH       = 2

# V_IN used when set_current() (not set_params()) is the caller
_V_IN = 3.3

# ---------------------------------------------------------------------------
# Pre-computed sine table (629 entries)
# Stored as bytearray with values offset +100 to stay unsigned (0..200).
# Reading: fast_sin(phase) = sin_table[phase % 629] - 100
# ---------------------------------------------------------------------------

_SIN_SIZE = 629   # covers 0..2*pi * 100 in steps of 0.01 rad

sin_table = bytearray(_SIN_SIZE)
for _i in range(_SIN_SIZE):
    sin_table[_i] = int(math.sin(_i / 100.0) * 100.0) + 100
# _i left in module namespace but that's one small int — acceptable


def _fast_sin(phase_100):
    """Return sin * 100 for a phase value that is already * 100."""
    return sin_table[phase_100 % _SIN_SIZE] - 100


# ---------------------------------------------------------------------------
# Inline pixel helpers (module-level so they're accessible as local names
# inside methods via assignment — avoids attribute lookup in hot paths)
# ---------------------------------------------------------------------------

_bmp = matrix_display.bitmap     # direct reference; no dict lookup per pixel
_dsp = matrix_display.display    # for refresh()


def _sp(x, y, c):
    """Set pixel with bounds check."""
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        _bmp[x, y] = c


def _spb(x, y, c):
    """Set pixel only if new color index is higher (brighter) than current."""
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        if c > _bmp[x, y]:
            _bmp[x, y] = c


# ---------------------------------------------------------------------------
# CurrentAnimation
# ---------------------------------------------------------------------------

class CurrentAnimation:
    """Full-frame electron flow animation driven by voltage and resistance."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self):
        """Pre-allocate all animation state; no hardware re-init."""

        # Electrical state
        self._voltage    = 3.3
        self._resistance = 330.0
        self._active     = False

        # Electron arrays — positions in units of (pixel * 100)
        # Spread electrons evenly across the wire at startup
        spacing = (WIDTH * 100) // NUM_ELECTRONS
        self._ex      = [0] * NUM_ELECTRONS
        self._ey      = [0] * NUM_ELECTRONS
        self._ebase_y = [0] * NUM_ELECTRONS
        self._ephase  = [0] * NUM_ELECTRONS
        self._eheat   = [0] * NUM_ELECTRONS

        for _i in range(NUM_ELECTRONS):
            self._ex[_i]      = _i * spacing
            _base             = WIRE_Y1 * 100 + random.randint(0, (WIRE_Y2 - WIRE_Y1 + 1) * 100)
            self._ey[_i]      = _base
            self._ebase_y[_i] = _base
            self._ephase[_i]  = random.randint(0, 628)
            self._eheat[_i]   = 0

        # Heat particle arrays
        self._hpx    = [0] * MAX_HEAT_PARTICLES
        self._hpy    = [0] * MAX_HEAT_PARTICLES
        self._hpvx   = [0] * MAX_HEAT_PARTICLES
        self._hpvy   = [0] * MAX_HEAT_PARTICLES
        self._hplife = [0] * MAX_HEAT_PARTICLES   # 0 = dead, 1-100 = alive

        # Timing
        self._tick              = 0
        self._heat_spawn_ctr    = 0

        # Idle state
        self._idle_x    = 0    # pixel x for the single idle dot
        self._idle_last = 0.0  # time.monotonic() of last idle step

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_params(self, voltage, resistance):
        """Set voltage (V) and resistance (Ω) directly; clamps to safe ranges."""
        if voltage < 0.0:
            voltage = 0.0
        elif voltage > 15.0:
            voltage = 15.0
        if resistance < 0.1:
            resistance = 0.1

        self._voltage    = voltage
        self._resistance = resistance
        self._active     = (voltage > 0.0)

    def set_current(self, amps):
        """Backward-compatible: derive resistance from V_IN / amps, update params."""
        if amps < 0.0:
            amps = 0.0
        if amps < 0.00001:
            # Treat as zero — no current
            self._voltage    = _V_IN
            self._resistance = 330000.0   # very large R → near-zero I
            self._active     = False
            return

        # Clamp to avoid divide-by-zero and unrealistic values
        if amps > 0.5:
            amps = 0.5

        self._voltage    = _V_IN
        self._resistance = _V_IN / amps   # derived R
        self._active     = True

    def update(self):
        """Render one complete frame: clear, static, electrons, heat, refresh.

        Must be called from the main loop; never blocks.
        """
        if not self._active:
            return

        current = self._voltage / self._resistance
        heat_intensity = min(1.0, current * 0.35)   # 0.0..1.0

        self._tick += 1
        tick = self._tick

        # -- Clear --
        _bmp.fill(0)

        # -- Static elements --
        self._draw_static(tick, current, heat_intensity)

        # -- Electrons --
        self._update_electrons(current)

        # -- Heat particles --
        self._update_heat_particles(current, heat_intensity)

        # -- Flow indicators --
        self._draw_flow_indicators(tick, current)

        # -- Refresh --
        _dsp.refresh(minimum_frames_per_second=0)

    def idle_animation(self):
        """Single dim dot drifts along the wire; call once per main-loop tick."""
        now = time.monotonic()
        if now - self._idle_last < 0.08:
            return
        self._idle_last = now

        # Erase previous dot
        py = (WIRE_Y1 + WIRE_Y2) // 2
        _sp(self._idle_x, py, 0)

        self._idle_x = (self._idle_x + 1) % WIDTH
        # Skip over resistor body
        if RES_X1 <= self._idle_x <= RES_X2:
            self._idle_x = RES_X2 + 1

        _sp(self._idle_x, py, 36)   # wire base colour — subtle glow
        _dsp.refresh(minimum_frames_per_second=0)

    def stop(self):
        """Black out display and halt animation."""
        _bmp.fill(0)
        _dsp.refresh(minimum_frames_per_second=0)
        self._active = False

    # ------------------------------------------------------------------
    # Internal frame sections
    # ------------------------------------------------------------------

    def _draw_static(self, tick, current, heat_intensity):
        """Draw wires, resistor body, leads, and polarity markers."""

        # Wires (skip resistor body x range)
        for x in range(WIDTH):
            if x < RES_X1 or x > RES_X2:
                for y in range(WIRE_Y1, WIRE_Y2 + 1):
                    _bmp[x, y] = 36

        # Resistor body
        for x in range(RES_X1, RES_X2 + 1):
            for y in range(RES_Y1, RES_Y2 + 1):
                edge = (x == RES_X1 or x == RES_X2 or y == RES_Y1 or y == RES_Y2)
                if edge:
                    _bmp[x, y] = 23
                else:
                    if heat_intensity > 0.1:
                        # Flicker: deterministic per pixel per tick — no allocation
                        flicker_up = ((tick + x * 3 + y * 7) % 11) > 5
                        # heat scaled 0..100
                        h100 = int(heat_intensity * 100)
                        if flicker_up:
                            h100 = min(100, h100 + 15)
                        else:
                            h100 = max(0, h100 - 15)
                        # Map to palette 21..30
                        if h100 < 20:
                            idx = 21
                        elif h100 < 40:
                            idx = 22
                        elif h100 < 60:
                            idx = 26
                        elif h100 < 75:
                            idx = 27
                        elif h100 < 88:
                            idx = 28
                        else:
                            idx = 29
                        _bmp[x, y] = idx
                    else:
                        _bmp[x, y] = 21

        # Rounded caps on sides of body
        for y in range(RES_Y1 + 1, RES_Y2):
            _sp(RES_X1 - 1, y, 24)
            _sp(RES_X2 + 1, y, 24)

        # Leads (two pixels each side)
        for y in range(WIRE_Y1, WIRE_Y2 + 1):
            _sp(RES_X1 - 1, y, 25)
            _sp(RES_X1 - 2, y, 25)
            _sp(RES_X2 + 1, y, 25)
            _sp(RES_X2 + 2, y, 25)

        # Polarity: + on left
        _sp(1, 15, 37)
        _sp(2, 15, 37)
        _sp(3, 15, 37)
        _sp(2, 14, 37)
        _sp(2, 16, 37)
        # - on right
        _sp(60, 15, 37)
        _sp(61, 15, 37)
        _sp(62, 15, 37)

    def _reset_electron(self, i, spread):
        """Place electron i at start (or random position if spread=True)."""
        if spread:
            self._ex[i] = random.randint(-1000, (WIDTH + 10) * 100)
        else:
            self._ex[i] = random.randint(-2400, 0)
        base = WIRE_Y1 * 100 + random.randint(0, (WIRE_Y2 - WIRE_Y1 + 1) * 100)
        self._ey[i]      = base
        self._ebase_y[i] = base
        self._ephase[i]  = random.randint(0, 628)
        self._eheat[i]   = 0

    def _update_electrons(self, current):
        """Advance all electrons one step and draw them."""
        ex      = self._ex
        ey      = self._ey
        ebase_y = self._ebase_y
        ephase  = self._ephase
        eheat   = self._eheat

        for i in range(NUM_ELECTRONS):
            px = ex[i] // 100
            in_res = RES_X1 <= px <= RES_X2

            # Speed (scaled * 100)
            if in_res:
                speed = int((2.5 + current * 1.2) * 100)
                h = eheat[i] + 8
                eheat[i] = h if h < 100 else 100
            else:
                speed = int((6.0 + current * 4.0) * 100)
                h = eheat[i] - 6
                eheat[i] = h if h > 0 else 0

            # Move and update phase
            ex[i] += speed // 3
            ephase[i] = (ephase[i] + 16) % _SIN_SIZE

            # Y wobble
            if in_res:
                center_y = ((WIRE_Y1 + WIRE_Y2) * 100) // 2
                wobble   = (_fast_sin(ephase[i]) * 350) // 100
                new_y    = center_y + wobble
                lo = (RES_Y1 + 1) * 100
                hi = (RES_Y2 - 1) * 100
                ey[i] = new_y if lo <= new_y <= hi else (lo if new_y < lo else hi)
            else:
                ey[i] = ebase_y[i] + ((_fast_sin(ephase[i]) * 70) // 100)

            # Reset if off right edge
            if ex[i] > (WIDTH + 8) * 100:
                self._reset_electron(i, False)

            # Draw position
            draw_x = ex[i] // 100
            draw_y = ey[i] // 100

            # Blended color 41-45 by heat band
            heat_t = eheat[i]
            if heat_t < 20:
                color = 41
            elif heat_t < 40:
                color = 42
            elif heat_t < 60:
                color = 43
            elif heat_t < 80:
                color = 44
            else:
                color = 45
            _spb(draw_x, draw_y, color)

            # Bright core
            if heat_t > 50:
                bright_idx = 11 + min(9, heat_t // 12)
            else:
                bright_idx = 1 + min(9, 5 + heat_t // 20)
            _spb(draw_x, draw_y, bright_idx)

            # Trail
            trail_c = 38 if heat_t < 50 else 39
            for t in range(1, TRAIL_LENGTH + 1):
                _spb(draw_x - t, draw_y, trail_c)

    def _spawn_heat_particle(self):
        """Find a dead heat particle slot and spawn above/below the resistor."""
        hplife = self._hplife
        for i in range(MAX_HEAT_PARTICLES):
            if hplife[i] == 0:
                self._hpx[i]  = (RES_X1 + 2 + random.randint(0, RES_X2 - RES_X1 - 4)) * 100
                if random.randint(0, 1) == 0:
                    self._hpy[i]  = (RES_Y1 - 1) * 100
                    self._hpvy[i] = random.randint(-300, -120)
                else:
                    self._hpy[i]  = (RES_Y2 + 1) * 100
                    self._hpvy[i] = random.randint(120, 300)
                self._hpvx[i] = random.randint(-150, 150)
                hplife[i]     = 100
                return

    def _update_heat_particles(self, current, heat_intensity):
        """Advance heat particles and draw them; spawn new ones as needed."""
        hpx    = self._hpx
        hpy    = self._hpy
        hpvx   = self._hpvx
        hpvy   = self._hpvy
        hplife = self._hplife

        # Spawn logic
        self._heat_spawn_ctr += 1
        if heat_intensity > 0.15:
            spawn_rate = max(2, int(8 / max(0.3, current * 0.25)))
            if self._heat_spawn_ctr >= spawn_rate:
                self._heat_spawn_ctr = 0
                self._spawn_heat_particle()

        # Update and draw
        for i in range(MAX_HEAT_PARTICLES):
            if hplife[i] == 0:
                continue
            hpx[i]    += hpvx[i] // 3
            hpy[i]    += hpvy[i] // 3
            life       = hplife[i] - 3
            if life <= 0:
                hplife[i] = 0
                continue
            hplife[i] = life

            px = hpx[i] // 100
            py = hpy[i] // 100

            if life > 80:
                cidx = 31
            elif life > 60:
                cidx = 32
            elif life > 40:
                cidx = 33
            elif life > 20:
                cidx = 34
            else:
                cidx = 35
            _spb(px, py, cidx)

    def _draw_flow_indicators(self, tick, current):
        """Draw periodic dim chevron dots above and below the wire."""
        flow_phase = (tick * int(2 + current * 2)) % 10
        for x in range(WIDTH):
            if RES_X1 - 2 <= x <= RES_X2 + 2:
                continue
            if (x + flow_phase) % 10 < 1:
                _spb(x, WIRE_Y1 - 1, 40)
                _spb(x, WIRE_Y2 + 1, 40)
