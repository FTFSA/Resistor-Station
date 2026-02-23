# Raspberry Pi Dependency Resolver - Project Memory

## Project: Resistor Station

**Target hardware:** Raspberry Pi 4
**OS:** Raspberry Pi OS (Bookworm assumed — latest as of project creation)
**Display:** MPI3508 480x320 touchscreen over HDMI
**ADC:** ADS1115 at I2C address 0x48
**Serial:** USB CDC to Adafruit Matrix Portal M4 at /dev/ttyACM0, 115200 baud

## Key File Paths

- Pi app root: `pi-app/`
- Entry point: `pi-app/main.py`
- Requirements: `pi-app/requirements.txt`
- Shared constants (must be on sys.path): `shared/` (imported via `sys.path.insert`)
- Tests: `pi-app/tests/` (uses SDL dummy mode, stubs hardware modules)

## Python Import Map (actual imports found in source)

| File | Imports |
|------|---------|
| color_code.py | math, sys, os, resistor_constants (from shared/) |
| screen_calculator.py | pygame, color_code.snap_to_e24, color_code.resistance_to_bands |
| screen_live_lab.py | pygame |
| screen_ohm_triangle.py | pygame |
| serial_comms.py | pyserial (serial) — TODO stub, not yet implemented |
| measurement.py | adafruit_ads1x15.ads1115, busio, board — TODO stub, not yet implemented |
| main.py | Nothing yet (all TODO) |
| ui_manager.py | No imports (pure Python) |
| conftest.py stubs: board, busio, adafruit_blinka, adafruit_ads1x15, adafruit_ads1x15.ads1115, adafruit_ads1x15.analog_in, serial |

## Confirmed Requirements

### requirements.txt (current)
- pygame
- adafruit-circuitpython-ads1x15
- pyserial
- adafruit-blinka

### Missing from requirements.txt
- `RPi.GPIO` or `lgpio` — blinka on Pi 4 with Bookworm needs lgpio (not RPi.GPIO)
- `pytest` — needed to run tests (dev dependency)

### Critical: adafruit-blinka on Pi 4 Bookworm
- Requires env var: `BLINKA_MCP2221=1` is NOT needed; for native Pi GPIO use `BLINKA_RASPBERRY_PI=1` is not needed either — blinka auto-detects Pi
- The correct env var for Pi 4 native I2C is NO extra env var needed; blinka detects automatically
- BUT: Bookworm switched from RPi.GPIO to lgpio — blinka >= 8.x uses lgpio on Bookworm

### System apt packages required
- python3-pygame OR compile from pip (pip version preferred for Pygame 2.x)
- python3-dev, gcc, libffi-dev (for packages requiring compilation)
- i2c-tools (for i2cdetect verification)
- python3-lgpio (or lgpio via pip) for blinka on Bookworm
- libsdl2-dev, libsdl2-ttf-dev, libsdl2-image-dev, libsdl2-mixer-dev (if pygame built from pip)
- libjpeg-dev, libpng-dev (pygame image support)

### raspi-config / /boot/firmware/config.txt changes
- Enable I2C: `dtparam=i2c_arm=on` — required for ADS1115
- Serial console must NOT occupy ttyACM0 (it won't — ttyACM0 is USB CDC, not UART)
- No SPI needed for this project

### User groups required
- `dialout` — for /dev/ttyACM0 serial access
- `i2c` — for I2C bus access without sudo
- `video` — for framebuffer/display access (usually already a member)

### sys.path note
- color_code.py inserts `../shared` into sys.path at runtime
- When running `python3 pi-app/main.py` from repo root, the shared/ import works
- When running from pi-app/ directly, `../shared` resolves correctly too

## Known Issues / Notes
- Bookworm moved boot config from /boot/config.txt to /boot/firmware/config.txt
- Bookworm uses PEP 668 — pip install requires --break-system-packages or venv
- MPI3508 over HDMI needs no special driver — standard HDMI display, SDL uses it natively
- pygame from pip on Pi 4 Bookworm builds fine; apt python3-pygame is pygame 2.1.x
- adafruit-blinka on Bookworm: lgpio replaces RPi.GPIO; install python3-lgpio via apt
