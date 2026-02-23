# Pygame Touchscreen UI - Agent Memory

## Project Structure
- `pi-app/ui_manager.py` — UIManager class (screen registry + dispatch)
- `pi-app/screen_live_lab.py` — ScreenLiveLab (measurement dashboard)
- `pi-app/screen_ohm_triangle.py` — ScreenOhmTriangle (V=IR solver)
- `pi-app/screen_calculator.py` — ScreenCalculator (E24 resistor calc)
- `pi-app/color_code.py` — snap_to_e24(), resistance_to_bands(), bands_to_rgb()
- `pi-app/tests/test_ui.py` — 39 pytest tests (all passing)
- `pi-app/tests/conftest.py` — SDL dummy mode, hardware stubs, sys.path setup
- `shared/resistor_constants.py` — E24_VALUES, COLOR_BANDS, TOLERANCE_BANDS

## Architecture Decisions
- UIManager stores screens in `self._screens` dict, active key in `self._active` (str or None)
- switch_to() raises KeyError for unknown names
- draw()/update()/handle_event() are no-ops when self._active is None (never crash)
- ScreenLiveLab.update() calls meter.read() then serial.send_measurement(resistance, bands)
  - resistance is FIRST positional arg to send_measurement (test checks args[0][0])
- screen_calculator.py imports snap_to_e24 and resistance_to_bands at MODULE LEVEL
  - Required so tests can patch via patch("screen_calculator.snap_to_e24")
- handle_event() in ScreenCalculator checks event.key BEFORE event.unicode
  - K_BACKSPACE arrives with unicode="" — key check must come first
  - Only event.unicode.isdigit() chars are appended (non-digits silently ignored)

## color_code.py Implementation Notes
- snap_to_e24() rounds UP to next E24 value for safety (uses 1e-9 epsilon for float equality)
- resistance_to_bands() returns [digit1, digit2, multiplier, 'gold'] — always gold tolerance
- Multiplier exponent = floor(log10(resistance)) - 1, giving a 2-digit mantissa [10..99]
- _MULTIPLIER_COLORS dict maps exponent -> color name (silver=-2, gold=-1, black=0, brown=1, ...)
- Path to shared/: inserted via sys.path in color_code.py using __file__ relative navigation

## Test Environment
- SDL_VIDEODRIVER=dummy (set in conftest.py before pygame import)
- Surface is MagicMock(spec=pygame.Surface) — not a real surface
- Hardware modules (board, busio, adafruit_*, serial) are stubbed as MagicMock in conftest.py
- Tests import from pi-app/ directly (sys.path set in conftest.py)

## Screen Interface Contract
Every screen must implement: __init__, update(dt), draw(), handle_event(event)
Optional: on_enter(), on_exit()
draw() must call surface.fill(), surface.blit(), or pygame.draw.* (test checks this)

## demo.py — Standalone Preview
- File: `pi-app/demo.py` — self-contained, no hardware imports
- Adds pi-app/ and shared/ to sys.path at top using os.path + __file__ pattern
- Layout: CONTENT_H=280, NAV_H=40, total SCREEN_H=320
- Uses pygame.font.SysFont("monospace", size) — no font file paths
- Colour constants: BG_COLOR=(26,26,46), CARD_COLOR=(22,33,62), NAV_BG=(15,15,26), ACCENT_ORANGE=(255,107,0)
- NavBar: three equal rects at y=280, each SCREEN_W//3 wide, 40px tall
- draw_resistor(): body_margin_x = rect.width//5; leads drawn as lines; 4 bands in 80% of body width
- Ohm triangle zone hit-test uses _point_in_triangle() with sign-of-cross-product method
  - I zone = (v_apex, i_base, centroid), R zone = (v_apex, r_base, centroid)
  - Full triangle drawn as overlapping polygons; no separate alpha surface needed
- Calculator keypad: 3-col x 4-row grid starting at x=248, y=60; btn_w=64, btn_h=44, gap=6
  - Action row below: Clear (1 col) + Enter (2 cols wide)
  - Physical keyboard also handled for convenience (digit, backspace, enter, escape)
- bands_to_rgb() returns (R,G,B) tuples; COLOR_BANDS in shared/resistor_constants.py maps name->(digit, rgb)
- Headless CI: SDL_VIDEODRIVER=dummy prevents window; smoke-tested with importlib.util.spec_from_file_location
