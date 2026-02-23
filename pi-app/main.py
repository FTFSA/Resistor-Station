"""
Resistor Station - Raspberry Pi 4 Main Entry Point

Initialises hardware (ADS1115, serial to Portal M4), builds the Pygame UI,
and runs the main event loop.

Hardware failures (ADS1115 not found, Portal not connected) are caught and
logged; the app continues in a degraded state so the UI is still usable.

Measurement flow
----------------
  Every MEASURE_INTERVAL seconds:
    1. meter.measure() → result dict
    2. color_code.resistance_to_bands() → 4-band list
    3. serial.send_measurement() → Portal M4
    4. live_lab.update(dt, measurement=result, bands=bands) → screen

  ScreenLiveLab is constructed with the UIManager object so it operates in
  "app mode" (it does not poll hardware itself).  OhmTriangle and Calculator
  receive the plain pygame surface and are stateless w.r.t. measurements.
"""

import logging
import sys
import time

import color_code
import config
from measurement import ResistanceMeter
from serial_comms import PortalSerial
from ui_manager import UIManager
from screen_live_lab import ScreenLiveLab
from screen_ohm_triangle import ScreenOhmTriangle
from screen_calculator import ScreenCalculator

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# How often to take a resistance measurement (seconds).
# 32-sample trimmed-mean read takes ~50 ms; 200 ms gives comfortable headroom.
MEASURE_INTERVAL = 0.2


def main() -> None:
    # ------------------------------------------------------------------
    # Hardware initialisation (graceful degradation on failure)
    # ------------------------------------------------------------------

    meter = None
    try:
        meter = ResistanceMeter(
            i2c_address=config.I2C_ADDRESS_ADS,
            r_known=config.R_KNOWN,
            v_in=config.V_IN,
        )
        log.info("ADS1115 initialised at I2C address 0x%02X", config.I2C_ADDRESS_ADS)
    except Exception as exc:
        log.warning("ADS1115 not available (%s) — running without live measurement", exc)

    serial = PortalSerial(port=config.SERIAL_PORT, baud=config.SERIAL_BAUD)
    if serial.is_connected():
        log.info("Portal M4 connected on %s", config.SERIAL_PORT)
    else:
        log.warning("Portal M4 not found on %s — will retry automatically", config.SERIAL_PORT)

    # ------------------------------------------------------------------
    # Pygame + UIManager (creates 480x320 fullscreen display)
    # ------------------------------------------------------------------

    mgr = UIManager()

    # ------------------------------------------------------------------
    # Screens
    #
    # ScreenLiveLab receives the UIManager so it operates in "app mode":
    # it extracts mgr._surface internally and expects measurement data to
    # be injected via update(dt, measurement=..., bands=...) each frame.
    #
    # OhmTriangle and Calculator are purely interactive; they only need
    # the pygame surface.
    # ------------------------------------------------------------------

    live_lab   = ScreenLiveLab(mgr)
    triangle   = ScreenOhmTriangle(mgr.screen)
    calculator = ScreenCalculator(mgr.screen)

    mgr.register_screen("live_lab",     live_lab)
    mgr.register_screen("ohm_triangle", triangle)
    mgr.register_screen("calculator",   calculator)

    mgr.switch_to("live_lab")

    log.info("Resistor Station started")

    # ------------------------------------------------------------------
    # Main loop state
    # ------------------------------------------------------------------

    last_t        = time.monotonic()
    last_measure  = 0.0          # time of last meter.measure() call
    last_result   = None         # most recent measurement dict (or None)
    last_bands    = []           # most recent 4-band list (or [])

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    try:
        running = True
        while running:
            now = time.monotonic()
            dt  = now - last_t
            last_t = now

            # -- Events --
            running = mgr.handle_events()

            # -- Measurement polling (hardware + serial send) --
            if meter is not None and (now - last_measure) >= MEASURE_INTERVAL:
                last_measure = now
                result = meter.measure()

                if result is not None:
                    if result.get("status") == "present":
                        std_r = result["standard_resistance"]
                        bands = color_code.resistance_to_bands(std_r)
                        band_names = [b["name"] for b in bands]
                        serial.send_measurement(std_r, band_names)
                        last_result = result
                        last_bands  = bands
                    else:
                        # Short or open — clear measurement state
                        last_result = result
                        last_bands  = []

            # -- Screen update --
            # Live lab is updated directly so we can inject measurement data.
            # All other screens go through mgr.update() as normal.
            if mgr.current_screen == "live_lab":
                live_lab.update(
                    dt,
                    measurement=last_result,
                    bands=last_bands if last_bands else None,
                )
            else:
                mgr.update(dt)

            # -- Draw --
            mgr.draw()

    finally:
        serial.close()
        log.info("Serial port closed")
        import pygame
        pygame.quit()
        log.info("Pygame quit")


if __name__ == "__main__":
    main()
