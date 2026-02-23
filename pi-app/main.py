"""
Resistor Station - Raspberry Pi 4 Main Entry Point

Initialises hardware (ADS1115, serial to Portal M4), builds the Pygame UI,
and runs the main event loop.

Hardware failures (ADS1115 not found, Portal not connected) are caught and
logged; the app continues in a degraded state so the UI is still usable.
"""

import logging
import sys
import time

import config
from ui_manager import UIManager
from measurement import ResistanceMeter
from serial_comms import PortalSerial
from screen_live_lab import ScreenLiveLab
from screen_ohm_triangle import ScreenOhmTriangle
from screen_calculator import ScreenCalculator

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


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
        log.info("Portal M4 serial connected on %s", config.SERIAL_PORT)
    else:
        log.warning("Portal M4 not connected on %s — will retry automatically", config.SERIAL_PORT)

    # ------------------------------------------------------------------
    # Pygame + UIManager (creates 480x320 fullscreen display)
    # ------------------------------------------------------------------

    mgr = UIManager()
    surface = mgr.screen

    # ------------------------------------------------------------------
    # Screens
    # ------------------------------------------------------------------

    live_lab   = ScreenLiveLab(surface, meter=meter, serial=serial)
    triangle   = ScreenOhmTriangle(surface)
    calculator = ScreenCalculator(surface)

    mgr.register_screen("live_lab",     live_lab)
    mgr.register_screen("ohm_triangle", triangle)
    mgr.register_screen("calculator",   calculator)

    mgr.switch_to("live_lab")

    log.info("Resistor Station started — entering main loop")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    last_t = time.monotonic()

    try:
        running = True
        while running:
            now = time.monotonic()
            dt  = now - last_t
            last_t = now

            running = mgr.handle_events()
            mgr.update(dt)
            mgr.draw()

    finally:
        serial.close()
        log.info("Serial port closed")
        import pygame
        pygame.quit()
        log.info("Pygame quit")


if __name__ == "__main__":
    main()
