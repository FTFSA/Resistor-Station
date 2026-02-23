from __future__ import annotations

"""
Resistor Station - Pygame Display Manager

Manages pygame initialisation, screen transitions, the nav bar, and the main
render loop for the MPI3508 480×320 HDMI touchscreen on Raspberry Pi 4.

The UIManager can be constructed in two modes:

  1. Hardware mode (no surface argument):
       mgr = UIManager()
     pygame.init() is called, a 480×320 fullscreen display is created, and
     the clock and fonts are set up.

  2. Headless / test mode (surface provided):
       mgr = UIManager(surface)
     pygame is NOT re-initialised.  The supplied surface is used directly.
     Clock and display-flip calls are skipped so the class works with a
     MagicMock surface under SDL dummy mode.
"""

import math
import pygame


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

SCREEN_W  = 480
SCREEN_H  = 320
NAV_H     = 48                  # nav bar height, pinned to bottom
CONTENT_H = SCREEN_H - NAV_H   # 272 px available for screen content

# Content and nav bar rects for convenience
CONTENT_AREA = pygame.Rect(0, 0, SCREEN_W, CONTENT_H)
NAV_BAR_AREA = pygame.Rect(0, SCREEN_H - NAV_H, SCREEN_W, NAV_H)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

BG_COLOR    = (15,  23,  42)   # dark blue-gray — main background
TEXT_COLOR  = (226, 232, 240)  # near-white — primary text
ACCENT      = (56,  189, 248)  # cyan — voltage / active nav
GREEN       = (52,  211, 153)  # current accent
ORANGE      = (251, 146, 60)   # resistance accent
YELLOW      = (251, 191, 36)   # warning / highlight
RED         = (248, 113, 113)  # error / warning
NAV_BG      = (8,   15,  30)   # nav bar background, darker than BG_COLOR
NAV_BORDER  = (30,  41,  59)   # 1-px top border on the nav bar
RESISTOR_TAN = (210, 180, 140)  # resistor body colour

# ---------------------------------------------------------------------------
# Nav bar configuration
# ---------------------------------------------------------------------------

_NAV_LABELS = ["Live Lab", "Triangle", "Calculator"]
_NAV_KEYS   = ["live_lab", "ohm_triangle", "calculator"]
_NAV_BTN_W  = SCREEN_W // 3   # 160 px each


# ---------------------------------------------------------------------------
# UIManager
# ---------------------------------------------------------------------------

class UIManager:
    """Manages registered screens and dispatches events, updates, and draws.

    Screens are registered by name and activated via switch_to() / switch_screen().
    Only the active screen receives update() and draw() calls.  handle_event()
    is also forwarded exclusively to the active screen.

    Construction:
        UIManager()          – hardware mode: calls pygame.init(), creates
                               480×320 fullscreen display.
        UIManager(surface)   – test/headless mode: uses the provided surface,
                               skips pygame init and display management.

    Args:
        surface: Optional pygame.Surface for headless / test mode.
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, surface=None) -> None:
        self._test_mode = surface is not None

        if self._test_mode:
            # Headless path — use the supplied mock/real surface as-is.
            # Initialise only the font subsystem (no display required).
            pygame.font.init()
            self._surface = surface
            self.screen   = surface       # alias used by drawing helpers
            self.clock    = None
            self._init_fonts_safe()
        else:
            # Hardware path — full Pygame setup.
            pygame.init()
            self.screen = pygame.display.set_mode(
                (SCREEN_W, SCREEN_H), pygame.FULLSCREEN
            )
            pygame.display.set_caption("Resistor Station")
            self._surface = self.screen
            self.clock = pygame.time.Clock()
            self._init_fonts_safe()

        # Screen registry
        self._screens: dict[str, object] = {}
        self._active: str | None = None

        # Nav hit-rects are built lazily in draw_nav_bar(); initialise to []
        # so _nav_hit() never crashes before the first draw.
        self._nav_rects: list[pygame.Rect] = []

        # Track the currently pressed nav button for visual feedback.
        self._nav_pressed: int | None = None

        # Expose primary screen keys as a public attribute for callers that
        # want to enumerate the default navigation structure.
        self.current_screen: str = "live_lab"

    # ------------------------------------------------------------------
    # Font loading
    # ------------------------------------------------------------------

    def _init_fonts_safe(self) -> None:
        """Load DejaVu Sans at each needed size, falling back to the default font."""
        def _load(family: str, size: int, bold: bool = False) -> pygame.font.Font:
            try:
                font = pygame.font.SysFont(family, size, bold=bold)
                # SysFont can return None in dummy SDL environments
                if font is None:
                    raise RuntimeError("SysFont returned None")
                return font
            except Exception:
                return pygame.font.SysFont(None, size, bold=bold)

        self.title_font   = _load("dejavusans", 32, bold=True)
        self.heading_font = _load("dejavusans", 22, bold=True)
        self.body_font    = _load("dejavusans", 16)
        self.mono_font    = _load("dejavusansmono", 14)

    # ------------------------------------------------------------------
    # Screen registry
    # ------------------------------------------------------------------

    def register_screen(self, name: str, screen_obj) -> None:
        """Add a screen to the registry under the given name.

        Args:
            name:       Unique string key (e.g. ``'live_lab'``).
            screen_obj: Object implementing the Screen interface contract
                        (update, draw, handle_event, optionally on_enter/on_exit).
        """
        self._screens[name] = screen_obj

    def switch_to(self, name: str) -> None:
        """Activate the named screen.

        Args:
            name: Key previously passed to register_screen().

        Raises:
            KeyError: If *name* has not been registered.
        """
        if name not in self._screens:
            raise KeyError(f"Unknown screen: {name!r}")
        # Call on_exit on the departing screen, if provided.
        if self._active is not None and self._active != name:
            old = self._screens[self._active]
            if hasattr(old, "on_exit"):
                old.on_exit()
        self._active = name
        self.current_screen = name
        new = self._screens[name]
        if hasattr(new, "on_enter"):
            new.on_enter()

    # Alias to match the new public API name in the spec.
    def switch_screen(self, name: str) -> None:
        """Alias for :meth:`switch_to`.  Both names are supported."""
        self.switch_to(name)

    # ------------------------------------------------------------------
    # Main-loop hooks
    # ------------------------------------------------------------------

    def handle_event(self, event) -> None:
        """Forward a single pygame event to the active screen (if any).

        This is the single-event dispatch path used by the test suite and by
        callers that manage their own event loop.

        Args:
            event: A pygame event object.
        """
        if self._active is not None:
            self._screens[self._active].handle_event(event)

    def handle_events(self) -> bool:
        """Drain the pygame event queue, handle nav taps, and dispatch to the active screen.

        Returns:
            ``False`` if the application should quit (QUIT or Escape pressed),
            ``True`` otherwise.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                nav_name = self._nav_hit(pos)
                if nav_name is None and self._active is not None:
                    screen = self._screens[self._active]
                    if hasattr(screen, "handle_touch"):
                        screen.handle_touch(pos[0], pos[1])
                    elif hasattr(screen, "handle_event"):
                        screen.handle_event(event)
        return True

    def update(self, dt: float) -> None:
        """Advance the active screen by *dt* seconds.

        Args:
            dt: Elapsed time in seconds since the last frame.
        """
        if self._active is not None:
            self._screens[self._active].update(dt)

    def draw(self) -> None:
        """Render the active screen onto the surface, then overlay the nav bar."""
        if self._active is not None:
            active_screen = self._screens[self._active]
            active_screen.draw(self._surface)

        if not self._test_mode:
            # Only draw nav bar and flip in hardware mode to avoid
            # calling pygame.draw on a MagicMock surface.
            self.draw_nav_bar()
            pygame.display.flip()
            if self.clock is not None:
                self.clock.tick(30)

    # ------------------------------------------------------------------
    # Nav bar
    # ------------------------------------------------------------------

    def draw_nav_bar(self) -> None:
        """Draw the bottom nav bar with three screen-switching buttons.

        Builds ``self._nav_rects`` so that ``_nav_hit()`` can do hit-testing.
        """
        nav_y = SCREEN_H - NAV_H

        # Top border
        pygame.draw.line(
            self._surface,
            NAV_BORDER,
            (0, nav_y),
            (SCREEN_W - 1, nav_y),
            1,
        )

        # Build hit rects on first call (or refresh each frame — cheap)
        self._nav_rects = []
        for i, (label, key) in enumerate(zip(_NAV_LABELS, _NAV_KEYS)):
            rect = pygame.Rect(i * _NAV_BTN_W, nav_y + 1, _NAV_BTN_W, NAV_H - 1)
            self._nav_rects.append(rect)

            is_active = (key == self._active)
            fill_color = ACCENT if is_active else NAV_BG
            label_color = BG_COLOR if is_active else TEXT_COLOR

            pygame.draw.rect(self._surface, fill_color, rect)
            self.draw_text(label, self.body_font, label_color,
                           rect.centerx, rect.centery, anchor="center")

    def _nav_hit(self, pos) -> str | None:
        """Test *pos* against nav bar rects.

        If a registered screen is hit, ``switch_to()`` is called automatically.

        Args:
            pos: (x, y) tuple from a MOUSEBUTTONDOWN event.

        Returns:
            The screen key string if a nav button was hit, else ``None``.
        """
        for rect, key in zip(self._nav_rects, _NAV_KEYS):
            if rect.collidepoint(pos):
                if key in self._screens:
                    self.switch_to(key)
                return key
        return None

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def draw_rounded_rect(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        color: tuple,
        radius: int = 8,
        width: int = 0,
    ) -> None:
        """Draw a filled or outlined rounded rectangle.

        Args:
            surface: Target surface.
            rect:    Bounding rect.
            color:   RGB colour tuple.
            radius:  Corner radius in pixels (default 8).
            width:   Line width; 0 = filled (default 0).
        """
        pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)

    def draw_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: tuple,
        x: int,
        y: int,
        anchor: str = "topleft",
    ) -> pygame.Rect:
        """Render *text* onto ``self.screen`` at the given anchor position.

        Args:
            text:   String to render.
            font:   pygame.font.Font instance.
            color:  RGB colour tuple.
            x, y:   Pixel coordinates for the anchor point.
            anchor: One of the pygame.Rect attributes (e.g. ``'topleft'``,
                    ``'center'``, ``'midtop'``, ``'midleft'``).

        Returns:
            The blit rect of the rendered text.
        """
        surf = font.render(text, True, color)
        rect = surf.get_rect()
        setattr(rect, anchor, (x, y))
        self.screen.blit(surf, rect)
        return rect

    def draw_button(
        self,
        text: str,
        rect: pygame.Rect,
        color: tuple,
        text_color: tuple,
        pressed: bool = False,
    ) -> pygame.Rect:
        """Draw a rounded-rectangle button with centred label text.

        Args:
            text:       Button label.
            rect:       Bounding rect for the button.
            color:      Button fill colour.
            text_color: Label colour.
            pressed:    If ``True``, darken *color* by 25 % for a press effect.

        Returns:
            *rect* as a ``pygame.Rect``.
        """
        if pressed:
            color = tuple(max(0, int(c * 0.75)) for c in color)
        pygame.draw.rect(self._surface, color, rect, border_radius=8)
        self.draw_text(text, self.body_font, text_color,
                       rect.centerx, rect.centery, anchor="center")
        return pygame.Rect(rect)

    def draw_resistor(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        w: int,
        h: int,
        bands: list[dict],
    ) -> None:
        """Draw a 4-band resistor illustration.

        The resistor is drawn as a tan rounded-rectangle body with wire leads
        extending from each end.  Four colour bands are rendered as vertical
        stripes evenly spaced across the middle 70 % of the body width, with
        their centres at 20 %, 40 %, 60 %, and 80 % of the body width.

        Args:
            surface: Target surface to draw onto.
            x, y:    Top-left origin of the overall bounding box (includes leads).
            w, h:    Width and height of the bounding box.
            bands:   List of 4 band dicts from ``color_code.resistance_to_bands()``.
                     Each dict has at least ``'rgb'`` (tuple) and ``'name'`` (str).
        """
        if not bands or len(bands) < 4:
            return

        # --- geometry ---
        lead_w   = int(w * 0.15)
        body_x   = x + lead_w
        body_w   = int(w * 0.70)
        body_y   = y
        cy       = y + h // 2   # vertical centre

        # Wire leads (thin horizontal lines at the vertical centre)
        lead_color = TEXT_COLOR
        # Left lead
        pygame.draw.line(surface, lead_color,
                         (x,              cy),
                         (body_x,         cy), 2)
        # Right lead
        pygame.draw.line(surface, lead_color,
                         (body_x + body_w, cy),
                         (x + w,           cy), 2)

        # Resistor body
        body_rect = pygame.Rect(body_x, body_y, body_w, h)
        radius = max(2, h // 3)
        pygame.draw.rect(surface, RESISTOR_TAN, body_rect, border_radius=radius)

        # --- colour bands ---
        # 4 bands; centres at 20 %, 40 %, 60 %, 80 % of body_w from body_x.
        band_w      = max(2, int(w * 0.06))
        half_band   = band_w // 2
        centres_pct = [0.20, 0.40, 0.60, 0.80]

        for i, band in enumerate(bands[:4]):
            rgb = band.get("rgb", (128, 128, 128))
            centre_x = int(body_x + centres_pct[i] * body_w)
            bx = centre_x - half_band
            # Clip band to body bounds
            bx = max(body_x, min(bx, body_x + body_w - band_w))
            band_rect = pygame.Rect(bx, body_y, band_w, h)
            # Clip to body rect so bands don't overdraw the rounded corners
            band_rect = band_rect.clip(body_rect)
            if band_rect.width > 0 and band_rect.height > 0:
                pygame.draw.rect(surface, rgb, band_rect)

        # Re-draw the body outline to crisp up the rounded corners over bands
        pygame.draw.rect(surface, RESISTOR_TAN, body_rect,
                         width=2, border_radius=radius)
