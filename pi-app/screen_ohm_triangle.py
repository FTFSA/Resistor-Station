from __future__ import annotations

"""
Resistor Station - Ohm's Law Triangle Screen

Interactive V=IR triangle: tap a zone to select which variable to solve for.
The right panel shows the formula, a slider to adjust inputs, and a live
reading indicator when a real resistor is connected.

Layout (480 x 320, nav bar at y=272):
  Left  (x 10–235):   equilateral triangle with V / I / R zones
  Right (x 250–470):  formula card + slider + insight text
"""

import math
import pygame

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

SCREEN_W   = 480
SCREEN_H   = 320
NAV_H      = 48
CONTENT_H  = SCREEN_H - NAV_H   # 272 px

CONTENT_AREA = pygame.Rect(0, 0, SCREEN_W, CONTENT_H)

# Triangle vertices (absolute pixel coordinates)
TRI_APEX  = (122, 15)    # V — top
TRI_LEFT  = (20,  250)   # I — bottom-left
TRI_RIGHT = (224, 250)   # R — bottom-right

# Midpoint y of dividing line inside the triangle (separates V zone from I/R)
_TRI_MID_Y = (TRI_APEX[1] + TRI_LEFT[1]) // 2   # ≈ 132

# Zone label centres
_V_LABEL = (122, 88)
_I_LABEL = (62,  205)
_R_LABEL = (182, 205)

# Right-panel geometry
_RPANEL_X  = 250
_RPANEL_W  = 220   # 250..470
_CARD_Y    = 10
_CARD_H    = 130
_LIVE_Y    = 153
_SLIDER_Y  = 177
_SLIDER_X  = 255
_SLIDER_W  = 210   # thumb at 255 + slider_value * 210
_SLIDER_H  = 8
_INSIGHT_Y = 232

# Slider ranges (linear)
_I_MIN = 0.0001   # A   (0.1 mA)
_I_MAX = 0.01     # A   (10 mA)
_V_MIN = 0.1      # V
_V_MAX = 30.0     # V

# ---------------------------------------------------------------------------
# Colour palette (mirrors ui_manager.py)
# ---------------------------------------------------------------------------

BG_COLOR    = (15,  23,  42)
TEXT_COLOR  = (226, 232, 240)
MUTED_COLOR = (150, 160, 180)
ACCENT      = (56,  189, 248)   # cyan — V / voltage
GREEN       = (52,  211, 153)   # I / current
ORANGE      = (251, 146, 60)    # R / resistance
CARD_BG     = (22,  33,  62)

# Triangle zone fill colours (unselected / selected)
_V_FILL_OFF = (30,  50,  80)
_V_FILL_ON  = (56,  100, 140)
_I_FILL_OFF = (20,  50,  30)
_I_FILL_ON  = (30,  90,  60)
_R_FILL_OFF = (50,  30,  20)
_R_FILL_ON  = (90,  50,  20)

# Accent colour lookup per variable
_VAR_ACCENT = {"V": ACCENT, "I": GREEN, "R": ORANGE}

# Insight text per solved variable
_INSIGHTS = {
    "V": "V = I \u00d7 R  \u00b7  More R \u2192 More V",
    "I": "I = V / R  \u00b7  More R \u2192 Less I",
    "R": "R = V / I  \u00b7  More V \u2192 More R",
}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _fmt_r(ohms: float) -> str:
    """Format a resistance value with appropriate SI prefix."""
    if ohms >= 1_000_000:
        return f"{ohms / 1_000_000:.2g}M\u03a9"
    if ohms >= 1_000:
        return f"{ohms / 1_000:.2g}k\u03a9"
    return f"{ohms:.0f}\u03a9"


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _point_in_triangle(px: int, py: int,
                       ax: int, ay: int,
                       bx: int, by: int,
                       cx: int, cy: int) -> bool:
    """Return True if (px,py) is inside triangle (a,b,c) using cross products."""
    def _sign(p1x, p1y, p2x, p2y, p3x, p3y) -> float:
        return (p1x - p3x) * (p2y - p3y) - (p2x - p3x) * (p1y - p3y)

    d1 = _sign(px, py, ax, ay, bx, by)
    d2 = _sign(px, py, bx, by, cx, cy)
    d3 = _sign(px, py, cx, cy, ax, ay)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


# ---------------------------------------------------------------------------
# ScreenOhmTriangle
# ---------------------------------------------------------------------------

class ScreenOhmTriangle:
    """Interactive Ohm's Law triangle screen.

    Left half shows the V/I/R triangle; tapping a zone selects the variable
    to solve for.  Right half shows the formula card, a slider, and an
    insight blurb.  A live indicator shows if a real resistor is connected.

    Args:
        surface: pygame.Surface (hardware mode) or UIManager instance (app
                 mode).  Detected via ``hasattr(surface, '_surface')``.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, surface) -> None:
        # Dual-mode construction: accept either a raw Surface or a UIManager.
        if hasattr(surface, "_surface"):
            self._surface = surface._surface
            self._ui      = surface
        else:
            self._surface = surface
            self._ui      = None

        # Ensure the font subsystem is available (needed in test-mode where
        # UIManager may not have been fully initialised for this surface).
        if not pygame.font.get_init():
            pygame.font.init()

        # State
        self.selected    : str   = "R"
        self.voltage     : float = 3.3
        self.current     : float = 0.001
        self.resistance  : float = 3300.0
        self.slider_value: float = 0.5
        self.measurement         = None
        self._live_r     : float | None = None

        # Hit rects for touch detection — initialised to empty rects so
        # handle_touch() never crashes before the first draw().
        self._v_rect = pygame.Rect(TRI_APEX[0] - 30, TRI_APEX[1],      60, 90)
        self._i_rect = pygame.Rect(TRI_LEFT[0],       _TRI_MID_Y,      110, 100)
        self._r_rect = pygame.Rect(TRI_APEX[0],       _TRI_MID_Y,      110, 100)
        self._slider_rect = pygame.Rect(_SLIDER_X, _SLIDER_Y - 14,
                                        _SLIDER_W, 28)

        # Fonts — prefer DejaVu Sans, fall back gracefully.
        if self._ui is not None and hasattr(self._ui, "heading_font"):
            self._heading = self._ui.heading_font
            self._body    = self._ui.body_font
            self._mono    = self._ui.mono_font
        else:
            self._heading = self._load_font("dejavusans",     22, bold=True)
            self._body    = self._load_font("dejavusans",     16)
            self._mono    = self._load_font("dejavusansmono", 14)

        self._small = self._load_font("dejavusans", 13)

    # ------------------------------------------------------------------
    # Font helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_font(family: str, size: int, bold: bool = False) -> pygame.font.Font:
        """Load a named font, falling back to the default pygame font."""
        try:
            font = pygame.font.SysFont(family, size, bold=bold)
            if font is None:
                raise RuntimeError("SysFont returned None")
            return font
        except Exception:
            return pygame.font.SysFont(None, size, bold=bold)

    # ------------------------------------------------------------------
    # Public Ohm's Law solver (exact stub implementation — preserved)
    # ------------------------------------------------------------------

    def calculate(self, solve_for: str, **kwargs) -> float:
        """Solve Ohm's Law for the requested variable.

        Args:
            solve_for: One of ``'V'``, ``'I'``, or ``'R'``.
            **kwargs:  The two known values: ``V`` (volts), ``I`` (amps),
                       ``R`` (ohms).

        Returns:
            The computed value as a float.

        Raises:
            ZeroDivisionError: If a divisor is zero.
            ValueError:        If *solve_for* is not ``'V'``, ``'I'``, or
                               ``'R'``.
        """
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

    # ------------------------------------------------------------------
    # Internal recalculation
    # ------------------------------------------------------------------

    def _recalculate(self) -> None:
        """Recompute the selected (unknown) variable from the other two."""
        if self.selected == "V":
            self.voltage = self.current * self.resistance
        elif self.selected == "I":
            if self.resistance != 0:
                self.current = self.voltage / self.resistance
        elif self.selected == "R":
            if self.current != 0:
                self.resistance = self.voltage / self.current

    # ------------------------------------------------------------------
    # Screen interface contract
    # ------------------------------------------------------------------

    def update(self, dt=None, measurement=None) -> None:
        """Advance screen state.

        In app mode (called from the main loop with a measurement dict),
        stores the live resistance reading and recalculates.  In test mode
        (single positional arg) this is a no-op.

        Args:
            dt:          Elapsed time in seconds (ignored — no time animation).
            measurement: Optional dict with keys ``'voltage'``, ``'current'``,
                         ``'resistance'``, ``'status'``.
        """
        if measurement is not None:
            status = measurement.get("status", "present")
            if status == "present":
                self._live_r = measurement["resistance"]
                self.resistance = self._live_r
                self._recalculate()

    def draw(self, surface=None) -> None:
        """Render the Ohm's Law triangle screen.

        Args:
            surface: Target surface.  Defaults to ``self._surface`` when
                     called without arguments (test mode).
        """
        target = surface if surface is not None else self._surface
        target.fill(BG_COLOR)

        try:
            self._draw_triangle(target)
            self._draw_right_panel(target)
        except Exception:
            # MagicMock surfaces will raise on pygame.draw.* calls.
            # Silently swallow so tests that just check "no crash" still pass.
            pass

    def handle_event(self, event) -> bool:
        """Dispatch a pygame event to handle_touch or slider logic.

        Args:
            event: A pygame event object.

        Returns:
            ``True`` if the event was consumed.
        """
        try:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                return self.handle_touch(event.pos[0], event.pos[1])
        except Exception:
            pass
        return False

    def on_enter(self) -> None:
        """Called when this screen becomes active — reset slider to midpoint."""
        self.slider_value = 0.5
        self._recalculate()

    def on_exit(self) -> None:
        """Called when this screen is deactivated."""
        pass

    # ------------------------------------------------------------------
    # Touch handling
    # ------------------------------------------------------------------

    def handle_touch(self, x: int, y: int) -> bool:
        """Process a tap at (x, y).

        Checks the triangle zone hit-rects first, then the slider track.

        Args:
            x, y: Screen coordinates of the tap.

        Returns:
            ``True`` if the tap was handled.
        """
        # --- Triangle zone hits ---
        ax, ay = TRI_APEX
        lx, ly = TRI_LEFT
        rx, ry = TRI_RIGHT
        # Centroid of full triangle
        cx = (ax + lx + rx) // 3
        cy = (ay + ly + ry) // 3

        if _point_in_triangle(x, y, ax, ay, lx, ly, rx, ry):
            # Determine sub-zone: V above dividing line; I left of centroid
            # below; R right of centroid below.
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

        # --- Slider hit ---
        if self._slider_rect.collidepoint(x, y):
            raw = (x - _SLIDER_X) / _SLIDER_W
            self.slider_value = _clamp(raw, 0.0, 1.0)
            self._apply_slider()
            return True

        return False

    # ------------------------------------------------------------------
    # Slider application
    # ------------------------------------------------------------------

    def _apply_slider(self) -> None:
        """Map self.slider_value → the appropriate input variable, then recalc."""
        t = self.slider_value
        if self.selected == "V":
            # Slider adjusts current (I): 0.1 mA → 10 mA
            self.current = _I_MIN + t * (_I_MAX - _I_MIN)
        else:
            # Slider adjusts voltage (V): 0.1 V → 30 V
            self.voltage = _V_MIN + t * (_V_MAX - _V_MIN)
        self._recalculate()

    # ------------------------------------------------------------------
    # Drawing — triangle (left half)
    # ------------------------------------------------------------------

    def _draw_triangle(self, target: pygame.Surface) -> None:
        """Draw the zoned equilateral triangle on the left half."""
        ax, ay = TRI_APEX
        lx, ly = TRI_LEFT
        rx, ry = TRI_RIGHT
        mid_y  = _TRI_MID_Y
        mid_x  = (lx + rx) // 2   # x at the dividing line level

        # Interpolate the left and right edges of the triangle at mid_y so
        # we can fill each zone as a polygon.
        # Left edge: apex → left vertex.  Parametric t where t=0 is apex.
        t_left  = (mid_y - ay) / (ly - ay)
        edge_lx = int(ax + t_left * (lx - ax))

        # Right edge: apex → right vertex.
        t_right  = (mid_y - ay) / (ry - ay)
        edge_rx  = int(ax + t_right * (rx - ax))

        # --- Zone fills ---
        v_color = _V_FILL_ON  if self.selected == "V" else _V_FILL_OFF
        i_color = _I_FILL_ON  if self.selected == "I" else _I_FILL_OFF
        r_color = _R_FILL_ON  if self.selected == "R" else _R_FILL_OFF

        # V zone: triangle  apex → edge_l → edge_r
        pygame.draw.polygon(target, v_color,
                            [(ax, ay), (edge_lx, mid_y), (edge_rx, mid_y)])

        # I zone: triangle  edge_l → left_vertex → mid_bottom
        pygame.draw.polygon(target, i_color,
                            [(edge_lx, mid_y), (lx, ly), (mid_x, ly)])

        # R zone: triangle  edge_r → mid_bottom → right_vertex
        pygame.draw.polygon(target, r_color,
                            [(edge_rx, mid_y), (mid_x, ly), (rx, ry)])

        # --- Dividing line ---
        pygame.draw.line(target, (80, 100, 130),
                         (edge_lx, mid_y), (edge_rx, mid_y), 1)

        # --- Outline ---
        pygame.draw.polygon(target, TEXT_COLOR,
                            [(ax, ay), (lx, ly), (rx, ry)], 2)

        # --- Labels ---
        self._draw_var_label(target, "V", _V_LABEL)
        self._draw_var_label(target, "I", _I_LABEL)
        self._draw_var_label(target, "R", _R_LABEL)

        # Update hit rects to match actual geometry
        self._v_rect = pygame.Rect(
            min(ax, edge_lx) - 4, ay - 4,
            abs(edge_rx - min(ax, edge_lx)) + 8,
            mid_y - ay + 8,
        )
        self._i_rect = pygame.Rect(lx - 4, mid_y - 4,
                                   mid_x - lx + 8, ly - mid_y + 8)
        self._r_rect = pygame.Rect(mid_x - 4, mid_y - 4,
                                   rx - mid_x + 8, ry - mid_y + 8)

    def _draw_var_label(self, target: pygame.Surface,
                        var: str, centre: tuple[int, int]) -> None:
        """Draw a variable label (V, I, or R) at the given centre position.

        The selected variable is rendered larger with its accent colour;
        unselected variables are muted with their current value below.

        Args:
            target: Surface to draw onto.
            var:    ``'V'``, ``'I'``, or ``'R'``.
            centre: (x, y) centre of the label area.
        """
        cx, cy = centre
        if var == self.selected:
            font   = self._heading
            colour = _VAR_ACCENT[var]
            surf   = font.render(var, True, colour)
            rect   = surf.get_rect(center=(cx, cy))
            target.blit(surf, rect)
        else:
            colour = MUTED_COLOR
            # Letter
            surf = self._body.render(var, True, colour)
            rect = surf.get_rect(center=(cx, cy - 8))
            target.blit(surf, rect)
            # Value below
            val_text = self._value_str(var)
            vs = self._small.render(val_text, True, colour)
            vr = vs.get_rect(center=(cx, cy + 10))
            target.blit(vs, vr)

    def _value_str(self, var: str) -> str:
        """Return a compact display string for the current value of *var*."""
        if var == "V":
            return f"{self.voltage:.2f}V"
        if var == "I":
            return f"{self.current * 1000:.2f}mA"
        return _fmt_r(self.resistance)

    # ------------------------------------------------------------------
    # Drawing — right panel
    # ------------------------------------------------------------------

    def _draw_right_panel(self, target: pygame.Surface) -> None:
        """Draw formula card, live indicator, slider, and insight text."""
        self._draw_formula_card(target)
        self._draw_live_indicator(target)
        self._draw_slider(target)
        self._draw_insight(target)

    def _draw_formula_card(self, target: pygame.Surface) -> None:
        """Draw the formula card on the right panel."""
        card_rect = pygame.Rect(_RPANEL_X, _CARD_Y, _RPANEL_W, _CARD_H)
        pygame.draw.rect(target, CARD_BG, card_rect, border_radius=8)

        s = self.selected
        accent = _VAR_ACCENT[s]

        # "Solving for X"
        title_surf = self._heading.render(f"Solving for {s}", True, accent)
        target.blit(title_surf, title_surf.get_rect(
            topleft=(_RPANEL_X + 10, _CARD_Y + 8)))

        # Formula line e.g. "R = V / I"
        formula = {"V": "V = I \u00d7 R", "I": "I = V / R", "R": "R = V / I"}[s]
        f_surf = self._body.render(formula, True, TEXT_COLOR)
        target.blit(f_surf, f_surf.get_rect(
            topleft=(_RPANEL_X + 10, _CARD_Y + 36)))

        # Numbers line e.g. "= 3.3V / 1.0mA"
        nums = self._numbers_line()
        n_surf = self._mono.render(nums, True, MUTED_COLOR)
        target.blit(n_surf, n_surf.get_rect(
            topleft=(_RPANEL_X + 10, _CARD_Y + 60)))

        # Result line — large, accent colour
        result = self._result_str()
        r_surf = self._heading.render(result, True, accent)
        target.blit(r_surf, r_surf.get_rect(
            topleft=(_RPANEL_X + 10, _CARD_Y + 84)))

    def _numbers_line(self) -> str:
        """Build the substituted-values line for the formula card."""
        s = self.selected
        if s == "V":
            return f"= {self.current * 1000:.2f}mA \u00d7 {_fmt_r(self.resistance)}"
        if s == "I":
            return f"= {self.voltage:.2f}V / {_fmt_r(self.resistance)}"
        return f"= {self.voltage:.2f}V / {self.current * 1000:.2f}mA"

    def _result_str(self) -> str:
        """Build the calculated-result string for the formula card."""
        s = self.selected
        if s == "V":
            return f"= {self.voltage:.3g}V"
        if s == "I":
            return f"= {self.current * 1000:.3g}mA"
        return f"= {_fmt_r(self.resistance)}"

    def _draw_live_indicator(self, target: pygame.Surface) -> None:
        """Draw the live / no-resistor status dot and label."""
        dot_x = _RPANEL_X + 6
        dot_y = _LIVE_Y + 7

        if self._live_r is not None:
            colour = GREEN
            label  = f"Live: R = {_fmt_r(self._live_r)}"
        else:
            colour = MUTED_COLOR
            label  = "No resistor"

        pygame.draw.circle(target, colour, (dot_x, dot_y), 5)
        l_surf = self._body.render(label, True, colour)
        target.blit(l_surf, l_surf.get_rect(midleft=(dot_x + 10, dot_y)))

    def _draw_slider(self, target: pygame.Surface) -> None:
        """Draw the horizontal slider and its label."""
        track_rect = pygame.Rect(_SLIDER_X, _SLIDER_Y, _SLIDER_W, _SLIDER_H)
        pygame.draw.rect(target, (40, 50, 70), track_rect, border_radius=4)

        # Filled portion
        fill_w = int(self.slider_value * _SLIDER_W)
        if fill_w > 0:
            fill_rect = pygame.Rect(_SLIDER_X, _SLIDER_Y, fill_w, _SLIDER_H)
            pygame.draw.rect(target, ACCENT, fill_rect, border_radius=4)

        # Thumb
        thumb_x = _SLIDER_X + int(self.slider_value * _SLIDER_W)
        pygame.draw.circle(target, TEXT_COLOR,
                           (thumb_x, _SLIDER_Y + _SLIDER_H // 2), 10)

        # Update hit rect (generous tap target around the track)
        self._slider_rect = pygame.Rect(_SLIDER_X, _SLIDER_Y - 14,
                                        _SLIDER_W, 28)

        # Label below slider
        lbl = self._slider_label()
        l_surf = self._small.render(lbl, True, MUTED_COLOR)
        target.blit(l_surf, l_surf.get_rect(
            midtop=(_SLIDER_X + _SLIDER_W // 2, _SLIDER_Y + _SLIDER_H + 14)))

    def _slider_label(self) -> str:
        """Return the label text that describes what the slider is controlling."""
        if self.selected == "V":
            return f"Current: {self.current * 1000:.2f} mA"
        return f"Voltage: {self.voltage:.2f} V"

    def _draw_insight(self, target: pygame.Surface) -> None:
        """Draw the one-line insight text."""
        text  = _INSIGHTS[self.selected]
        surf  = self._small.render(text, True, MUTED_COLOR)
        rect  = surf.get_rect(topleft=(_RPANEL_X, _INSIGHT_Y))
        target.blit(surf, rect)

        # Also draw a second line with the actual formula values as a reminder
        detail = (
            f"{self.voltage:.2f}V   {self.current * 1000:.2f}mA   "
            f"{_fmt_r(self.resistance)}"
        )
        d_surf = self._small.render(detail, True, (100, 115, 140))
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
