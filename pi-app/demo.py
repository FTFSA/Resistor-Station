"""
Resistor Station — Standalone GUI Demo
=======================================
Runs on any machine with Pygame installed.  No hardware required.

Usage (from repo root):
    python3 pi-app/demo.py

Controls:
    LEFT / RIGHT arrow keys  — cycle through screens
    Mouse click              — tap nav bar tabs or interact with screen elements
    Escape / window-close    — quit

Layout:
    Content area  : y=0  .. y=280  (280 px tall)
    Nav bar       : y=280 .. y=320  (40 px tall)
"""

import math
import os
import sys

# ---------------------------------------------------------------------------
# Path setup — mirrors conftest.py so shared/ is importable
# ---------------------------------------------------------------------------
_DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.join(_DEMO_DIR, "..")
sys.path.insert(0, _DEMO_DIR)                          # pi-app/
sys.path.insert(0, os.path.join(_REPO_ROOT, "shared")) # shared/

import pygame

from color_code import snap_to_e24, resistance_to_bands, bands_to_rgb

# ---------------------------------------------------------------------------
# Global layout constants
# ---------------------------------------------------------------------------
SCREEN_W = 480
SCREEN_H = 320
NAV_H    = 40
CONTENT_H = SCREEN_H - NAV_H   # 280

NAV_RECT     = pygame.Rect(0, CONTENT_H, SCREEN_W, NAV_H)
CONTENT_RECT = pygame.Rect(0, 0, SCREEN_W, CONTENT_H)

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
BG_COLOR        = (26,  26,  46)   # #1a1a2e  — dark navy
CARD_COLOR      = (22,  33,  62)   # #16213e  — slightly lighter card
NAV_BG          = (15,  15,  26)   # #0f0f1a  — nav bar
ACCENT_ORANGE   = (255, 107,  0)   # #ff6b00  — active tab / highlights
COLOR_WHITE     = (255, 255, 255)
COLOR_GREY      = (170, 170, 170)  # #aaaaaa  — secondary text
COLOR_CYAN      = (  0, 212, 255)  # voltage accent
COLOR_GREEN     = (  0, 255, 136)  # current accent
COLOR_RED_ACCENT= (255,  68,  68)  # error / resistance accent
COLOR_BLUE_ZONE = ( 40,  80, 200)  # Ohm triangle V zone
COLOR_GREEN_ZONE= ( 20, 160,  60)  # Ohm triangle I zone
COLOR_RED_ZONE  = (180,  30,  30)  # Ohm triangle R zone
BTN_IDLE        = ( 38,  52,  86)  # calculator key idle
BTN_PRESS       = ( 80, 110, 180)  # calculator key pressed
RESISTOR_BODY   = (220, 185, 130)  # tan/beige body colour

NAV_TABS = ["Live Lab", "Ohm's Law", "Calculator"]

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _load_fonts():
    """Return a dict of (name -> pygame.Font) using monospace system font."""
    sizes = {
        "tiny":   12,
        "small":  14,
        "body":   16,
        "label":  18,
        "medium": 22,
        "large":  32,
        "xlarge": 48,
    }
    fonts = {}
    for name, pt in sizes.items():
        fonts[name] = pygame.font.SysFont("monospace", pt, bold=False)
    # Bold variants
    fonts["body_b"]   = pygame.font.SysFont("monospace", 16, bold=True)
    fonts["label_b"]  = pygame.font.SysFont("monospace", 18, bold=True)
    fonts["medium_b"] = pygame.font.SysFont("monospace", 22, bold=True)
    fonts["large_b"]  = pygame.font.SysFont("monospace", 32, bold=True)
    fonts["xlarge_b"] = pygame.font.SysFont("monospace", 48, bold=True)
    return fonts


# ---------------------------------------------------------------------------
# Drawing utilities
# ---------------------------------------------------------------------------

def draw_rounded_rect(surface, color, rect, radius=8, border=0, border_color=None):
    """Fill a rounded rectangle; optionally draw a border."""
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(surface, border_color, rect, width=border, border_radius=radius)


def draw_text(surface, text, font, color, pos, anchor="topleft"):
    """Blit rendered text anchored at pos using the given anchor string.

    anchor may be any pygame Rect attribute: 'topleft', 'center', 'midtop', etc.
    """
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    setattr(rect, anchor, pos)
    surface.blit(surf, rect)


def draw_resistor(surface, rect, band_colors_rgb, show_leads=True):
    """Draw a 4-band resistor inside *rect*.

    Args:
        surface:         pygame.Surface to draw onto.
        rect:            pygame.Rect defining the overall bounding box
                         (including lead wires).
        band_colors_rgb: List of 4 RGB tuples for the colour bands.
        show_leads:      Draw wire leads on each side.
    """
    body_margin_x = rect.width // 5    # leads take up 1/5 each side
    body_rect = pygame.Rect(
        rect.x + body_margin_x,
        rect.y,
        rect.width - 2 * body_margin_x,
        rect.height,
    )

    # Wire leads
    if show_leads:
        lead_y = rect.centery
        lead_color = (160, 160, 160)
        lead_thickness = max(2, rect.height // 10)
        pygame.draw.line(surface, lead_color,
                         (rect.x, lead_y),
                         (body_rect.x, lead_y),
                         lead_thickness)
        pygame.draw.line(surface, lead_color,
                         (body_rect.right, lead_y),
                         (rect.right, lead_y),
                         lead_thickness)

    # Body
    draw_rounded_rect(surface, RESISTOR_BODY, body_rect, radius=max(4, rect.height // 5))

    # Colour bands — 4 bands with proportional spacing
    n_bands = len(band_colors_rgb)
    band_w = max(4, body_rect.width // 10)
    # Distribute bands evenly across 80% of the body width, centred
    usable_w = int(body_rect.width * 0.80)
    spacing = (usable_w - n_bands * band_w) // (n_bands + 1)
    x_start = body_rect.x + (body_rect.width - usable_w) // 2

    band_inset = max(2, rect.height // 8)
    band_rect_h = body_rect.height - 2 * band_inset

    for i, rgb in enumerate(band_colors_rgb):
        bx = x_start + spacing * (i + 1) + band_w * i
        band_rect = pygame.Rect(bx, body_rect.y + band_inset, band_w, band_rect_h)
        pygame.draw.rect(surface, rgb, band_rect)


# ---------------------------------------------------------------------------
# Screen 1 — Live Lab
# ---------------------------------------------------------------------------

class LiveLabScreen:
    """Hardcoded 4 700 Ω fake measurement with resistor illustration and stat cards."""

    RESISTANCE   = 4700.0
    V_IN         = 3.3
    R_KNOWN      = 10_000.0
    BANDS        = ["yellow", "violet", "red", "gold"]

    def __init__(self, fonts):
        self._fonts = fonts
        self._voltage  = self.V_IN * self.RESISTANCE / (self.R_KNOWN + self.RESISTANCE)
        self._current_ma = (self.V_IN / (self.R_KNOWN + self.RESISTANCE)) * 1000.0
        self._band_rgbs = bands_to_rgb(self.BANDS)

    def handle_event(self, event):
        pass  # No interactive elements on this screen

    def update(self, dt):
        pass

    def draw(self, surface):
        surface.fill(BG_COLOR)
        fonts = self._fonts
        cx = SCREEN_W // 2

        # ---- Section 1: Resistance value readout (top ~90px) ----
        # Format with thin space for thousands separator: "4 700 Ω"
        r_text = "4 700 \u03a9"
        draw_text(surface, "Resistance", fonts["label"], COLOR_GREY, (cx, 10), anchor="midtop")
        draw_text(surface, r_text, fonts["xlarge_b"], COLOR_WHITE, (cx, 32), anchor="midtop")

        # ---- Section 2: Resistor illustration (middle ~100px) ----
        res_rect = pygame.Rect(60, 98, 360, 56)
        draw_resistor(surface, res_rect, self._band_rgbs, show_leads=True)

        # Band colour labels below the resistor
        band_names_display = ["Yellow", "Violet", "Red", "Gold"]
        body_margin_x = res_rect.width // 5
        body_x = res_rect.x + body_margin_x
        body_w = res_rect.width - 2 * body_margin_x
        band_w = max(4, body_w // 10)
        usable_w = int(body_w * 0.80)
        spacing = (usable_w - 4 * band_w) // 5
        x_start = body_x + (body_w - usable_w) // 2

        for i, name in enumerate(band_names_display):
            bx = x_start + spacing * (i + 1) + band_w * i + band_w // 2
            draw_text(surface, name, fonts["tiny"], COLOR_GREY, (bx, 162), anchor="midtop")

        # ---- Section 3: Stat cards (bottom row, y=185..265) ----
        card_y = 185
        card_h = 70
        pad = 8
        card_w = (SCREEN_W - 3 * pad) // 3  # ~154px each

        # Voltage card
        vcard = pygame.Rect(pad, card_y, card_w, card_h)
        draw_rounded_rect(surface, CARD_COLOR, vcard, radius=8)
        draw_text(surface, "Voltage", fonts["small"], COLOR_GREY,
                  (vcard.centerx, vcard.y + 8), anchor="midtop")
        draw_text(surface, f"{self._voltage:.2f}", fonts["medium_b"], COLOR_CYAN,
                  (vcard.centerx, vcard.y + 28), anchor="midtop")
        draw_text(surface, "V", fonts["small"], COLOR_GREY,
                  (vcard.centerx, vcard.y + 52), anchor="midtop")

        # Current card
        icard = pygame.Rect(pad * 2 + card_w, card_y, card_w, card_h)
        draw_rounded_rect(surface, CARD_COLOR, icard, radius=8)
        draw_text(surface, "Current", fonts["small"], COLOR_GREY,
                  (icard.centerx, icard.y + 8), anchor="midtop")
        draw_text(surface, f"{self._current_ma:.2f}", fonts["medium_b"], COLOR_GREEN,
                  (icard.centerx, icard.y + 28), anchor="midtop")
        draw_text(surface, "mA", fonts["small"], COLOR_GREY,
                  (icard.centerx, icard.y + 52), anchor="midtop")

        # Resistance card
        rcard = pygame.Rect(pad * 3 + card_w * 2, card_y, card_w, card_h)
        draw_rounded_rect(surface, CARD_COLOR, rcard, radius=8)
        draw_text(surface, "Resistance", fonts["tiny"], COLOR_GREY,
                  (rcard.centerx, rcard.y + 8), anchor="midtop")
        draw_text(surface, "4 700", fonts["medium_b"], ACCENT_ORANGE,
                  (rcard.centerx, rcard.y + 28), anchor="midtop")
        draw_text(surface, "\u03a9", fonts["small"], COLOR_GREY,
                  (rcard.centerx, rcard.y + 52), anchor="midtop")


# ---------------------------------------------------------------------------
# Screen 2 — Ohm's Law Triangle
# ---------------------------------------------------------------------------

def _point_in_triangle(px, py, ax, ay, bx, by, cx, cy):
    """Return True if (px, py) lies inside the triangle (a, b, c)."""
    def _sign(x1, y1, x2, y2, x3, y3):
        return (x1 - x3) * (y2 - y3) - (x2 - x3) * (y1 - y3)

    d1 = _sign(px, py, ax, ay, bx, by)
    d2 = _sign(px, py, bx, by, cx, cy)
    d3 = _sign(px, py, cx, cy, ax, ay)

    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


class OhmTriangleScreen:
    """Equilateral V/I/R triangle with tappable zones and formula display."""

    # Apex and base of the equilateral triangle (left-half content)
    _TRI_CX   = 120    # horizontal centre of the triangle
    _TRI_TOP  = 20     # y of apex
    _TRI_BOT  = 230    # y of base
    _TRI_HALF_W = 110  # half-width at the base

    def __init__(self, fonts):
        self._fonts  = fonts
        self._selected = "V"   # "V", "I", or "R"
        self._pressed  = None  # zone briefly highlighted on press

        # Compute vertices once
        cx = self._TRI_CX
        self._v_apex  = (cx,               self._TRI_TOP)
        self._i_base  = (cx - self._TRI_HALF_W, self._TRI_BOT)
        self._r_base  = (cx + self._TRI_HALF_W, self._TRI_BOT)

        # Centroid for zone-splitting midpoint
        self._centroid = (
            (self._v_apex[0] + self._i_base[0] + self._r_base[0]) // 3,
            (self._v_apex[1] + self._i_base[1] + self._r_base[1]) // 3,
        )

    # Sub-triangle vertices for each zone (apex → two outer verts → centroid)
    def _zone_v_pts(self):
        # Top zone: V apex, left-midpoint edge, right-midpoint edge, centroid
        return [self._v_apex, self._i_base, self._r_base, self._centroid]

    def _v_tri(self):
        """V zone: apex triangle."""
        g = self._centroid
        return (self._v_apex, self._i_base, self._r_base, g)

    def _zone_points(self, zone):
        """Return (p1, p2, p3) for point-in-triangle test of each zone."""
        g = self._centroid
        if zone == "V":
            return (self._v_apex, self._i_base, self._r_base)
        elif zone == "I":
            return (self._v_apex, self._i_base, g)
        else:  # "R"
            return (self._v_apex, self._r_base, g)

    def _hit_zone(self, pos):
        """Return 'V', 'I', 'R', or None for a click at pos."""
        px, py = pos
        # Test I and R first (smaller zones); V covers the remainder
        for zone in ("I", "R"):
            p1, p2, p3 = self._zone_points(zone)
            if _point_in_triangle(px, py, p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]):
                return zone
        # Test full triangle for V zone
        p1, p2, p3 = self._zone_points("V")
        if _point_in_triangle(px, py, p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]):
            return "V"
        return None

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            zone = self._hit_zone(event.pos)
            if zone:
                self._selected = zone
                self._pressed  = zone
        elif event.type == pygame.MOUSEBUTTONUP:
            self._pressed = None

    def update(self, dt):
        pass

    def _formula_text(self):
        if self._selected == "V":
            return "V = I \u00d7 R"
        elif self._selected == "I":
            return "I = V \u00f7 R"
        else:
            return "R = V \u00f7 I"

    def _zone_color(self, zone):
        base = {
            "V": COLOR_BLUE_ZONE,
            "I": COLOR_GREEN_ZONE,
            "R": COLOR_RED_ZONE,
        }[zone]
        if zone == self._selected:
            # Brighten the selected zone
            return tuple(min(255, int(c * 1.4)) for c in base)
        if zone == self._pressed:
            return tuple(min(255, int(c * 1.2)) for c in base)
        return base

    def draw(self, surface):
        surface.fill(BG_COLOR)
        fonts = self._fonts
        g     = self._centroid
        va    = self._v_apex
        ib    = self._i_base
        rb    = self._r_base

        # --- Draw three filled zone triangles ---
        # V zone: full top region (apex, i_base, r_base) split by centroid lines
        # We draw three sub-triangles: V-apex/centroid/i_base left, etc.
        # Simpler: draw full triangle then two "cut" triangles for I and R zones.
        #
        # Strategy:
        #   Full triangle = V zone colour (draw first)
        #   I zone = triangle (v_apex, i_base, centroid)
        #   R zone = triangle (v_apex, r_base, centroid)
        #   I-R base zone = triangle (i_base, r_base, centroid) — split horizontally

        # Full triangle background (V colour)
        pygame.draw.polygon(surface, self._zone_color("V"), [va, ib, rb])

        # I zone (left lower)
        pygame.draw.polygon(surface, self._zone_color("I"), [va, ib, g])

        # R zone (right lower)
        pygame.draw.polygon(surface, self._zone_color("R"), [va, rb, g])

        # Base zone splits I and R at bottom — draw it with a blend
        # (centroid to i_base to r_base)
        # We skip a separate colour here — the I and R zones naturally cover it.
        # But we must also fill the bottom strip between the base line and centroid:
        pygame.draw.polygon(surface, self._zone_color("I"), [ib, rb, g])
        # Overdraw the right half of that strip for R
        mid_base = ((ib[0] + rb[0]) // 2, (ib[1] + rb[1]) // 2)
        pygame.draw.polygon(surface, self._zone_color("R"), [mid_base, rb, g])

        # Outline
        pygame.draw.polygon(surface, COLOR_WHITE, [va, ib, rb], 2)
        # Dividing lines
        pygame.draw.line(surface, COLOR_WHITE, va, g, 1)
        pygame.draw.line(surface, COLOR_WHITE, ib, g, 1)
        pygame.draw.line(surface, COLOR_WHITE, rb, g, 1)

        # --- Zone labels ---
        v_label_pos = (va[0], va[1] + 14)
        i_label_pos = (ib[0] + 20, ib[1] - 28)
        r_label_pos = (rb[0] - 20, rb[1] - 28)

        for label, pos, zone in [("V", v_label_pos, "V"),
                                  ("I", i_label_pos, "I"),
                                  ("R", r_label_pos, "R")]:
            col = COLOR_WHITE if zone == self._selected else COLOR_GREY
            f = fonts["medium_b"] if zone == self._selected else fonts["medium"]
            draw_text(surface, label, f, col, pos, anchor="midtop")

        # --- Right panel (x=240..480) ---
        panel_x = 248
        panel_w = SCREEN_W - panel_x - 8
        panel_rect = pygame.Rect(panel_x, 16, panel_w, CONTENT_H - 32)
        draw_rounded_rect(surface, CARD_COLOR, panel_rect, radius=10)

        # "Ohm's Law" title
        draw_text(surface, "Ohm's Law", fonts["label_b"], ACCENT_ORANGE,
                  (panel_rect.centerx, panel_rect.y + 10), anchor="midtop")

        # Divider
        pygame.draw.line(surface, COLOR_GREY,
                         (panel_rect.x + 10, panel_rect.y + 36),
                         (panel_rect.right - 10, panel_rect.y + 36), 1)

        # Selected variable label
        sel_colors = {"V": COLOR_CYAN, "I": COLOR_GREEN, "R": ACCENT_ORANGE}
        sel_col = sel_colors[self._selected]
        draw_text(surface, f"Solving for: {self._selected}", fonts["small"], COLOR_GREY,
                  (panel_rect.centerx, panel_rect.y + 44), anchor="midtop")

        # Formula
        draw_text(surface, self._formula_text(), fonts["large_b"], sel_col,
                  (panel_rect.centerx, panel_rect.y + 68), anchor="midtop")

        # Insight text
        insights = {
            "V": "Voltage = product\nof I and R",
            "I": "Current = Voltage\ndivided by R",
            "R": "Resistance = Voltage\ndivided by I",
        }
        insight_lines = insights[self._selected].split("\n")
        for idx, line in enumerate(insight_lines):
            draw_text(surface, line, fonts["small"], COLOR_GREY,
                      (panel_rect.centerx, panel_rect.y + 118 + idx * 20),
                      anchor="midtop")

        # Example values
        examples = {
            "V": "e.g. 0.47A \u00d7 10\u03a9 = 4.7V",
            "I": "e.g. 3.3V \u00f7 470\u03a9 = 7mA",
            "R": "e.g. 5V \u00f7 0.01A = 500\u03a9",
        }
        draw_text(surface, examples[self._selected], fonts["tiny"], COLOR_GREY,
                  (panel_rect.centerx, panel_rect.y + 168), anchor="midtop")

        # Tap hint
        draw_text(surface, "Tap a zone to select", fonts["tiny"], COLOR_GREY,
                  (panel_rect.centerx, panel_rect.y + 200), anchor="midtop")


# ---------------------------------------------------------------------------
# Screen 3 — Calculator
# ---------------------------------------------------------------------------

_E24_BAND_LABEL = {
    "black":  "0",
    "brown":  "1",
    "red":    "2",
    "orange": "3",
    "yellow": "4",
    "green":  "5",
    "blue":   "6",
    "violet": "7",
    "grey":   "8",
    "white":  "9",
    "gold":   "\u00b15%",
    "silver": "\u00b110%",
}


class CalculatorScreen:
    """On-screen keypad to enter a resistance, snap to E24, show colour bands."""

    def __init__(self, fonts):
        self._fonts         = fonts
        self._input_buffer  = ""
        self._result_value  = None   # snapped E24 float
        self._result_bands  = []     # list of colour name strings
        self._pressed_key   = None   # label of currently pressed button
        self._error         = False

        # Button layout: 3 columns × 4 rows grid
        # Row 0: 7 8 9
        # Row 1: 4 5 6
        # Row 2: 1 2 3
        # Row 3: . 0 ⌫  (backspace)
        # Row 4 (below): [  Clear  ] [ Enter ]
        self._keys = []       # list of (label, rect)
        self._build_keypad()

    def _build_keypad(self):
        """Pre-compute button rectangles for the 3×4 digit grid plus action row."""
        grid_x     = 248
        grid_y     = 60
        btn_w      = 64
        btn_h      = 44
        gap        = 6
        cols       = 3

        digit_rows = [
            ["7", "8", "9"],
            ["4", "5", "6"],
            ["1", "2", "3"],
            [".", "0", "\u232b"],  # ← backspace char
        ]

        self._keys = []
        for r, row in enumerate(digit_rows):
            for c, label in enumerate(row):
                x = grid_x + c * (btn_w + gap)
                y = grid_y + r * (btn_h + gap)
                self._keys.append((label, pygame.Rect(x, y, btn_w, btn_h)))

        # Action row: Clear and Enter
        action_y = grid_y + 4 * (btn_h + gap)
        clear_rect = pygame.Rect(grid_x, action_y, btn_w, btn_h)
        enter_rect = pygame.Rect(grid_x + btn_w + gap, action_y,
                                 btn_w * 2 + gap, btn_h)
        self._keys.append(("C", clear_rect))
        self._keys.append(("Enter", enter_rect))

    def _on_key(self, label):
        self._error = False
        if label == "\u232b":  # backspace
            self._input_buffer = self._input_buffer[:-1]
        elif label == "C":
            self._input_buffer = ""
            self._result_value = None
            self._result_bands = []
        elif label == "Enter":
            if self._input_buffer:
                try:
                    value = float(self._input_buffer)
                    if value <= 0:
                        self._error = True
                        return
                    snapped            = snap_to_e24(value)
                    self._result_value = snapped
                    self._result_bands = resistance_to_bands(snapped)
                except ValueError:
                    self._error = True
        elif label == ".":
            if "." not in self._input_buffer:
                self._input_buffer += "."
        elif label.isdigit():
            # Limit to 8 chars to avoid overflow
            if len(self._input_buffer) < 8:
                self._input_buffer += label

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for label, rect in self._keys:
                if rect.collidepoint(event.pos):
                    self._pressed_key = label
                    self._on_key(label)
                    break
        elif event.type == pygame.MOUSEBUTTONUP:
            self._pressed_key = None

        # Also support physical keyboard for convenience
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self._on_key("\u232b")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._on_key("Enter")
            elif event.key == pygame.K_ESCAPE:
                self._on_key("C")
            elif event.unicode and (event.unicode.isdigit() or event.unicode == "."):
                self._on_key(event.unicode)

    def update(self, dt):
        pass

    def _format_result(self, value):
        """Return a human-readable string for value in Ω/kΩ/MΩ."""
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f} M\u03a9"
        elif value >= 1_000:
            return f"{value / 1_000:.2f} k\u03a9"
        else:
            return f"{value:.1f} \u03a9"

    def draw(self, surface):
        surface.fill(BG_COLOR)
        fonts = self._fonts

        # ---- Left panel: display + result ----
        panel_rect = pygame.Rect(8, 8, 228, CONTENT_H - 16)
        draw_rounded_rect(surface, CARD_COLOR, panel_rect, radius=10)

        draw_text(surface, "Resistor Finder", fonts["body_b"], ACCENT_ORANGE,
                  (panel_rect.centerx, panel_rect.y + 10), anchor="midtop")

        # Input display box
        input_box = pygame.Rect(panel_rect.x + 8, panel_rect.y + 38,
                                panel_rect.width - 16, 40)
        draw_rounded_rect(surface, BG_COLOR, input_box, radius=6,
                          border=2, border_color=ACCENT_ORANGE)

        input_text = self._input_buffer if self._input_buffer else "\u2014"
        input_color = COLOR_WHITE if self._input_buffer else COLOR_GREY
        draw_text(surface, input_text + " \u03a9", fonts["medium_b"], input_color,
                  (input_box.centerx, input_box.centery), anchor="center")

        # Error message
        if self._error:
            draw_text(surface, "Invalid input", fonts["small"], COLOR_RED_ACCENT,
                      (panel_rect.centerx, input_box.bottom + 6), anchor="midtop")

        # Result area
        result_y = input_box.bottom + 28
        if self._result_value is not None:
            draw_text(surface, "E24 nearest:", fonts["small"], COLOR_GREY,
                      (panel_rect.centerx, result_y), anchor="midtop")
            draw_text(surface, self._format_result(self._result_value),
                      fonts["large_b"], COLOR_GREEN,
                      (panel_rect.centerx, result_y + 22), anchor="midtop")

            # Mini resistor
            if self._result_bands:
                band_rgbs = bands_to_rgb(self._result_bands)
                res_rect = pygame.Rect(panel_rect.x + 14, result_y + 68,
                                       panel_rect.width - 28, 36)
                draw_resistor(surface, res_rect, band_rgbs, show_leads=True)

                # Band names
                band_label_y = result_y + 110
                bnames = [b.capitalize() for b in self._result_bands]
                col_spacing = (panel_rect.width - 20) // 4
                for i, name in enumerate(bnames):
                    bx = panel_rect.x + 10 + i * col_spacing + col_spacing // 2
                    draw_text(surface, name, fonts["tiny"], COLOR_GREY,
                              (bx, band_label_y), anchor="midtop")
        else:
            draw_text(surface, "Enter a value", fonts["small"], COLOR_GREY,
                      (panel_rect.centerx, result_y), anchor="midtop")
            draw_text(surface, "and press Enter", fonts["small"], COLOR_GREY,
                      (panel_rect.centerx, result_y + 20), anchor="midtop")

        # ---- Right panel: keypad ----
        for label, rect in self._keys:
            is_pressed = (label == self._pressed_key)
            btn_color  = BTN_PRESS if is_pressed else BTN_IDLE

            if label == "Enter":
                btn_color = ACCENT_ORANGE if not is_pressed else (200, 80, 0)
            elif label == "C":
                btn_color = (120, 30, 30) if not is_pressed else (180, 40, 40)

            draw_rounded_rect(surface, btn_color, rect, radius=6)
            text_col = COLOR_WHITE
            f = fonts["medium_b"] if label == "Enter" else fonts["medium"]
            draw_text(surface, label, f, text_col,
                      (rect.centerx, rect.centery), anchor="center")


# ---------------------------------------------------------------------------
# Nav Bar
# ---------------------------------------------------------------------------

class NavBar:
    """Bottom nav bar with three equal-width tabs."""

    def __init__(self, fonts):
        self._fonts       = fonts
        self._active_idx  = 0
        self._pressed_idx = None
        tab_w = SCREEN_W // 3
        self._tabs = [
            pygame.Rect(i * tab_w, CONTENT_H, tab_w, NAV_H)
            for i in range(3)
        ]

    @property
    def active_index(self):
        return self._active_idx

    def set_active(self, idx):
        self._active_idx = idx % len(NAV_TABS)

    def handle_event(self, event):
        """Return the new tab index if a tap occurred, else None."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._tabs):
                if rect.collidepoint(event.pos):
                    self._pressed_idx = i
                    return i
        elif event.type == pygame.MOUSEBUTTONUP:
            self._pressed_idx = None
        return None

    def draw(self, surface):
        # Nav bar background
        draw_rounded_rect(surface, NAV_BG, NAV_RECT, radius=0)

        # Top separator
        pygame.draw.line(surface, COLOR_GREY,
                         (0, CONTENT_H), (SCREEN_W, CONTENT_H), 1)

        fonts = self._fonts
        for i, (label, rect) in enumerate(zip(NAV_TABS, self._tabs)):
            is_active  = (i == self._active_idx)
            is_pressed = (i == self._pressed_idx)

            if is_active:
                bg = ACCENT_ORANGE
            elif is_pressed:
                bg = (60, 60, 100)
            else:
                bg = NAV_BG

            pygame.draw.rect(surface, bg, rect)
            text_col = COLOR_WHITE if is_active else COLOR_GREY
            f = fonts["body_b"] if is_active else fonts["body"]
            draw_text(surface, label, f, text_col,
                      (rect.centerx, rect.centery), anchor="center")

        # Dividers between tabs
        for i in range(1, 3):
            x = i * (SCREEN_W // 3)
            pygame.draw.line(surface, COLOR_GREY,
                             (x, CONTENT_H + 4), (x, SCREEN_H - 4), 1)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    pygame.init()
    pygame.display.set_caption("Resistor Station \u2014 Demo")
    surface = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock   = pygame.time.Clock()

    fonts   = _load_fonts()
    screens = [
        LiveLabScreen(fonts),
        OhmTriangleScreen(fonts),
        CalculatorScreen(fonts),
    ]
    nav     = NavBar(fonts)
    active  = 0

    running = True
    while running:
        dt = clock.tick(30) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    active = (active + 1) % len(screens)
                    nav.set_active(active)
                elif event.key == pygame.K_LEFT:
                    active = (active - 1) % len(screens)
                    nav.set_active(active)

            # Nav bar handles its own tap first
            new_tab = nav.handle_event(event)
            if new_tab is not None:
                active = new_tab
                nav.set_active(active)
            else:
                # Forward event to active screen only if not consumed by nav
                screens[active].handle_event(event)

        screens[active].update(dt)
        screens[active].draw(surface)
        nav.draw(surface)

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
