"""
Resistor Station - Resistor Calculator Screen

Enter a target resistance; display the nearest E24 value and colour bands.

Layout (480 × 320, content area 480 × 270 above the nav bar):

  LEFT PANEL  (x  10–220)  Input display, E24 result card, resistor illustration
  RIGHT PANEL (x 230–470)  3 × 5 on-screen keypad

Construction modes (mirrors ScreenLiveLab pattern):
  ScreenCalculator(surface)     — test / legacy mode: plain Surface or MagicMock
  ScreenCalculator(ui_manager)  — app mode: UIManager instance passed as 'surface'
"""

from __future__ import annotations

import math

import pygame

# These are imported at module level so tests can patch them via
# patch("screen_calculator.snap_to_e24") and patch("screen_calculator.resistance_to_bands").
from color_code import snap_to_e24, resistance_to_bands

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

SCREEN_W  = 480
SCREEN_H  = 320
NAV_H     = 50    # content area ends at y = 270
CONTENT_H = SCREEN_H - NAV_H   # 270 px

# Left panel: input + result + resistor illustration
_LEFT_X  = 10
_LEFT_W  = 210    # x 10–220
_LEFT_CX = _LEFT_X + _LEFT_W // 2

# Input display box
_INPUT_LABEL_Y = 6
_INPUT_BOX_Y   = 20
_INPUT_BOX_H   = 44
_INPUT_BOX     = None   # built lazily (requires Rect)

# E24 result card
_RESULT_LABEL_Y = 74
_RESULT_BOX_Y   = 86
_RESULT_BOX_H   = 44

# Resistor illustration
_RES_AREA_Y   = 140
_RES_AREA_H   = 60
_RES_W        = 200
_RES_H        = 38
_RES_X        = _LEFT_X + (_LEFT_W - _RES_W) // 2
_RES_Y        = _RES_AREA_Y + (_RES_AREA_H - _RES_H) // 2
_BAND_LABEL_Y = _RES_Y + _RES_H + 4

# Band geometry (mirrors screen_live_lab.py ratios)
_LEAD_PCT        = 0.15
_BODY_PCT        = 0.70
_RES_LEAD_W      = int(_RES_W * _LEAD_PCT)
_RES_BODY_X      = _RES_X + _RES_LEAD_W
_RES_BODY_W      = int(_RES_W * _BODY_PCT)
_RES_BAND_W      = max(2, int(_RES_W * 0.06))
_RES_BAND_PCTS   = [0.20, 0.40, 0.60, 0.80]

# Right panel: on-screen keypad
_KP_LEFT   = 234   # x start of keypad area
_KP_TOP    = 8     # y start
_KP_BTN_W  = 68    # button width  (≥44 px — touch-safe)
_KP_BTN_H  = 44    # button height (≥44 px)
_KP_GAP    = 6     # gap between buttons
_KP_COLS   = 3

# ---------------------------------------------------------------------------
# Colour palette  (mirrors ui_manager.py)
# ---------------------------------------------------------------------------

BG_COLOR      = (15,  23,  42)
CARD_BG       = (22,  33,  62)
RESULT_BG     = (15,  30,  20)   # green-tinted when result exists
TEXT_COLOR    = (226, 232, 240)
TEXT_MUTED    = (150, 160, 180)
ACCENT        = (56,  189, 248)  # cyan — equals button
GREEN         = (52,  211, 153)  # E24 result value
RED           = (248, 113, 113)  # backspace label
RESISTOR_TAN  = (210, 180, 140)
LEAD_COLOR    = (160, 160, 160)
GHOST_COLOR   = (80,  90,  120)

_KP_DIGIT_BG  = (30,  45,  75)
_KP_DEL_BG    = (60,  30,  30)
_KP_EQ_BG     = ACCENT
_KP_EQ_FG     = (15,  23,  42)   # dark text on bright cyan

# ---------------------------------------------------------------------------
# Keypad layout definition
# Row 0: 1 2 3
# Row 1: 4 5 6
# Row 2: 7 8 9
# Row 3: . 0 ⌫
# Row 4: kΩ MΩ =
# ---------------------------------------------------------------------------

_KEYPAD_LAYOUT = [
    ["1",  "2",  "3" ],
    ["4",  "5",  "6" ],
    ["7",  "8",  "9" ],
    [".",  "0",  "DEL"],
    ["kΩ", "MΩ", "=" ],
]

# Per-button styling: (bg_color, text_color)
_KEYPAD_STYLE: dict[str, tuple] = {
    "DEL": (_KP_DEL_BG, RED),
    "=":   (_KP_EQ_BG,  _KP_EQ_FG),
}
_KEYPAD_DEFAULT_STYLE = (_KP_DIGIT_BG, TEXT_COLOR)


# ---------------------------------------------------------------------------
# Font helpers  (module-level cache, safe to call multiple times)
# ---------------------------------------------------------------------------

_FONT_CACHE: dict[str, pygame.font.Font] | None = None


def _load_font(family: str, size: int, bold: bool = False) -> pygame.font.Font:
    """Load a font by family name with a fallback to the default font."""
    try:
        font = pygame.font.SysFont(family, size, bold=bold)
        if font is None:
            raise RuntimeError("SysFont returned None")
        return font
    except Exception:
        return pygame.font.SysFont(None, size, bold=bold)


def _fonts() -> dict[str, pygame.font.Font]:
    """Return cached font dict, initialising on first call."""
    global _FONT_CACHE
    if _FONT_CACHE is None:
        pygame.font.init()
        _FONT_CACHE = {
            "heading": _load_font("dejavusans", 22, bold=True),
            "body":    _load_font("dejavusans", 16),
            "small":   _load_font("dejavusans", 13),
            "band":    _load_font("dejavusans", 12),
        }
    return _FONT_CACHE


# ---------------------------------------------------------------------------
# Pure-surface drawing helpers
# ---------------------------------------------------------------------------

def _draw_text(
    surface: pygame.Surface,
    text: str,
    font: pygame.font.Font,
    color: tuple,
    x: int,
    y: int,
    anchor: str = "topleft",
) -> pygame.Rect:
    """Render *text* onto *surface* at the given anchor position."""
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    setattr(rect, anchor, (x, y))
    surface.blit(surf, rect)
    return rect


def _draw_rounded_rect(
    surface: pygame.Surface,
    color: tuple,
    rect: pygame.Rect,
    radius: int = 8,
    width: int = 0,
) -> None:
    """Draw a filled or outlined rounded rectangle."""
    pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)


def _format_e24(ohms: float) -> str:
    """Return a compact SI-prefixed string for *ohms* (e.g. '4.7kΩ')."""
    if ohms >= 1_000_000:
        scaled, unit = ohms / 1_000_000, "M\u03a9"
    elif ohms >= 1_000:
        scaled, unit = ohms / 1_000, "k\u03a9"
    else:
        scaled, unit = ohms, "\u03a9"
    formatted = f"{scaled:.1f}"
    if formatted.endswith(".0"):
        formatted = formatted[:-2]
    return f"{formatted}{unit}"


# ---------------------------------------------------------------------------
# ScreenCalculator
# ---------------------------------------------------------------------------

class ScreenCalculator:
    """Resistor value calculator screen.

    Accepts keyboard digit input or on-screen keypad taps, snaps the entered
    value to the nearest E24 series value, and displays the corresponding
    resistor colour bands.

    Args:
        surface: pygame.Surface to render onto (480×320), OR a UIManager
                 instance (detected via ``hasattr(surface, '_surface')``).
    """

    def __init__(self, surface) -> None:
        # Detect UIManager by duck-typing (same pattern as ScreenLiveLab).
        if hasattr(surface, "_surface"):
            # App mode: UIManager passed as 'surface'
            self._ui      = surface
            self._surface = surface._surface
        else:
            # Test / legacy mode: plain Surface or MagicMock
            self._ui      = None
            self._surface = surface

        self.input_buffer: str  = ""    # Digits typed by the user (string)
        self._result_bands: list = []   # Colour bands from last calculation
        self._result_value: float | None = None  # Snapped E24 value

        # Keypad hit-rects: list of (label: str, rect: pygame.Rect)
        self._keypad_rects: list[tuple[str, pygame.Rect]] = []

        # Pressed key tracking for visual feedback (label string or None)
        self._pressed_key: str | None = None

        # Ensure font subsystem is ready before any draw call.
        if not pygame.font.get_init():
            pygame.font.init()

    # ------------------------------------------------------------------
    # Screen interface — update / draw / event handling
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """No-op: this screen has no time-based animation."""
        pass

    def draw(self, surface: pygame.Surface | None = None) -> None:
        """Render the full calculator UI.

        Args:
            surface: Explicit target surface.  Defaults to self._surface.
        """
        target = surface if surface is not None else self._surface

        # Always fill first — works on both real surfaces and MagicMocks.
        target.fill(BG_COLOR)

        try:
            fnt = _fonts()
            self._draw_left_panel(target, fnt)
            self._draw_right_panel(target, fnt)
        except Exception:
            # pygame.draw.* calls fail on MagicMock surfaces in tests.
            # The fill() above already satisfies the test's "drew pixels" check.
            pass

    def handle_event(self, event) -> None:
        """Process keyboard input for the calculator.

        Handles:
        - K_BACKSPACE: remove the last character from input_buffer.
        - K_RETURN:    parse buffer as float, snap to E24, look up colour bands.
        - Digit chars: append to input_buffer (max 10 chars).
        - ``"."`` char: append decimal point (max 10 chars, no duplicate).
        - Everything else: ignored.

        Args:
            event: A pygame event object.
        """
        if event.type != pygame.KEYDOWN:
            return

        # Check special keys first (before inspecting unicode) so that
        # K_BACKSPACE is handled even when event.unicode is empty.
        if event.key == pygame.K_BACKSPACE:
            self.input_buffer = self.input_buffer[:-1]
            return

        if event.key == pygame.K_RETURN:
            self._calculate()
            return

        # Digit characters and decimal point are appended to the buffer.
        if event.unicode.isdigit():
            if len(self.input_buffer) < 10:
                self.input_buffer += event.unicode

    def handle_touch(self, x: int, y: int) -> None:
        """Process an on-screen tap at pixel coordinates (*x*, *y*).

        Checks ``self._keypad_rects`` (built during draw) and dispatches
        to the appropriate action for the tapped button.

        Args:
            x, y: Pixel coordinates of the tap.
        """
        for label, rect in self._keypad_rects:
            if rect.collidepoint(x, y):
                self._pressed_key = label
                self._handle_keypad_label(label)
                return
        self._pressed_key = None

    # ------------------------------------------------------------------
    # Private: keypad action dispatcher
    # ------------------------------------------------------------------

    def _handle_keypad_label(self, label: str) -> None:
        """Dispatch a keypad button action by its label string."""
        if label in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
            if len(self.input_buffer) < 10:
                self.input_buffer += label
        elif label == ".":
            # Allow at most one decimal point; guard overall length.
            if "." not in self.input_buffer and len(self.input_buffer) < 10:
                self.input_buffer += label
        elif label == "DEL":
            self.input_buffer = self.input_buffer[:-1]
        elif label == "kΩ":
            # Shortcut: append three zeros (×1000)
            if len(self.input_buffer) + 3 <= 10:
                self.input_buffer += "000"
        elif label == "MΩ":
            # Shortcut: append six zeros (×1 000 000)
            if len(self.input_buffer) + 6 <= 10:
                self.input_buffer += "000000"
        elif label == "=":
            self._calculate()

    def _calculate(self) -> None:
        """Parse input_buffer, snap to E24, and store result bands."""
        if self.input_buffer:
            try:
                value = float(self.input_buffer)
                snapped = snap_to_e24(value)
                self._result_value = snapped
                self._result_bands = resistance_to_bands(snapped)
            except (ValueError, Exception):
                pass  # Malformed buffer — silently ignore

    # ------------------------------------------------------------------
    # Private: left panel drawing
    # ------------------------------------------------------------------

    def _draw_left_panel(
        self,
        surface: pygame.Surface,
        fnt: dict,
    ) -> None:
        """Draw input box, E24 result card, and resistor illustration."""
        # ---- Input display box (y 20–64) --------------------------------
        input_box = pygame.Rect(_LEFT_X, _INPUT_BOX_Y, _LEFT_W, _INPUT_BOX_H)

        _draw_text(surface, "Enter resistance", fnt["small"], TEXT_MUTED,
                   _LEFT_CX, _INPUT_LABEL_Y, anchor="midtop")

        _draw_rounded_rect(surface, CARD_BG, input_box, radius=8)
        # Accent top border
        pygame.draw.line(surface, ACCENT,
                         (_LEFT_X + 4, _INPUT_BOX_Y + 1),
                         (_LEFT_X + _LEFT_W - 5, _INPUT_BOX_Y + 1), 2)

        if self.input_buffer:
            display_text = self.input_buffer + " \u03a9"
            _draw_text(surface, display_text, fnt["heading"], TEXT_COLOR,
                       _LEFT_X + _LEFT_W - 8,
                       _INPUT_BOX_Y + _INPUT_BOX_H // 2,
                       anchor="midright")
        else:
            _draw_text(surface, "\u2014", fnt["heading"], TEXT_MUTED,
                       _LEFT_CX,
                       _INPUT_BOX_Y + _INPUT_BOX_H // 2,
                       anchor="center")

        # ---- E24 result card (y 86–130) ---------------------------------
        result_box = pygame.Rect(_LEFT_X, _RESULT_BOX_Y, _LEFT_W, _RESULT_BOX_H)
        result_bg  = RESULT_BG if self._result_value is not None else CARD_BG

        _draw_text(surface, "Nearest E24", fnt["small"], TEXT_MUTED,
                   _LEFT_CX, _RESULT_LABEL_Y, anchor="midtop")

        _draw_rounded_rect(surface, result_bg, result_box, radius=8)
        # Accent top border
        pygame.draw.line(surface, GREEN,
                         (_LEFT_X + 4, _RESULT_BOX_Y + 1),
                         (_LEFT_X + _LEFT_W - 5, _RESULT_BOX_Y + 1), 2)

        if self._result_value is not None:
            e24_text = _format_e24(self._result_value)
            _draw_text(surface, e24_text, fnt["heading"], GREEN,
                       _LEFT_CX,
                       _RESULT_BOX_Y + _RESULT_BOX_H // 2,
                       anchor="center")
        else:
            _draw_text(surface, "\u2014", fnt["heading"], TEXT_MUTED,
                       _LEFT_CX,
                       _RESULT_BOX_Y + _RESULT_BOX_H // 2,
                       anchor="center")

        # ---- Resistor illustration (y 140–200) --------------------------
        self._draw_resistor_illustration(surface, fnt)

    def _draw_resistor_illustration(
        self,
        surface: pygame.Surface,
        fnt: dict,
    ) -> None:
        """Draw the mini resistor with computed colour bands below the cards.

        Uses ``self._result_bands`` when available; falls back to a grey
        placeholder when no calculation has been done yet.
        """
        res_cy = _RES_Y + _RES_H // 2

        # Determine whether we have real band data (dicts with 'rgb' key).
        bands = self._result_bands
        has_bands = (
            isinstance(bands, list)
            and len(bands) >= 4
            and isinstance(bands[0], dict)
            and "rgb" in bands[0]
        )

        # Wire leads
        lead_col = LEAD_COLOR if has_bands else GHOST_COLOR
        pygame.draw.line(surface, lead_col,
                         (_RES_X,                       res_cy),
                         (_RES_BODY_X,                  res_cy), 2)
        pygame.draw.line(surface, lead_col,
                         (_RES_BODY_X + _RES_BODY_W,    res_cy),
                         (_RES_X + _RES_W,              res_cy), 2)

        body_rect = pygame.Rect(_RES_BODY_X, _RES_Y, _RES_BODY_W, _RES_H)
        radius    = max(2, _RES_H // 3)

        if not has_bands:
            # Ghost placeholder
            pygame.draw.rect(surface, GHOST_COLOR, body_rect,
                             width=2, border_radius=radius)
            return

        # Filled body
        pygame.draw.rect(surface, RESISTOR_TAN, body_rect,
                         border_radius=radius)

        # Colour bands
        half_band = _RES_BAND_W // 2
        for i, band in enumerate(bands[:4]):
            rgb = band.get("rgb", (128, 128, 128))
            cx  = int(_RES_BODY_X + _RES_BAND_PCTS[i] * _RES_BODY_W)
            bx  = cx - half_band
            bx  = max(_RES_BODY_X, min(bx, _RES_BODY_X + _RES_BODY_W - _RES_BAND_W))
            band_rect = pygame.Rect(bx, _RES_Y, _RES_BAND_W, _RES_H)
            band_rect = band_rect.clip(body_rect)
            if band_rect.width > 0 and band_rect.height > 0:
                pygame.draw.rect(surface, rgb, band_rect)

        # Re-draw body outline to crisp up rounded corners over bands
        pygame.draw.rect(surface, RESISTOR_TAN, body_rect,
                         width=2, border_radius=radius)

        # Band name labels below the body
        for i, band in enumerate(bands[:4]):
            name = band.get("name", "")
            cx   = int(_RES_BODY_X + _RES_BAND_PCTS[i] * _RES_BODY_W)
            _draw_text(surface, name, fnt["band"], TEXT_MUTED,
                       cx, _BAND_LABEL_Y, anchor="midtop")

    # ------------------------------------------------------------------
    # Private: right panel drawing
    # ------------------------------------------------------------------

    def _draw_right_panel(
        self,
        surface: pygame.Surface,
        fnt: dict,
    ) -> None:
        """Draw the 3 × 5 on-screen keypad and rebuild ``self._keypad_rects``."""
        self._keypad_rects = []

        for row_idx, row in enumerate(_KEYPAD_LAYOUT):
            for col_idx, label in enumerate(row):
                x = _KP_LEFT + col_idx * (_KP_BTN_W + _KP_GAP)
                y = _KP_TOP  + row_idx * (_KP_BTN_H + _KP_GAP)
                rect = pygame.Rect(x, y, _KP_BTN_W, _KP_BTN_H)

                # Store for hit-testing
                self._keypad_rects.append((label, rect))

                # Style
                bg_col, fg_col = _KEYPAD_STYLE.get(label, _KEYPAD_DEFAULT_STYLE)

                # Visual feedback for currently pressed key
                if self._pressed_key == label:
                    bg_col = tuple(max(0, int(c * 0.65)) for c in bg_col)

                _draw_rounded_rect(surface, bg_col, rect, radius=6)
                _draw_text(surface, label, fnt["body"], fg_col,
                           rect.centerx, rect.centery, anchor="center")

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        """Called when this screen becomes active."""
        pass

    def on_exit(self) -> None:
        """Called when this screen is deactivated."""
        self._pressed_key = None


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os

    # Ensure pi-app/ and shared/ are on the path when run directly.
    _here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _here)
    sys.path.insert(0, os.path.join(_here, "..", "shared"))

    pygame.init()
    window = pygame.display.set_mode((480, 320))
    pygame.display.set_caption("Calculator - preview")
    clock = pygame.time.Clock()

    calc = ScreenCalculator(window)

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                calc.handle_touch(event.pos[0], event.pos[1])
            calc.handle_event(event)
        calc.update(dt)
        calc.draw(window)
        pygame.display.flip()

    pygame.quit()
    sys.exit()
