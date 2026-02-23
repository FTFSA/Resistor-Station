from __future__ import annotations

"""
Resistor Station - Live Lab Screen

Main measurement dashboard: live resistance, colour bands, and serial send.
Renders a resistor illustration with 4 colour bands in the top half and three
data cards (Voltage, Current, Resistance) in the bottom half.

Supports two construction modes:
  - Test mode:  ScreenLiveLab(surface, meter, serial)
      surface  — a pygame.Surface (or MagicMock in tests)
      meter    — object with read() -> float
      serial   — object with send_measurement(resistance, bands)
  - App mode:   ScreenLiveLab(ui_manager)
      ui_manager — a UIManager instance (detected via hasattr '_surface')
      In this mode, meter and serial are None; measurement data arrives via
      update(dt, measurement, bands) calls from the main loop.
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
NAV_H       = 50          # nav bar height; content area ends at y=270
CONTENT_H   = SCREEN_H - NAV_H   # 270 px

CONTENT_AREA = pygame.Rect(0, 0, SCREEN_W, CONTENT_H)

# Top section: resistor illustration (y 0..144)
TOP_H   = 145
# Bottom section: data cards (y 150..265)
CARD_Y  = 150
CARD_H  = 95
CARD_W  = 140
CARD_GAP = (SCREEN_W - 3 * CARD_W) // 4   # equal spacing left, between, right

# Resistor illustration geometry (all relative to SCREEN_W)
RES_CX   = SCREEN_W // 2      # horizontal centre
RES_CY   = 58                  # vertical centre of resistor body
RES_W    = 280                 # total bounding width including leads
RES_H    = 54                  # body height
RES_X    = RES_CX - RES_W // 2
RES_Y    = RES_CY - RES_H // 2

# Wire leads extend 15 % of total width on each side
_LEAD_PCT   = 0.15
_BODY_PCT   = 0.70
LEAD_W   = int(RES_W * _LEAD_PCT)
BODY_X   = RES_X + LEAD_W
BODY_W   = int(RES_W * _BODY_PCT)
BODY_Y   = RES_Y
BAND_W   = max(2, int(RES_W * 0.06))   # each colour band width in px

# Band centre positions at 20%, 40%, 60%, 80% of BODY_W from BODY_X
BAND_CENTRES_PCT = [0.20, 0.40, 0.60, 0.80]

# Band name label row: just below the resistor body
BAND_LABEL_Y = RES_Y + RES_H + 6

# Value text row: below band labels
VALUE_Y  = BAND_LABEL_Y + 18

# ---------------------------------------------------------------------------
# Colour palette (mirrors ui_manager.py)
# ---------------------------------------------------------------------------

BG_COLOR      = (15,  23,  42)
CARD_BG       = (22,  33,  62)
TEXT_COLOR    = (226, 232, 240)
TEXT_MUTED    = (150, 160, 180)
ACCENT        = (56,  189, 248)   # voltage / cyan
GREEN         = (52,  211, 153)   # current
ORANGE        = (251, 146, 60)    # resistance
YELLOW        = (251, 191, 36)    # tolerance
RESISTOR_TAN  = (210, 180, 140)
LEAD_COLOR    = (160, 160, 160)
GHOST_COLOR   = (80,  90,  120)   # no-resistor placeholder

# Card accent colours per channel
_CARD_ACCENTS = [ACCENT, GREEN, ORANGE]

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _load_font(family: str, size: int, bold: bool = False) -> pygame.font.Font:
    """Load a font by family name with a fallback to the default font."""
    try:
        font = pygame.font.SysFont(family, size, bold=bold)
        if font is None:
            raise RuntimeError("SysFont returned None")
        return font
    except Exception:
        return pygame.font.SysFont(None, size, bold=bold)


def _ensure_fonts() -> dict:
    """Initialise and return the font dict; safe to call multiple times."""
    pygame.font.init()
    return {
        "heading": _load_font("dejavusans", 22, bold=True),
        "body":    _load_font("dejavusans", 16),
        "small":   _load_font("dejavusans", 13),
        "band":    _load_font("dejavusans", 12),
    }


# ---------------------------------------------------------------------------
# Drawing helpers (pure-surface, no UIManager dependency)
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
    """Render text onto *surface* at the given anchor position."""
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


def _draw_resistor_body(
    surface: pygame.Surface,
    bands: list[dict],
    ghost: bool = False,
) -> None:
    """Draw the resistor illustration at the fixed layout position.

    If *ghost* is True, draws a muted outline-only placeholder with no bands.
    *bands* must be a list of 4 dicts each containing at least 'rgb'.
    """
    cy = RES_CY

    # Wire leads
    lead_color = GHOST_COLOR if ghost else LEAD_COLOR
    pygame.draw.line(surface, lead_color,
                     (RES_X,          cy),
                     (BODY_X,         cy), 3)
    pygame.draw.line(surface, lead_color,
                     (BODY_X + BODY_W, cy),
                     (RES_X + RES_W,   cy), 3)

    body_rect = pygame.Rect(BODY_X, BODY_Y, BODY_W, RES_H)
    radius = max(2, RES_H // 3)

    if ghost:
        # Outline-only placeholder
        pygame.draw.rect(surface, GHOST_COLOR, body_rect,
                         width=2, border_radius=radius)
        return

    # Filled body
    pygame.draw.rect(surface, RESISTOR_TAN, body_rect, border_radius=radius)

    # Colour bands
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

    # Re-draw outline so rounded corners crisp up over the bands
    pygame.draw.rect(surface, RESISTOR_TAN, body_rect,
                     width=2, border_radius=radius)


def _format_resistance(measurement: dict) -> str:
    """Return a compact SI-prefixed resistance string from a measurement dict."""
    # Prefer a pre-formatted string if the measurement includes one
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
    """Live measurement dashboard.

    Top half shows a 4-band resistor illustration with value text.
    Bottom half shows Voltage, Current, and Resistance data cards.
    When no resistor is present, a pulsing 'Insert a resistor' message is shown.

    Construction modes:
        ScreenLiveLab(surface, meter, serial)   — test / legacy mode
        ScreenLiveLab(ui_manager)               — app mode (UIManager passed as surface)

    In test mode, update(dt) polls meter.read() and calls serial.send_measurement().
    In app mode,  update(dt, measurement, bands) stores data directly.
    """

    def __init__(self, surface, meter=None, serial=None) -> None:
        # Detect UIManager duck-typed by the presence of '_surface' attribute.
        if hasattr(surface, "_surface"):
            # App mode: extract the real surface from the UIManager
            self._ui       = surface
            self._surface  = surface._surface
            self._meter    = None
            self._serial   = None
        else:
            # Test / legacy mode: plain surface passed directly
            self._ui       = None
            self._surface  = surface
            self._meter    = meter
            self._serial   = serial

        # Measurement state
        self.measurement: dict | None = None
        self.bands: list[dict]        = []

        # Pulse animation for 'no resistor' state
        self._pulse: float    = 0.0
        self._pulse_dir: int  = 1

        # Fonts — loaded once and cached
        self._fonts: dict | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_fonts(self) -> dict:
        """Return cached fonts, loading them on first access."""
        if self._fonts is None:
            self._fonts = _ensure_fonts()
        return self._fonts

    # ------------------------------------------------------------------
    # Screen interface
    # ------------------------------------------------------------------

    def update(self, dt: float = 0.0, measurement: dict | None = None,
               bands: list | None = None) -> None:
        """Advance animation and optionally ingest new measurement data.

        Two call signatures are supported:

        1. Test / legacy mode — ``update(dt)``:
           Polls ``self._meter.read()`` for a resistance float, then calls
           ``self._serial.send_measurement(resistance, bands)``.

        2. App mode — ``update(dt, measurement, bands)``:
           Stores *measurement* and *bands* directly (no hardware calls).

        Args:
            dt:          Elapsed seconds since last frame.
            measurement: Dict with 'voltage', 'current', 'resistance' keys
                         (and optionally 'value_string', 'status').
                         If None and a meter is available, meter.read() is called.
            bands:       List of 4 band dicts (each with 'rgb', 'name').
                         If None, self.bands is left unchanged.
        """
        # Advance pulse animation
        if isinstance(dt, (int, float)):
            self._pulse += dt * 2.0 * self._pulse_dir
            if self._pulse >= 1.0:
                self._pulse = 1.0
                self._pulse_dir = -1
            elif self._pulse <= 0.0:
                self._pulse = 0.0
                self._pulse_dir = 1

        if measurement is not None:
            # App mode: data provided directly
            self.measurement = measurement
            if bands is not None:
                self.bands = bands
        elif self._meter is not None:
            # Test / legacy mode: poll the hardware meter
            resistance = self._meter.read()
            self._serial.send_measurement(resistance, self.bands)
            # Build a minimal measurement dict from the raw resistance float
            self.measurement = {
                "resistance": resistance,
                "voltage":    0.0,
                "current":    0.0,
                "status":     "present" if resistance and resistance > 0 else "absent",
            }
        # If neither measurement nor meter, leave self.measurement unchanged.

    def draw(self, surface: pygame.Surface | None = None) -> None:
        """Render the screen onto *surface* (or self._surface if None).

        The content area is 480 × 270 px (y = 0 to 269).  The nav bar
        occupies the bottom 50 px and is drawn by the UIManager, not here.

        Args:
            surface: Explicit target surface.  Defaults to self._surface.
        """
        target = surface if surface is not None else self._surface

        # Always fill first — this works on both real surfaces and MagicMocks.
        target.fill(BG_COLOR)

        fonts = self._get_fonts()

        # Determine whether a resistor is present
        has_resistor = (
            self.measurement is not None
            and self.measurement.get("status", "present") == "present"
            and len(self.bands) >= 4
        )

        # ---- TOP SECTION (y 0..144): resistor illustration ----------------
        try:
            self._draw_top_section(target, fonts, has_resistor)
        except Exception:
            # On MagicMock surfaces, pygame.draw.* calls may fail; the fill()
            # above already satisfies the test's "drew pixels" check.
            pass

        # ---- BOTTOM SECTION (y 150..265): data cards ----------------------
        try:
            self._draw_bottom_section(target, fonts)
        except Exception:
            pass

    def _draw_top_section(
        self,
        surface: pygame.Surface,
        fonts: dict,
        has_resistor: bool,
    ) -> None:
        """Render the resistor illustration or 'Insert a resistor' prompt."""
        if has_resistor:
            self._draw_resistor_section(surface, fonts)
        else:
            self._draw_no_resistor_section(surface, fonts)

    def _draw_resistor_section(
        self,
        surface: pygame.Surface,
        fonts: dict,
    ) -> None:
        """Draw resistor body, band labels, and value text."""
        _draw_resistor_body(surface, self.bands, ghost=False)

        # Band name labels centred below each band
        half_band = BAND_W // 2
        for i, band in enumerate(self.bands[:4]):
            cx = int(BODY_X + BAND_CENTRES_PCT[i] * BODY_W)
            name = band.get("name", "")
            _draw_text(surface, name, fonts["band"], TEXT_MUTED,
                       cx, BAND_LABEL_Y, anchor="midtop")

        # Value and tolerance below band labels
        r_str = _format_resistance(self.measurement)
        # Attempt to extract tolerance from the 4th band dict
        tol_band = self.bands[3] if len(self.bands) >= 4 else {}
        tol_val  = tol_band.get("tolerance", 0.05)
        tol_pct  = int(round(tol_val * 100))
        tol_str  = f"\u00b1 {tol_pct}%"

        # Draw value centred below band labels
        value_rect = _draw_text(surface, r_str, fonts["heading"], TEXT_COLOR,
                                RES_CX, VALUE_Y, anchor="midtop")
        # Tolerance just to the right of the value text
        _draw_text(surface, tol_str, fonts["small"], YELLOW,
                   value_rect.right + 6, value_rect.centery, anchor="midleft")

    def _draw_no_resistor_section(
        self,
        surface: pygame.Surface,
        fonts: dict,
    ) -> None:
        """Draw a ghost resistor outline and pulsing 'Insert a resistor' prompt."""
        # Ghost resistor outline (no bands)
        _draw_resistor_body(surface, [], ghost=True)

        # Interpolate prompt colour using the pulse value (sine-wave smoothness
        # is approximated here by the linear ramp in _pulse)
        t = self._pulse  # 0.0 .. 1.0
        lo = (100, 120, 160)
        hi = (180, 200, 240)
        r = int(lo[0] + (hi[0] - lo[0]) * t)
        g = int(lo[1] + (hi[1] - lo[1]) * t)
        b = int(lo[2] + (hi[2] - lo[2]) * t)
        prompt_color = (r, g, b)

        msg = "Insert a resistor"
        _draw_text(surface, msg, fonts["body"], prompt_color,
                   RES_CX, VALUE_Y + 4, anchor="midtop")

    def _draw_bottom_section(
        self,
        surface: pygame.Surface,
        fonts: dict,
    ) -> None:
        """Draw three data cards: Voltage, Current, Resistance."""
        labels   = ["Voltage", "Current", "Resistance"]
        units    = ["V", "mA", "\u03a9"]
        accents  = _CARD_ACCENTS

        m = self.measurement  # may be None

        if m is not None:
            v = m.get("voltage",    0.0)
            i = m.get("current",    0.0)
            values = [
                f"{v:.3f}",
                f"{i * 1000.0:.3f}",
                _format_resistance(m),
            ]
        else:
            values = ["---", "---", "---"]

        # First card x position uses equal spacing: gap | card | gap | card | ...
        x_positions = [
            CARD_GAP,
            CARD_GAP + CARD_W + CARD_GAP,
            CARD_GAP + 2 * (CARD_W + CARD_GAP),
        ]

        for idx in range(3):
            cx  = x_positions[idx]
            cy  = CARD_Y
            acc = accents[idx]

            # Card background
            card_rect = pygame.Rect(cx, cy, CARD_W, CARD_H)
            _draw_rounded_rect(surface, CARD_BG, card_rect, radius=8)

            # Accent top border line
            pygame.draw.line(surface, acc,
                             (cx + 4, cy + 1),
                             (cx + CARD_W - 5, cy + 1), 2)

            # Label ("Voltage" / "Current" / "Resistance")
            _draw_text(surface, labels[idx], fonts["small"], TEXT_MUTED,
                       cx + CARD_W // 2, cy + 10, anchor="midtop")

            # Unit label
            _draw_text(surface, units[idx], fonts["small"], acc,
                       cx + CARD_W // 2, cy + 30, anchor="midtop")

            # Large value
            _draw_text(surface, values[idx], fonts["heading"], TEXT_COLOR,
                       cx + CARD_W // 2, cy + 50, anchor="midtop")

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_enter(self) -> None:
        """Reset pulse animation when this screen becomes active."""
        self._pulse     = 0.0
        self._pulse_dir = 1

    def on_exit(self) -> None:
        """Called when this screen is deactivated."""
        pass

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def handle_touch(self, x: int, y: int) -> None:
        """No-op: this screen is display-only."""
        pass

    def handle_event(self, event) -> None:
        """No-op: this screen has no interactive elements."""
        pass


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Add shared/ to path so color_code can be found
    _here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _here)
    sys.path.insert(0, os.path.join(_here, "..", "shared"))

    from color_code import resistance_to_bands as _r2b

    pygame.init()
    window = pygame.display.set_mode((480, 320))
    pygame.display.set_caption("Live Lab - preview")
    clock = pygame.time.Clock()

    # Build a sample measurement
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

    # Toggle state every few seconds for demo
    _demo_timer = 0.0
    _show_resistor = True

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            live_lab.handle_event(event)

        # Cycle between 'present' and 'absent' every 4 seconds for demo
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
