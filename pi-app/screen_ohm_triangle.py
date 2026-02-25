from __future__ import annotations

"""
Resistor Station - Ohm's Law Triangle Screen

Interactive V=IR triangle with brutalist light theme.
Left: equilateral triangle with V / I / R zones.
Right: formula card + slider + insight text.
"""

import math
import pygame

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

SCREEN_W   = 480
SCREEN_H   = 320
NAV_H      = 48
STATUS_H   = 24
CONTENT_Y  = STATUS_H
CONTENT_H  = SCREEN_H - NAV_H - STATUS_H   # 248 px

CONTENT_AREA = pygame.Rect(0, CONTENT_Y, SCREEN_W, CONTENT_H)

# Triangle vertices (shifted down by STATUS_H)
TRI_APEX  = (122, CONTENT_Y + 10)
TRI_LEFT  = (20,  CONTENT_Y + 225)
TRI_RIGHT = (224, CONTENT_Y + 225)

_TRI_MID_Y = (TRI_APEX[1] + TRI_LEFT[1]) // 2

_V_LABEL = (122, CONTENT_Y + 75)
_I_LABEL = (62,  CONTENT_Y + 180)
_R_LABEL = (182, CONTENT_Y + 180)

# Right panel
_RPANEL_X  = 250
_RPANEL_W  = 220
_CARD_Y    = CONTENT_Y + 6
_CARD_H    = 120
_LIVE_Y    = CONTENT_Y + 136
_SLIDER_Y  = CONTENT_Y + 160
_SLIDER_X  = 255
_SLIDER_W  = 210
_SLIDER_H  = 8
_INSIGHT_Y = CONTENT_Y + 205

_I_MIN = 0.0001
_I_MAX = 0.01
_V_MIN = 0.1
_V_MAX = 30.0

# ---------------------------------------------------------------------------
# Colour palette — brutalist light theme
# ---------------------------------------------------------------------------

BG_COLOR     = (247, 245, 240)
TEXT_COLOR    = (24,  24,  27)
MUTED_COLOR  = (113, 113, 122)
CARD_BG      = (255, 255, 255)
BORDER_COLOR = (0,   0,   0)
SHADOW_COLOR = (0,   0,   0)
GRID_COLOR   = (235, 233, 228)
SCREW_COLOR  = (161, 161, 170)

VOLTAGE_COLOR = (239, 68,  68)
CURRENT_COLOR = (59,  130, 246)
RESIST_COLOR  = (251, 146, 60)    # orange for resistance

# Triangle zone fill colours (unselected / selected)
_V_FILL_OFF = (254, 226, 226)   # light red
_V_FILL_ON  = (254, 202, 202)   # stronger red
_I_FILL_OFF = (219, 234, 254)   # light blue
_I_FILL_ON  = (191, 219, 254)   # stronger blue
_R_FILL_OFF = (254, 235, 213)   # light orange
_R_FILL_ON  = (253, 216, 180)   # stronger orange

_VAR_ACCENT = {"V": VOLTAGE_COLOR, "I": CURRENT_COLOR, "R": RESIST_COLOR}

_INSIGHTS = {
    "V": "V = I \u00d7 R  \u00b7  More R \u2192 More V",
    "I": "I = V / R  \u00b7  More R \u2192 Less I",
    "R": "R = V / I  \u00b7  More V \u2192 More R",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_r(ohms):
    if ohms >= 1_000_000:
        return f"{ohms / 1_000_000:.2g}M\u03a9"
    if ohms >= 1_000:
        return f"{ohms / 1_000:.2g}k\u03a9"
    return f"{ohms:.0f}\u03a9"


def _clamp(val, lo, hi):
    return max(lo, min(hi, val))


def _point_in_triangle(px, py, ax, ay, bx, by, cx, cy):
    def _sign(p1x, p1y, p2x, p2y, p3x, p3y):
        return (p1x - p3x) * (p2y - p3y) - (p2x - p3x) * (p1y - p3y)
    d1 = _sign(px, py, ax, ay, bx, by)
    d2 = _sign(px, py, bx, by, cx, cy)
    d3 = _sign(px, py, cx, cy, ax, ay)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


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
# ScreenOhmTriangle
# ---------------------------------------------------------------------------

class ScreenOhmTriangle:
    """Interactive Ohm's Law triangle screen with brutalist light theme."""

    def __init__(self, surface) -> None:
        if hasattr(surface, "_surface"):
            self._surface = surface._surface
            self._ui      = surface
        else:
            self._surface = surface
            self._ui      = None

        if not pygame.font.get_init():
            pygame.font.init()

        self.selected    : str   = "R"
        self.voltage     : float = 3.3
        self.current     : float = 0.001
        self.resistance  : float = 3300.0
        self.slider_value: float = 0.5
        self.measurement         = None
        self._live_r     : float | None = None

        self._v_rect = pygame.Rect(TRI_APEX[0] - 30, TRI_APEX[1], 60, 90)
        self._i_rect = pygame.Rect(TRI_LEFT[0], _TRI_MID_Y, 110, 100)
        self._r_rect = pygame.Rect(TRI_APEX[0], _TRI_MID_Y, 110, 100)
        self._slider_rect = pygame.Rect(_SLIDER_X, _SLIDER_Y - 14,
                                        _SLIDER_W, 28)

        if self._ui is not None and hasattr(self._ui, "heading_font"):
            self._heading = self._ui.heading_font
            self._body    = self._ui.body_font
            self._mono    = self._ui.mono_font
        else:
            self._heading = self._load_font("dejavusans", 22, bold=True)
            self._body    = self._load_font("dejavusans", 16)
            self._mono    = self._load_font("dejavusansmono", 14)

        self._small = self._load_font("dejavusans", 13)

    @staticmethod
    def _load_font(family, size, bold=False):
        try:
            font = pygame.font.SysFont(family, size, bold=bold)
            if font is None:
                raise RuntimeError("SysFont returned None")
            return font
        except Exception:
            return pygame.font.SysFont(None, size, bold=bold)

    # ------------------------------------------------------------------
    # Public Ohm's Law solver
    # ------------------------------------------------------------------

    def calculate(self, solve_for, **kwargs):
        if solve_for == "V":
            return kwargs["I"] * kwargs["R"]
        elif solve_for == "I":
            r = kwargs["R"]
            if r == 0:
                raise ZeroDivisionError("Cannot divide by R=0 when solving for I")
            return kwargs["V"] / r
        elif solve_for == "R":
            i = kwargs["I"]
            if i == 0:
                raise ZeroDivisionError("Cannot divide by I=0 when solving for R")
            return kwargs["V"] / i
        else:
            raise ValueError(
                f"Unknown variable to solve for: {solve_for!r}. "
                f"Expected 'V', 'I', or 'R'."
            )

    def _recalculate(self):
        if self.selected == "V":
            self.voltage = self.current * self.resistance
        elif self.selected == "I":
            if self.resistance != 0:
                self.current = self.voltage / self.resistance
        elif self.selected == "R":
            if self.current != 0:
                self.resistance = self.voltage / self.current

    # ------------------------------------------------------------------
    # Screen interface
    # ------------------------------------------------------------------

    def update(self, dt=None, measurement=None):
        if measurement is not None:
            status = measurement.get("status", "present")
            if status == "present":
                self._live_r = measurement["resistance"]
                if self.selected != "R":
                    self.resistance = self._live_r
                    self._recalculate()
            else:
                self._live_r = None

    def draw(self, surface=None):
        target = surface if surface is not None else self._surface
        target.fill(BG_COLOR)

        try:
            _draw_grid(target, CONTENT_AREA)
            self._draw_triangle(target)
            self._draw_right_panel(target)
            _draw_screws(target, CONTENT_AREA)
        except Exception:
            pass

    def handle_event(self, event):
        try:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                return self.handle_touch(event.pos[0], event.pos[1])
        except Exception:
            pass
        return False

    def on_enter(self):
        self.slider_value = 0.5
        self._recalculate()

    def on_exit(self):
        pass

    # ------------------------------------------------------------------
    # Touch handling
    # ------------------------------------------------------------------

    def handle_touch(self, x, y):
        ax, ay = TRI_APEX
        lx, ly = TRI_LEFT
        rx, ry = TRI_RIGHT

        if _point_in_triangle(x, y, ax, ay, lx, ly, rx, ry):
            if y < _TRI_MID_Y:
                self.selected = "V"
            else:
                mid_x = (lx + rx) // 2
                if x < mid_x:
                    self.selected = "I"
                else:
                    self.selected = "R"
            self._recalculate()
            return True

        if self._slider_rect.collidepoint(x, y):
            raw = (x - _SLIDER_X) / _SLIDER_W
            self.slider_value = _clamp(raw, 0.0, 1.0)
            self._apply_slider()
            return True

        return False

    def _apply_slider(self):
        t = self.slider_value
        if self.selected == "V":
            self.current = _I_MIN + t * (_I_MAX - _I_MIN)
        else:
            self.voltage = _V_MIN + t * (_V_MAX - _V_MIN)
        self._recalculate()

    # ------------------------------------------------------------------
    # Drawing — triangle
    # ------------------------------------------------------------------

    def _draw_triangle(self, target):
        ax, ay = TRI_APEX
        lx, ly = TRI_LEFT
        rx, ry = TRI_RIGHT
        mid_y  = _TRI_MID_Y
        mid_x  = (lx + rx) // 2

        t_left  = (mid_y - ay) / (ly - ay)
        edge_lx = int(ax + t_left * (lx - ax))
        t_right = (mid_y - ay) / (ry - ay)
        edge_rx = int(ax + t_right * (rx - ax))

        v_color = _V_FILL_ON if self.selected == "V" else _V_FILL_OFF
        i_color = _I_FILL_ON if self.selected == "I" else _I_FILL_OFF
        r_color = _R_FILL_ON if self.selected == "R" else _R_FILL_OFF

        pygame.draw.polygon(target, v_color,
                            [(ax, ay), (edge_lx, mid_y), (edge_rx, mid_y)])
        pygame.draw.polygon(target, i_color,
                            [(edge_lx, mid_y), (lx, ly), (mid_x, ly)])
        pygame.draw.polygon(target, r_color,
                            [(edge_rx, mid_y), (mid_x, ly), (rx, ry)])

        # Dividing line
        pygame.draw.line(target, MUTED_COLOR,
                         (edge_lx, mid_y), (edge_rx, mid_y), 1)

        # 2px black outline
        pygame.draw.polygon(target, BORDER_COLOR,
                            [(ax, ay), (lx, ly), (rx, ry)], 2)

        self._draw_var_label(target, "V", _V_LABEL)
        self._draw_var_label(target, "I", _I_LABEL)
        self._draw_var_label(target, "R", _R_LABEL)

        self._v_rect = pygame.Rect(
            min(ax, edge_lx) - 4, ay - 4,
            abs(edge_rx - min(ax, edge_lx)) + 8, mid_y - ay + 8)
        self._i_rect = pygame.Rect(lx - 4, mid_y - 4,
                                   mid_x - lx + 8, ly - mid_y + 8)
        self._r_rect = pygame.Rect(mid_x - 4, mid_y - 4,
                                   rx - mid_x + 8, ry - mid_y + 8)

    def _draw_var_label(self, target, var, centre):
        cx, cy = centre
        if var == self.selected:
            font   = self._heading
            colour = _VAR_ACCENT[var]
            surf   = font.render(var, True, colour)
            rect   = surf.get_rect(center=(cx, cy))
            target.blit(surf, rect)
        else:
            colour = MUTED_COLOR
            surf = self._body.render(var, True, colour)
            rect = surf.get_rect(center=(cx, cy - 8))
            target.blit(surf, rect)
            val_text = self._value_str(var)
            vs = self._small.render(val_text, True, colour)
            vr = vs.get_rect(center=(cx, cy + 10))
            target.blit(vs, vr)

    def _value_str(self, var):
        if var == "V":
            return f"{self.voltage:.2f}V"
        if var == "I":
            return f"{self.current * 1000:.2f}mA"
        return _fmt_r(self.resistance)

    # ------------------------------------------------------------------
    # Drawing — right panel
    # ------------------------------------------------------------------

    def _draw_right_panel(self, target):
        self._draw_formula_card(target)
        self._draw_live_indicator(target)
        self._draw_slider(target)
        self._draw_insight(target)

    def _draw_formula_card(self, target):
        card_rect = pygame.Rect(_RPANEL_X, _CARD_Y, _RPANEL_W, _CARD_H)
        _draw_hard_shadow_rect(target, card_rect, CARD_BG)

        s = self.selected
        accent = _VAR_ACCENT[s]

        title_surf = self._heading.render(f"Solving for {s}", True, accent)
        target.blit(title_surf, title_surf.get_rect(
            topleft=(_RPANEL_X + 10, _CARD_Y + 8)))

        formula = {"V": "V = I \u00d7 R", "I": "I = V / R", "R": "R = V / I"}[s]
        f_surf = self._body.render(formula, True, TEXT_COLOR)
        target.blit(f_surf, f_surf.get_rect(
            topleft=(_RPANEL_X + 10, _CARD_Y + 34)))

        nums = self._numbers_line()
        n_surf = self._mono.render(nums, True, MUTED_COLOR)
        target.blit(n_surf, n_surf.get_rect(
            topleft=(_RPANEL_X + 10, _CARD_Y + 56)))

        result = self._result_str()
        r_surf = self._heading.render(result, True, accent)
        target.blit(r_surf, r_surf.get_rect(
            topleft=(_RPANEL_X + 10, _CARD_Y + 80)))

    def _numbers_line(self):
        s = self.selected
        if s == "V":
            return f"= {self.current * 1000:.2f}mA \u00d7 {_fmt_r(self.resistance)}"
        if s == "I":
            return f"= {self.voltage:.2f}V / {_fmt_r(self.resistance)}"
        return f"= {self.voltage:.2f}V / {self.current * 1000:.2f}mA"

    def _result_str(self):
        s = self.selected
        if s == "V":
            return f"= {self.voltage:.3g}V"
        if s == "I":
            return f"= {self.current * 1000:.3g}mA"
        return f"= {_fmt_r(self.resistance)}"

    def _draw_live_indicator(self, target):
        dot_x = _RPANEL_X + 6
        dot_y = _LIVE_Y + 7

        if self._live_r is not None:
            colour = (34, 197, 94)   # green-500
            label  = f"Live: R = {_fmt_r(self._live_r)}"
        else:
            colour = MUTED_COLOR
            label  = "No resistor"

        pygame.draw.circle(target, colour, (dot_x, dot_y), 5)
        l_surf = self._body.render(label, True, colour)
        target.blit(l_surf, l_surf.get_rect(midleft=(dot_x + 10, dot_y)))

    def _draw_slider(self, target):
        track_rect = pygame.Rect(_SLIDER_X, _SLIDER_Y, _SLIDER_W, _SLIDER_H)
        pygame.draw.rect(target, (220, 220, 220), track_rect, border_radius=4)
        pygame.draw.rect(target, BORDER_COLOR, track_rect, width=1, border_radius=4)

        fill_w = int(self.slider_value * _SLIDER_W)
        if fill_w > 0:
            fill_rect = pygame.Rect(_SLIDER_X, _SLIDER_Y, fill_w, _SLIDER_H)
            pygame.draw.rect(target, VOLTAGE_COLOR, fill_rect, border_radius=4)

        thumb_x = _SLIDER_X + int(self.slider_value * _SLIDER_W)
        pygame.draw.circle(target, (255, 255, 255),
                           (thumb_x, _SLIDER_Y + _SLIDER_H // 2), 10)
        pygame.draw.circle(target, BORDER_COLOR,
                           (thumb_x, _SLIDER_Y + _SLIDER_H // 2), 10, 2)

        self._slider_rect = pygame.Rect(_SLIDER_X, _SLIDER_Y - 14,
                                        _SLIDER_W, 28)

        lbl = self._slider_label()
        l_surf = self._small.render(lbl, True, MUTED_COLOR)
        target.blit(l_surf, l_surf.get_rect(
            midtop=(_SLIDER_X + _SLIDER_W // 2, _SLIDER_Y + _SLIDER_H + 14)))

    def _slider_label(self):
        if self.selected == "V":
            return f"Current: {self.current * 1000:.2f} mA"
        return f"Voltage: {self.voltage:.2f} V"

    def _draw_insight(self, target):
        text  = _INSIGHTS[self.selected]
        surf  = self._small.render(text, True, MUTED_COLOR)
        rect  = surf.get_rect(topleft=(_RPANEL_X, _INSIGHT_Y))
        target.blit(surf, rect)

        detail = (
            f"{self.voltage:.2f}V   {self.current * 1000:.2f}mA   "
            f"{_fmt_r(self.resistance)}"
        )
        d_surf = self._small.render(detail, True, MUTED_COLOR)
        target.blit(d_surf, d_surf.get_rect(
            topleft=(_RPANEL_X, _INSIGHT_Y + 18)))


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    pygame.init()
    win = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Ohm Triangle - preview")
    clock = pygame.time.Clock()

    ohm = ScreenOhmTriangle(win)
    ohm.on_enter()

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            ohm.handle_event(event)
        ohm.update(dt)
        ohm.draw(win)
        pygame.display.flip()

    pygame.quit()
    sys.exit()
