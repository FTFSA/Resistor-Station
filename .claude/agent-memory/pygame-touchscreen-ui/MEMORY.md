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
- switch_to() raises KeyError for unknown names; switch_screen() is an alias
- draw()/update()/handle_event() are no-ops when self._active is None (never crash)
- UIManager has dual-mode construction:
  - `UIManager()` — hardware mode: calls pygame.init(), fullscreen display, clock
  - `UIManager(surface)` — test mode: calls pygame.font.init() ONLY, uses supplied surface
  - Test mode skips draw_nav_bar() and display.flip() to avoid pygame.draw on MagicMock
- draw() in hardware mode calls screen.draw(self._surface), draws nav bar, flips display
- draw() in test mode calls screen.draw(self._surface) only (no nav, no flip)
- ScreenLiveLab.update() calls meter.read() then serial.send_measurement(resistance, bands)
  - resistance is FIRST positional arg to send_measurement (test checks args[0][0])
- screen_calculator.py imports snap_to_e24 and resistance_to_bands at MODULE LEVEL
  - Required so tests can patch via patch("screen_calculator.snap_to_e24")
- handle_event() in ScreenCalculator checks event.key BEFORE event.unicode
  - K_BACKSPACE arrives with unicode="" — key check must come first
  - Only event.unicode.isdigit() chars are appended (non-digits silently ignored)

## UIManager Layout Constants (ui_manager.py)
- SCREEN_W=480, SCREEN_H=320, NAV_H=48, CONTENT_H=272
- CONTENT_AREA = pygame.Rect(0, 0, 480, 272)
- NAV_BAR_AREA = pygame.Rect(0, 272, 480, 48)
- Nav: 3 buttons x 160px (_NAV_BTN_W = SCREEN_W//3), y starts at SCREEN_H - NAV_H = 272
- _nav_rects built in draw_nav_bar(); initialized to [] in __init__ so _nav_hit never crashes

## UIManager Colour Constants (ui_manager.py)
- BG_COLOR=(15,23,42), TEXT_COLOR=(226,232,240), ACCENT=(56,189,248)
- GREEN=(52,211,153), ORANGE=(251,146,60), YELLOW=(251,191,36), RED=(248,113,113)
- NAV_BG=(8,15,30), NAV_BORDER=(30,41,59), RESISTOR_TAN=(210,180,140)

## Font Loading Pattern (CRITICAL)
- In test mode: call pygame.font.init() before SysFont — font subsystem needs init without display
- pygame.font.SysFont() raises pygame.error "font not initialized" if subsystem not init'd
- SysFont can return None in some dummy SDL environments — check and raise RuntimeError
- Fall back to SysFont(None, size) if named family fails

## draw_resistor() in ui_manager.py
- `draw_resistor(surface, x, y, w, h, bands)` — bands is list of dicts with 'rgb' key
- Lead width = w*0.15 each side; body_x = x + w*0.15; body_w = w*0.70
- 4 band centres at 20%, 40%, 60%, 80% of body_w from body_x
- Band width = w*0.06; clips to body rect to avoid corner overdraw
- Re-draws body outline (width=2) after bands to crisp up rounded corners

## color_code.py Implementation Notes
- snap_to_e24() uses log-ratio distance — nearest match, not always rounding up
- resistance_to_bands() returns [digit1, digit2, multiplier, tolerance] dicts
- Each band dict has 'digit', 'name', 'rgb' keys; tolerance dict has 'tolerance' float
- Path to shared/: inserted via sys.path in color_code.py using __file__ relative navigation

## Test Environment
- SDL_VIDEODRIVER=dummy (set in conftest.py before pygame import)
- Surface is MagicMock(spec=pygame.Surface) — not a real surface
- Hardware modules (board, busio, adafruit_*, serial) are stubbed as MagicMock in conftest.py
- Tests import from pi-app/ directly (sys.path set in conftest.py)

## Screen Interface Contract
Every screen must implement: __init__, update(dt), draw(surface), handle_event(event)
Optional: on_enter(), on_exit()
draw() receives surface as argument; must call surface.fill(), surface.blit(), or pygame.draw.*

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
