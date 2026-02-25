"""
Resistor Station - Resistor Calculator Screen

Enter a target resistance; display the nearest E24 value and colour bands.
Brutalist light theme: white cards, black borders, hard shadows.
"""

from __future__ import annotations

import math
import pygame

from color_code import snap_to_e24, resistance_to_bands

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

SCREEN_W  = 480
SCREEN_H  = 320
NAV_H     = 48
STATUS_H  = 24
CONTENT_Y = STATUS_H
CONTENT_H = SCREEN_H - NAV_H - STATUS_H   # 248 px

CONTENT_AREA = pygame.Rect(0, CONTENT_Y, SCREEN_W, CONTENT_H)

# Left panel
_LEFT_X  = 10
_LEFT_W  = 210
_LEFT_CX = _LEFT_X + _LEFT_W // 2

_INPUT_LABEL_Y = CONTENT_Y + 4
_INPUT_BOX_Y   = CONTENT_Y + 18
_INPUT_BOX_H   = 44

_RESULT_LABEL_Y = CONTENT_Y + 70
_RESULT_BOX_Y   = CONTENT_Y + 84
_RESULT_BOX_H   = 44

_RES_AREA_Y   = CONTENT_Y + 136
_RES_AREA_H   = 106
_RES_W        = 200
_RES_H        = 50
_RES_X        = _LEFT_X + (_LEFT_W - _RES_W) // 2
_RES_Y        = _RES_AREA_Y + (_RES_AREA_H - _RES_H) // 2
_BAND_LABEL_Y = _RES_Y + _RES_H + 4

_LEAD_PCT      = 0.15
_BODY_PCT      = 0.70
_RES_LEAD_W    = int(_RES_W * _LEAD_PCT)
_RES_BODY_X    = _RES_X + _RES_LEAD_W
_RES_BODY_W    = int(_RES_W * _BODY_PCT)
_RES_BAND_W    = max(2, int(_RES_W * 0.06))
_RES_BAND_PCTS = [0.20, 0.40, 0.60, 0.80]

# Right panel: keypad
_KP_LEFT   = 234
_KP_TOP    = CONTENT_Y + 6
_KP_BTN_W  = 68
_KP_BTN_H  = 44
_KP_GAP    = 6
_KP_COLS   = 3

# ---------------------------------------------------------------------------
# Colour palette — brutalist light theme
# ---------------------------------------------------------------------------

BG_COLOR       = (247, 245, 240)
CARD_BG        = (255, 255, 255)
RESULT_BG      = (240, 253, 244)   # green-tinted when result exists
TEXT_COLOR      = (24,  24,  27)
TEXT_MUTED      = (113, 113, 122)
BORDER_COLOR    = (0,   0,   0)
SHADOW_COLOR    = (0,   0,   0)
GRID_COLOR      = (235, 233, 228)
SCREW_COLOR     = (161, 161, 170)
ACCENT          = (239, 68,  68)    # red-500
GREEN           = (34,  197, 94)    # green-500
RED             = (239, 68,  68)
RESISTOR_TAN    = (232, 222, 194)
LEAD_COLOR      = (24,  24,  27)
GHOST_COLOR     = (161, 161, 170)
LCD_GREEN       = (57,  255, 20)

_KP_DIGIT_BG   = (255, 255, 255)
_KP_DEL_BG     = (239, 68,  68)    # red-500
_KP_EQ_BG      = (57,  255, 20)    # LCD green
_KP_EQ_FG      = (24,  24,  27)

_KEYPAD_LAYOUT = [
    ["1",  "2",  "3" ],
    ["4",  "5",  "6" ],
    ["7",  "8",  "9" ],
    [".",  "0",  "DEL"],
    ["\u006b\u03a9", "M\u03a9", "=" ],
]

_KEYPAD_STYLE = {
    "DEL": (_KP_DEL_BG, (255, 255, 255)),
    "=":   (_KP_EQ_BG,  _KP_EQ_FG),
}
_KEYPAD_DEFAULT_STYLE = (_KP_DIGIT_BG, TEXT_COLOR)


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

_FONT_CACHE = None


def _load_font(family, size, bold=False):
    try:
        font = pygame.font.SysFont(family, size, bold=bold)
        if font is None:
            raise RuntimeError("SysFont returned None")
        return font
    except Exception:
        return pygame.font.SysFont(None, size, bold=bold)


def _fonts():
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
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_text(surface, text, font, color, x, y, anchor="topleft"):
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    setattr(rect, anchor, (x, y))
    surface.blit(surf, rect)
    return rect


def _draw_hard_shadow_rect(surface, rect, color, radius=8):
    shadow = rect.move(2, 2)
    pygame.draw.rect(surface, SHADOW_COLOR, shadow, border_radius=radius)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, BORDER_COLOR, rect, width=2, border_radius=radius)


def _draw_grid(surface, area):
    for x in range(area.left, area.right, 20):
        pygame.draw.line(surface, GRID_COLOR, (x, area.top), (x, area.bottom))
    for y in range(area.top, area.bottom, 20):
        pygame.draw.line(surface, GRID_COLOR, (area.left, y), (area.right, y))


def _draw_screws(surface, area):
    inset = 8
    for pos in [
        (area.left + inset, area.top + inset),
        (area.right - inset, area.top + inset),
        (area.left + inset, area.bottom - inset),
        (area.right - inset, area.bottom - inset),
    ]:
        pygame.draw.circle(surface, SCREW_COLOR, pos, 3)
        pygame.draw.circle(surface, BORDER_COLOR, pos, 3, 1)


def _format_e24(ohms):
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
    """Resistor value calculator with brutalist light theme."""

    def __init__(self, surface) -> None:
        if hasattr(surface, "_surface"):
            self._ui      = surface
            self._surface = surface._surface
        else:
            self._ui      = None
            self._surface = surface

        self.input_buffer: str  = ""
        self._result_bands: list = []
        self._result_value: float | None = None
        self._keypad_rects: list[tuple[str, pygame.Rect]] = []
        self._pressed_key: str | None = None

        if not pygame.font.get_init():
            pygame.font.init()

    # ------------------------------------------------------------------
    # Screen interface
    # ------------------------------------------------------------------

    def update(self, dt):
        pass

    def draw(self, surface=None):
        target = surface if surface is not None else self._surface
        target.fill(BG_COLOR)

        try:
            fnt = _fonts()
            _draw_grid(target, CONTENT_AREA)
            self._draw_left_panel(target, fnt)
            self._draw_right_panel(target, fnt)
            _draw_screws(target, CONTENT_AREA)
        except Exception:
            pass

        self._pressed_key = None

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_BACKSPACE:
            self.input_buffer = self.input_buffer[:-1]
            return
        if event.key == pygame.K_RETURN:
            self._calculate()
            return
        if event.unicode.isdigit():
            if len(self.input_buffer) < 10:
                self.input_buffer += event.unicode
        elif event.unicode == ".":
            if "." not in self.input_buffer and len(self.input_buffer) < 10:
                self.input_buffer += "."

    def handle_touch(self, x, y):
        for label, rect in self._keypad_rects:
            if rect.collidepoint(x, y):
                self._pressed_key = label
                self._handle_keypad_label(label)
                return
        self._pressed_key = None

    # ------------------------------------------------------------------
    # Keypad dispatch
    # ------------------------------------------------------------------

    def _handle_keypad_label(self, label):
        if label in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
            if len(self.input_buffer) < 10:
                self.input_buffer += label
        elif label == ".":
            if "." not in self.input_buffer and len(self.input_buffer) < 10:
                self.input_buffer += label
        elif label == "DEL":
            self.input_buffer = self.input_buffer[:-1]
        elif label == "k\u03a9":
            self._apply_multiplier(1000)
        elif label == "M\u03a9":
            self._apply_multiplier(1_000_000)
        elif label == "=":
            self._calculate()

    def _apply_multiplier(self, factor):
        if not self.input_buffer:
            return
        try:
            value = float(self.input_buffer) * factor
            if value == int(value):
                self.input_buffer = str(int(value))
            else:
                self.input_buffer = f"{value:g}"
            if len(self.input_buffer) > 10:
                self.input_buffer = self.input_buffer[:10]
        except ValueError:
            pass

    def _calculate(self):
        if self.input_buffer:
            try:
                value = float(self.input_buffer)
                snapped = snap_to_e24(value)
                self._result_value = snapped
                self._result_bands = resistance_to_bands(snapped)
            except (ValueError, Exception):
                pass

    # ------------------------------------------------------------------
    # Left panel
    # ------------------------------------------------------------------

    def _draw_left_panel(self, surface, fnt):
        # Input box
        input_box = pygame.Rect(_LEFT_X, _INPUT_BOX_Y, _LEFT_W, _INPUT_BOX_H)

        _draw_text(surface, "Enter resistance", fnt["small"], TEXT_MUTED,
                   _LEFT_CX, _INPUT_LABEL_Y, anchor="midtop")

        _draw_hard_shadow_rect(surface, input_box, CARD_BG)

        # Accent top strip
        strip = pygame.Rect(input_box.x + 2, input_box.y + 2,
                             input_box.width - 4, 4)
        pygame.draw.rect(surface, ACCENT, strip)

        if self.input_buffer:
            display_text = self.input_buffer + " \u03a9"
            _draw_text(surface, display_text, fnt["heading"], TEXT_COLOR,
                       _LEFT_X + _LEFT_W - 12,
                       _INPUT_BOX_Y + _INPUT_BOX_H // 2,
                       anchor="midright")
        else:
            _draw_text(surface, "\u2014", fnt["heading"], TEXT_MUTED,
                       _LEFT_CX,
                       _INPUT_BOX_Y + _INPUT_BOX_H // 2,
                       anchor="center")

        # E24 result card
        result_box = pygame.Rect(_LEFT_X, _RESULT_BOX_Y, _LEFT_W, _RESULT_BOX_H)
        result_bg  = RESULT_BG if self._result_value is not None else CARD_BG

        _draw_text(surface, "Nearest E24", fnt["small"], TEXT_MUTED,
                   _LEFT_CX, _RESULT_LABEL_Y, anchor="midtop")

        _draw_hard_shadow_rect(surface, result_box, result_bg)

        strip2 = pygame.Rect(result_box.x + 2, result_box.y + 2,
                              result_box.width - 4, 4)
        pygame.draw.rect(surface, GREEN, strip2)

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

        # Resistor illustration
        self._draw_resistor_illustration(surface, fnt)

    def _draw_resistor_illustration(self, surface, fnt):
        res_cy = _RES_Y + _RES_H // 2
        bands = self._result_bands
        has_bands = (
            isinstance(bands, list)
            and len(bands) >= 4
            and isinstance(bands[0], dict)
            and "rgb" in bands[0]
        )

        lead_col = LEAD_COLOR if has_bands else GHOST_COLOR
        pygame.draw.line(surface, lead_col,
                         (_RES_X, res_cy), (_RES_BODY_X, res_cy), 2)
        pygame.draw.line(surface, lead_col,
                         (_RES_BODY_X + _RES_BODY_W, res_cy),
                         (_RES_X + _RES_W, res_cy), 2)

        body_rect = pygame.Rect(_RES_BODY_X, _RES_Y, _RES_BODY_W, _RES_H)
        radius    = max(2, _RES_H // 3)

        if not has_bands:
            pygame.draw.rect(surface, GHOST_COLOR, body_rect,
                             width=2, border_radius=radius)
            return

        shadow = body_rect.move(2, 2)
        pygame.draw.rect(surface, SHADOW_COLOR, shadow, border_radius=radius)
        pygame.draw.rect(surface, RESISTOR_TAN, body_rect, border_radius=radius)

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

        pygame.draw.rect(surface, BORDER_COLOR, body_rect,
                         width=2, border_radius=radius)

        for i, band in enumerate(bands[:4]):
            name = band.get("name", "")
            cx   = int(_RES_BODY_X + _RES_BAND_PCTS[i] * _RES_BODY_W)
            _draw_text(surface, name, fnt["band"], TEXT_MUTED,
                       cx, _BAND_LABEL_Y, anchor="midtop")

    # ------------------------------------------------------------------
    # Right panel: keypad
    # ------------------------------------------------------------------

    def _draw_right_panel(self, surface, fnt):
        self._keypad_rects = []

        for row_idx, row in enumerate(_KEYPAD_LAYOUT):
            for col_idx, label in enumerate(row):
                x = _KP_LEFT + col_idx * (_KP_BTN_W + _KP_GAP)
                y = _KP_TOP  + row_idx * (_KP_BTN_H + _KP_GAP)
                rect = pygame.Rect(x, y, _KP_BTN_W, _KP_BTN_H)

                self._keypad_rects.append((label, rect))

                bg_col, fg_col = _KEYPAD_STYLE.get(label, _KEYPAD_DEFAULT_STYLE)

                if self._pressed_key == label:
                    bg_col = tuple(max(0, int(c * 0.65)) for c in bg_col)

                _draw_hard_shadow_rect(surface, rect, bg_col, radius=6)
                _draw_text(surface, label, fnt["body"], fg_col,
                           rect.centerx, rect.centery, anchor="center")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_enter(self):
        pass

    def on_exit(self):
        self._pressed_key = None


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os

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
