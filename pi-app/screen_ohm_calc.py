"""
Resistor Station - Ohm's Law Calculator Screen

Solve for V, I, R, or P given two known values.
Left panel: mode selector, LCD display, input fields.
Right panel: 4x4 keypad.
Brutalist light theme with LCD-green display.
"""

from __future__ import annotations

import math
import pygame

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

# Left panel (45%)
LEFT_W   = 216
LEFT_X   = 6

# Mode selector buttons
MODE_BTN_Y = CONTENT_Y + 6
MODE_BTN_W = 46
MODE_BTN_H = 30
MODE_BTN_GAP = 4

# LCD display
LCD_X = LEFT_X
LCD_Y = CONTENT_Y + 44
LCD_W = LEFT_W - 12
LCD_H = 62

# Input fields
INPUT1_Y = CONTENT_Y + 116
INPUT2_Y = CONTENT_Y + 162
INPUT_W  = LEFT_W - 12
INPUT_H  = 38

# Right panel: keypad
_KP_LEFT  = 230
_KP_TOP   = CONTENT_Y + 6
_KP_BTN_W = 56
_KP_BTN_H = 48
_KP_GAP   = 5
_KP_COLS  = 4

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

BG_COLOR       = (247, 245, 240)
CARD_BG        = (255, 255, 255)
TEXT_COLOR      = (24,  24,  27)
TEXT_MUTED      = (113, 113, 122)
BORDER_COLOR    = (0,   0,   0)
SHADOW_COLOR    = (0,   0,   0)
GRID_COLOR      = (235, 233, 228)
SCREW_COLOR     = (161, 161, 170)

LCD_BG          = (18,  18,  18)
LCD_GREEN       = (57,  255, 20)
LCD_DIM         = (20,  80,  10)

VOLTAGE_COLOR   = (239, 68,  68)
CURRENT_COLOR   = (59,  130, 246)
RESIST_COLOR    = (251, 146, 60)
POWER_COLOR     = (16,  185, 129)

_MODE_COLORS = {
    "V": VOLTAGE_COLOR,
    "I": CURRENT_COLOR,
    "R": RESIST_COLOR,
    "P": POWER_COLOR,
}

# Keypad layout: 4 columns × 4 rows
_KEYPAD_LAYOUT = [
    ["7", "8", "9", "DEL"],
    ["4", "5", "6", "ENT"],
    ["1", "2", "3", ""],     # ENT spans row 1-2
    ["0", ".", "CLR", ""],   # empty = skip
]

_KP_DEL_BG  = (239, 68,  68)    # red
_KP_ENT_BG  = (57,  255, 20)    # LCD green
_KP_CLR_BG  = (228, 228, 231)   # zinc-200
_KP_DIGIT_BG = (255, 255, 255)

# ---------------------------------------------------------------------------
# Ohm's Law + Power formulas
# ---------------------------------------------------------------------------

# Given solve_for and two knowns, compute result
# P = V * I,  V = I * R,  P = I^2 * R,  P = V^2 / R

_INPUT_PAIRS = {
    "V": [("I", "R"), ("P", "I"), ("P", "R")],
    "I": [("V", "R"), ("P", "V"), ("P", "R")],
    "R": [("V", "I"), ("P", "I"), ("P", "V")],
    "P": [("V", "I"), ("I", "R"), ("V", "R")],
}

# Labels for input fields per solve_for mode
_INPUT_LABELS = {
    "V": {"pair": ("I", "R"), "labels": ("Current (A)", "Resistance (\u03a9)")},
    "I": {"pair": ("V", "R"), "labels": ("Voltage (V)", "Resistance (\u03a9)")},
    "R": {"pair": ("V", "I"), "labels": ("Voltage (V)", "Current (A)")},
    "P": {"pair": ("V", "I"), "labels": ("Voltage (V)", "Current (A)")},
}

_UNIT_MAP = {"V": "V", "I": "A", "R": "\u03a9", "P": "W"}
_FULL_NAMES = {"V": "Voltage", "I": "Current", "R": "Resistance", "P": "Power"}


def _solve(solve_for, val1_name, val1, val2_name, val2):
    """Solve for the unknown given two known values."""
    knowns = {val1_name: val1, val2_name: val2}

    if solve_for == "V":
        if "I" in knowns and "R" in knowns:
            return knowns["I"] * knowns["R"]
        if "P" in knowns and "I" in knowns:
            return knowns["P"] / knowns["I"] if knowns["I"] != 0 else None
        if "P" in knowns and "R" in knowns:
            return math.sqrt(knowns["P"] * knowns["R"]) if knowns["R"] >= 0 else None
    elif solve_for == "I":
        if "V" in knowns and "R" in knowns:
            return knowns["V"] / knowns["R"] if knowns["R"] != 0 else None
        if "P" in knowns and "V" in knowns:
            return knowns["P"] / knowns["V"] if knowns["V"] != 0 else None
        if "P" in knowns and "R" in knowns:
            return math.sqrt(knowns["P"] / knowns["R"]) if knowns["R"] != 0 else None
    elif solve_for == "R":
        if "V" in knowns and "I" in knowns:
            return knowns["V"] / knowns["I"] if knowns["I"] != 0 else None
        if "P" in knowns and "I" in knowns:
            return knowns["P"] / (knowns["I"] ** 2) if knowns["I"] != 0 else None
        if "P" in knowns and "V" in knowns:
            return (knowns["V"] ** 2) / knowns["P"] if knowns["P"] != 0 else None
    elif solve_for == "P":
        if "V" in knowns and "I" in knowns:
            return knowns["V"] * knowns["I"]
        if "I" in knowns and "R" in knowns:
            return (knowns["I"] ** 2) * knowns["R"]
        if "V" in knowns and "R" in knowns:
            return (knowns["V"] ** 2) / knowns["R"] if knowns["R"] != 0 else None
    return None


def _format_result(value, unit):
    """Format with SI prefix."""
    if value is None:
        return "ERR"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.4g} M{unit}"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.4g} k{unit}"
    if abs(value) < 0.001 and value != 0:
        return f"{value * 1000:.4g} m{unit}"
    return f"{value:.4g} {unit}"


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
            "heading":  _load_font("dejavusans", 20, bold=True),
            "body":     _load_font("dejavusans", 16),
            "small":    _load_font("dejavusans", 13),
            "mono_lg":  _load_font("dejavusansmono", 22, bold=True),
            "mono":     _load_font("dejavusansmono", 14),
            "tiny":     _load_font("dejavusansmono", 10),
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


# ---------------------------------------------------------------------------
# ScreenOhmCalc
# ---------------------------------------------------------------------------

class ScreenOhmCalc:
    """Ohm's Law calculator: solve for V, I, R, or P."""

    def __init__(self, surface) -> None:
        if hasattr(surface, "_surface"):
            self._ui      = surface
            self._surface = surface._surface
        else:
            self._ui      = None
            self._surface = surface

        self.solve_for: str = "V"
        self.input1_buf: str = ""
        self.input2_buf: str = ""
        self.active_input: int = 1   # 1 or 2
        self.result: float | None = None
        self.result_str: str = "READY"

        self._mode_rects: list[tuple[str, pygame.Rect]] = []
        self._input1_rect = pygame.Rect(0, 0, 0, 0)
        self._input2_rect = pygame.Rect(0, 0, 0, 0)
        self._keypad_rects: list[tuple[str, pygame.Rect]] = []
        self._pressed_key: str | None = None

        if not pygame.font.get_init():
            pygame.font.init()

    # ------------------------------------------------------------------
    # Screen interface
    # ------------------------------------------------------------------

    def update(self, dt=None, measurement=None):
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
            self._do_del()
        elif event.key == pygame.K_RETURN:
            self._do_enter()
        elif event.key == pygame.K_TAB:
            self.active_input = 2 if self.active_input == 1 else 1
        elif event.unicode.isdigit():
            self._append_char(event.unicode)
        elif event.unicode == ".":
            self._append_char(".")

    def handle_touch(self, x, y):
        # Mode buttons
        for mode, rect in self._mode_rects:
            if rect.collidepoint(x, y):
                self.solve_for = mode
                self.input1_buf = ""
                self.input2_buf = ""
                self.result = None
                self.result_str = "READY"
                self.active_input = 1
                return

        # Input field taps
        if self._input1_rect.collidepoint(x, y):
            self.active_input = 1
            return
        if self._input2_rect.collidepoint(x, y):
            self.active_input = 2
            return

        # Keypad
        for label, rect in self._keypad_rects:
            if rect.collidepoint(x, y):
                self._pressed_key = label
                self._handle_key(label)
                return

    def on_enter(self):
        pass

    def on_exit(self):
        self._pressed_key = None

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def _handle_key(self, label):
        if label in "0123456789":
            self._append_char(label)
        elif label == ".":
            self._append_char(".")
        elif label == "DEL":
            self._do_del()
        elif label == "ENT":
            self._do_enter()
        elif label == "CLR":
            self.input1_buf = ""
            self.input2_buf = ""
            self.result = None
            self.result_str = "READY"
            self.active_input = 1

    def _append_char(self, ch):
        buf = self.input1_buf if self.active_input == 1 else self.input2_buf
        if ch == "." and "." in buf:
            return
        if len(buf) >= 10:
            return
        buf += ch
        if self.active_input == 1:
            self.input1_buf = buf
        else:
            self.input2_buf = buf

    def _do_del(self):
        if self.active_input == 1:
            self.input1_buf = self.input1_buf[:-1]
        else:
            self.input2_buf = self.input2_buf[:-1]

    def _do_enter(self):
        cfg = _INPUT_LABELS[self.solve_for]
        n1, n2 = cfg["pair"]
        try:
            v1 = float(self.input1_buf) if self.input1_buf else None
            v2 = float(self.input2_buf) if self.input2_buf else None
        except ValueError:
            self.result_str = "ERR"
            return

        if v1 is None or v2 is None:
            self.result_str = "ENTER VALUES"
            return

        self.result = _solve(self.solve_for, n1, v1, n2, v2)
        unit = _UNIT_MAP[self.solve_for]
        self.result_str = _format_result(self.result, unit)

    # ------------------------------------------------------------------
    # Left panel drawing
    # ------------------------------------------------------------------

    def _draw_left_panel(self, target, fnt):
        self._draw_mode_buttons(target, fnt)
        self._draw_lcd(target, fnt)
        self._draw_inputs(target, fnt)

    def _draw_mode_buttons(self, target, fnt):
        self._mode_rects = []
        modes = ["V", "I", "R", "P"]
        start_x = LEFT_X
        for i, mode in enumerate(modes):
            x = start_x + i * (MODE_BTN_W + MODE_BTN_GAP)
            rect = pygame.Rect(x, MODE_BTN_Y, MODE_BTN_W, MODE_BTN_H)
            self._mode_rects.append((mode, rect))

            if mode == self.solve_for:
                # Active: black bg, white text
                _draw_hard_shadow_rect(target, rect, BORDER_COLOR, radius=6)
                _draw_text(target, mode, fnt["body"], (255, 255, 255),
                           rect.centerx, rect.centery, anchor="center")
            else:
                # Inactive: white bg, colored text
                _draw_hard_shadow_rect(target, rect, CARD_BG, radius=6)
                _draw_text(target, mode, fnt["body"], _MODE_COLORS[mode],
                           rect.centerx, rect.centery, anchor="center")

    def _draw_lcd(self, target, fnt):
        lcd_rect = pygame.Rect(LCD_X, LCD_Y, LCD_W, LCD_H)

        # Shadow + dark bg + border
        shadow = lcd_rect.move(2, 2)
        pygame.draw.rect(target, SHADOW_COLOR, shadow, border_radius=6)
        pygame.draw.rect(target, LCD_BG, lcd_rect, border_radius=6)
        pygame.draw.rect(target, BORDER_COLOR, lcd_rect, width=2, border_radius=6)

        # Status dot
        dot_x = LCD_X + 10
        dot_y = LCD_Y + 12
        dot_color = LCD_GREEN if self.result is not None else LCD_DIM
        pygame.draw.circle(target, dot_color, (dot_x, dot_y), 3)
        status = "RESULT" if self.result is not None else "READY"
        _draw_text(target, status, fnt["tiny"], LCD_DIM,
                   dot_x + 8, dot_y, anchor="midleft")

        # Solve-for label
        name = _FULL_NAMES[self.solve_for]
        _draw_text(target, f"Solve: {name}", fnt["tiny"],
                   _MODE_COLORS[self.solve_for],
                   LCD_X + LCD_W - 8, dot_y, anchor="midright")

        # Main result text
        _draw_text(target, self.result_str, fnt["mono_lg"], LCD_GREEN,
                   lcd_rect.centerx, lcd_rect.centery + 8, anchor="center")

        # Glass glare effect (subtle line near top)
        glare_y = LCD_Y + 6
        glare_color = (40, 40, 40)
        pygame.draw.line(target, glare_color,
                         (LCD_X + 8, glare_y), (LCD_X + LCD_W - 8, glare_y), 1)

    def _draw_inputs(self, target, fnt):
        cfg = _INPUT_LABELS[self.solve_for]
        labels = cfg["labels"]
        bufs = [self.input1_buf, self.input2_buf]
        ys = [INPUT1_Y, INPUT2_Y]

        for i in range(2):
            label = labels[i]
            buf = bufs[i]
            y = ys[i]

            # Label
            _draw_text(target, label, fnt["small"], TEXT_MUTED,
                       LEFT_X, y - 12, anchor="topleft")

            # Input box
            rect = pygame.Rect(LEFT_X, y, INPUT_W, INPUT_H)
            if i == 0:
                self._input1_rect = rect
            else:
                self._input2_rect = rect

            is_active = (self.active_input == i + 1)
            border_c = _MODE_COLORS[self.solve_for] if is_active else BORDER_COLOR
            _draw_hard_shadow_rect(target, rect, CARD_BG, radius=6)
            if is_active:
                pygame.draw.rect(target, border_c, rect, width=2, border_radius=6)

            # Value text
            display = buf if buf else "\u2014"
            color = TEXT_COLOR if buf else TEXT_MUTED
            _draw_text(target, display, fnt["mono"], color,
                       rect.right - 10, rect.centery, anchor="midright")

    # ------------------------------------------------------------------
    # Right panel: keypad
    # ------------------------------------------------------------------

    def _draw_right_panel(self, target, fnt):
        self._keypad_rects = []

        # Build the grid, handling ENT spanning 2 rows
        for row_idx in range(4):
            for col_idx in range(4):
                label = _KEYPAD_LAYOUT[row_idx][col_idx]
                if label == "":
                    continue

                x = _KP_LEFT + col_idx * (_KP_BTN_W + _KP_GAP)
                y = _KP_TOP  + row_idx * (_KP_BTN_H + _KP_GAP)

                # ENT button spans 2 rows
                if label == "ENT":
                    h = _KP_BTN_H * 2 + _KP_GAP
                else:
                    h = _KP_BTN_H

                rect = pygame.Rect(x, y, _KP_BTN_W, h)
                self._keypad_rects.append((label, rect))

                # Styling
                if label == "DEL":
                    bg, fg = _KP_DEL_BG, (255, 255, 255)
                elif label == "ENT":
                    bg, fg = _KP_ENT_BG, TEXT_COLOR
                elif label == "CLR":
                    bg, fg = _KP_CLR_BG, TEXT_COLOR
                else:
                    bg, fg = _KP_DIGIT_BG, TEXT_COLOR

                if self._pressed_key == label:
                    bg = tuple(max(0, int(c * 0.65)) for c in bg)

                _draw_hard_shadow_rect(target, rect, bg, radius=6)
                _draw_text(target, label, fnt["body"], fg,
                           rect.centerx, rect.centery, anchor="center")


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    pygame.init()
    win = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Ohm Calc - preview")
    clock = pygame.time.Clock()

    calc = ScreenOhmCalc(win)

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                calc.handle_touch(event.pos[0], event.pos[1])
            calc.handle_event(event)
        calc.update(dt)
        calc.draw(win)
        pygame.display.flip()

    pygame.quit()
    sys.exit()
