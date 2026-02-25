from __future__ import annotations

"""
Resistor Station - Live Lab Screen

Main measurement dashboard with brutalist light theme.
Left panel: resistor illustration + value card.
Right panel: 3 stacked cards (Voltage, Current, Power).
"""

import math
import sys
import os

import pygame

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

SCREEN_W    = 480
SCREEN_H    = 320
NAV_H       = 48
STATUS_H    = 24
CONTENT_Y   = STATUS_H
CONTENT_H   = SCREEN_H - NAV_H - STATUS_H   # 248 px

CONTENT_AREA = pygame.Rect(0, CONTENT_Y, SCREEN_W, CONTENT_H)

# Left panel (45% = ~216px)
LEFT_W    = 216
LEFT_X    = 0
# Right panel (55% = ~264px)
RIGHT_X   = LEFT_W
RIGHT_W   = SCREEN_W - LEFT_W

# Resistor illustration geometry (in left panel)
RES_CX    = LEFT_W // 2
RES_CY    = CONTENT_Y + 70
RES_W     = 190
RES_H     = 56
RES_X     = RES_CX - RES_W // 2
RES_Y     = RES_CY - RES_H // 2

_LEAD_PCT  = 0.15
_BODY_PCT  = 0.70
LEAD_W     = int(RES_W * _LEAD_PCT)
BODY_X     = RES_X + LEAD_W
BODY_W     = int(RES_W * _BODY_PCT)
BODY_Y     = RES_Y
BAND_W     = max(2, int(RES_W * 0.06))
BAND_CENTRES_PCT = [0.20, 0.40, 0.60, 0.80]

# Value card below resistor
VALUE_CARD_Y = RES_Y + RES_H + 16
VALUE_CARD_W = 180
VALUE_CARD_H = 60
VALUE_CARD_X = RES_CX - VALUE_CARD_W // 2

# Right panel cards
CARD_MARGIN = 8
CARD_X      = RIGHT_X + CARD_MARGIN
CARD_W      = RIGHT_W - CARD_MARGIN * 2
CARD_H      = 70
CARD_GAP    = 6
CARD_TOP    = CONTENT_Y + 8

# ---------------------------------------------------------------------------
# Colour palette — brutalist light theme
# ---------------------------------------------------------------------------

BG_COLOR       = (247, 245, 240)
CARD_BG        = (255, 255, 255)
TEXT_COLOR      = (24,  24,  27)
TEXT_MUTED      = (113, 113, 122)
BORDER_COLOR    = (0,   0,   0)
SHADOW_COLOR    = (0,   0,   0)
GRID_COLOR      = (235, 233, 228)
RESISTOR_TAN    = (232, 222, 194)
LEAD_COLOR      = (24,  24,  27)
GHOST_COLOR     = (161, 161, 170)
SCREW_COLOR     = (161, 161, 170)

VOLTAGE_COLOR   = (239, 68,  68)
CURRENT_COLOR   = (59,  130, 246)
POWER_COLOR     = (16,  185, 129)

_CARD_ACCENTS   = [VOLTAGE_COLOR, CURRENT_COLOR, POWER_COLOR]

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _load_font(family: str, size: int, bold: bool = False) -> pygame.font.Font:
    try:
        font = pygame.font.SysFont(family, size, bold=bold)
        if font is None:
            raise RuntimeError("SysFont returned None")
        return font
    except Exception:
        return pygame.font.SysFont(None, size, bold=bold)


def _ensure_fonts() -> dict:
    pygame.font.init()
    return {
        "heading": _load_font("dejavusans", 22, bold=True),
        "body":    _load_font("dejavusans", 16),
        "small":   _load_font("dejavusans", 13),
        "band":    _load_font("dejavusans", 12),
        "mono_lg": _load_font("dejavusansmono", 20, bold=True),
        "mono":    _load_font("dejavusansmono", 14),
        "tiny":    _load_font("dejavusansmono", 10),
    }


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


def _draw_resistor_body(surface, bands, ghost=False):
    """Draw resistor at fixed left-panel position."""
    cy = RES_CY
    lead_color = GHOST_COLOR if ghost else LEAD_COLOR
    pygame.draw.line(surface, lead_color, (RES_X, cy), (BODY_X, cy), 3)
    pygame.draw.line(surface, lead_color,
                     (BODY_X + BODY_W, cy), (RES_X + RES_W, cy), 3)

    body_rect = pygame.Rect(BODY_X, BODY_Y, BODY_W, RES_H)
    radius = max(2, RES_H // 3)

    if ghost:
        pygame.draw.rect(surface, GHOST_COLOR, body_rect,
                         width=2, border_radius=radius)
        return

    # Hard shadow + body
    shadow = body_rect.move(2, 2)
    pygame.draw.rect(surface, SHADOW_COLOR, shadow, border_radius=radius)
    pygame.draw.rect(surface, RESISTOR_TAN, body_rect, border_radius=radius)

    half_band = BAND_W // 2
    for i, band in enumerate(bands[:4]):
        rgb = band.get("rgb", (128, 128, 128))
        cx = int(BODY_X + BAND_CENTRES_PCT[i] * BODY_W)
        bx = cx - half_band
        bx = max(BODY_X, min(bx, BODY_X + BODY_W - BAND_W))
        band_rect = pygame.Rect(bx, BODY_Y, BAND_W, RES_H)
        band_rect = band_rect.clip(body_rect)
        if band_rect.width > 0 and band_rect.height > 0:
            pygame.draw.rect(surface, rgb, band_rect)

    pygame.draw.rect(surface, BORDER_COLOR, body_rect,
                     width=2, border_radius=radius)


def _format_resistance(measurement):
    if measurement and "value_string" in measurement:
        return measurement["value_string"]
    r = measurement.get("resistance", 0.0) if measurement else 0.0
    if r >= 1_000_000:
        scaled, unit = r / 1_000_000, "M\u03a9"
    elif r >= 1_000:
        scaled, unit = r / 1_000, "k\u03a9"
    else:
        scaled, unit = r, "\u03a9"
    formatted = f"{scaled:.1f}"
    if formatted.endswith(".0"):
        formatted = formatted[:-2]
    return f"{formatted}{unit}"


# ---------------------------------------------------------------------------
# ScreenLiveLab
# ---------------------------------------------------------------------------

class ScreenLiveLab:
    """Live measurement dashboard with left/right layout."""

    def __init__(self, surface, meter=None, serial=None) -> None:
        if hasattr(surface, "_surface"):
            self._ui       = surface
            self._surface  = surface._surface
            self._meter    = None
            self._serial   = None
        else:
            self._ui       = None
            self._surface  = surface
            self._meter    = meter
            self._serial   = serial

        self.measurement: dict | None = None
        self.bands: list[dict]        = []
        self._pulse: float    = 0.0
        self._pulse_dir: int  = 1
        self._fonts: dict | None = None

    def _get_fonts(self) -> dict:
        if self._fonts is None:
            self._fonts = _ensure_fonts()
        return self._fonts

    # ------------------------------------------------------------------
    # Screen interface
    # ------------------------------------------------------------------

    def update(self, dt: float = 0.0, measurement: dict | None = None,
               bands: list | None = None) -> None:
        if isinstance(dt, (int, float)):
            self._pulse += dt * 2.0 * self._pulse_dir
            if self._pulse >= 1.0:
                self._pulse = 1.0
                self._pulse_dir = -1
            elif self._pulse <= 0.0:
                self._pulse = 0.0
                self._pulse_dir = 1

        if measurement is not None:
            self.measurement = measurement
            if bands is not None:
                self.bands = bands
        elif self._meter is not None:
            resistance = self._meter.read()
            self._serial.send_measurement(resistance, self.bands)
            self.measurement = {
                "resistance": resistance,
                "voltage":    0.0,
                "current":    0.0,
                "status":     "present" if resistance and resistance > 0 else "absent",
            }

    def draw(self, surface=None) -> None:
        target = surface if surface is not None else self._surface
        target.fill(BG_COLOR)

        fonts = self._get_fonts()
        has_resistor = (
            self.measurement is not None
            and self.measurement.get("status", "present") == "present"
            and len(self.bands) >= 4
        )

        try:
            _draw_grid(target, CONTENT_AREA)
            self._draw_left_panel(target, fonts, has_resistor)
            self._draw_right_panel(target, fonts)
            _draw_screws(target, CONTENT_AREA)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Left panel: resistor + value card
    # ------------------------------------------------------------------

    def _draw_left_panel(self, surface, fonts, has_resistor):
        if has_resistor:
            _draw_resistor_body(surface, self.bands, ghost=False)

            # Value card below resistor
            card_rect = pygame.Rect(VALUE_CARD_X, VALUE_CARD_Y,
                                    VALUE_CARD_W, VALUE_CARD_H)
            _draw_hard_shadow_rect(surface, card_rect, CARD_BG)

            r_str = _format_resistance(self.measurement)
            _draw_text(surface, r_str, fonts["mono_lg"], TEXT_COLOR,
                       card_rect.centerx, card_rect.centery - 8,
                       anchor="center")

            tol_band = self.bands[3] if len(self.bands) >= 4 else {}
            tol_val  = tol_band.get("tolerance", 0.05)
            tol_pct  = int(round(tol_val * 100))
            _draw_text(surface, f"DETECTED \u00b1{tol_pct}%", fonts["tiny"],
                       TEXT_MUTED, card_rect.centerx, card_rect.centery + 12,
                       anchor="center")
        else:
            _draw_resistor_body(surface, [], ghost=True)

            t = self._pulse
            lo, hi = (161, 161, 170), (80, 80, 90)
            r = int(lo[0] + (hi[0] - lo[0]) * t)
            g = int(lo[1] + (hi[1] - lo[1]) * t)
            b = int(lo[2] + (hi[2] - lo[2]) * t)
            prompt_color = (r, g, b)
            _draw_text(surface, "Insert a resistor", fonts["body"],
                       prompt_color, RES_CX, VALUE_CARD_Y + 10,
                       anchor="midtop")

    # ------------------------------------------------------------------
    # Right panel: 3 stacked LabCards
    # ------------------------------------------------------------------

    def _draw_right_panel(self, surface, fonts):
        labels   = ["Voltage", "Current", "Power"]
        units    = ["V", "mA", "mW"]
        accents  = _CARD_ACCENTS

        m = self.measurement
        if m is not None:
            v = m.get("voltage", 0.0)
            i = m.get("current", 0.0)
            i_ma = i * 1000.0
            p_mw = v * i * 1000.0
            values = [f"{v:.3f}", f"{i_ma:.3f}", f"{p_mw:.2f}"]
        else:
            values = ["---", "---", "---"]

        for idx in range(3):
            cy = CARD_TOP + idx * (CARD_H + CARD_GAP)
            card_rect = pygame.Rect(CARD_X, cy, CARD_W, CARD_H)
            _draw_hard_shadow_rect(surface, card_rect, CARD_BG)

            # 4px colored accent strip at top
            accent = accents[idx]
            strip_rect = pygame.Rect(card_rect.x + 2, card_rect.y + 2,
                                     card_rect.width - 4, 4)
            pygame.draw.rect(surface, accent, strip_rect)

            # Colored dot indicator
            dot_x = card_rect.x + 14
            dot_y = card_rect.y + 20
            pygame.draw.circle(surface, accent, (dot_x, dot_y), 4)

            # Label
            _draw_text(surface, labels[idx], fonts["small"], TEXT_MUTED,
                       dot_x + 10, dot_y, anchor="midleft")

            # Large value + unit
            _draw_text(surface, values[idx], fonts["mono_lg"], TEXT_COLOR,
                       card_rect.x + 14, card_rect.y + 36, anchor="topleft")
            _draw_text(surface, units[idx], fonts["body"], accent,
                       card_rect.right - 14, card_rect.y + 38,
                       anchor="topright")

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        self._pulse     = 0.0
        self._pulse_dir = 1

    def on_exit(self) -> None:
        pass

    def handle_touch(self, x, y) -> None:
        pass

    def handle_event(self, event) -> None:
        pass


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _here)
    sys.path.insert(0, os.path.join(_here, "..", "shared"))

    from color_code import resistance_to_bands as _r2b

    pygame.init()
    window = pygame.display.set_mode((480, 320))
    pygame.display.set_caption("Live Lab - preview")
    clock = pygame.time.Clock()

    _bands = _r2b(4700.0)
    live_lab = ScreenLiveLab.__new__(ScreenLiveLab)
    live_lab._ui       = None
    live_lab._surface  = window
    live_lab._meter    = None
    live_lab._serial   = None
    live_lab.measurement = {
        "voltage":    3.300,
        "current":    0.000702,
        "resistance": 4700.0,
        "value_string": "4.7k\u03a9",
        "status":     "present",
    }
    live_lab.bands       = _bands
    live_lab._pulse      = 0.0
    live_lab._pulse_dir  = 1
    live_lab._fonts      = None

    _demo_timer = 0.0
    _show_resistor = True

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            live_lab.handle_event(event)

        _demo_timer += dt
        if _demo_timer >= 4.0:
            _demo_timer = 0.0
            _show_resistor = not _show_resistor
            if _show_resistor:
                live_lab.measurement["status"] = "present"
                live_lab.bands = _bands
            else:
                live_lab.measurement["status"] = "absent"
                live_lab.bands = []

        live_lab.update(dt)
        live_lab.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()
