from __future__ import annotations

"""
Resistor Station - Pygame Display Manager

Manages pygame initialisation, screen transitions, the nav bar, status bar,
and the main render loop for the MPI3508 480×320 HDMI touchscreen on Pi 4.

Brutalist light theme: cream background, hard shadows, black borders.
"""

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
NAV_BAR_AREA = pygame.Rect(0, SCREEN_H - NAV_H, SCREEN_W, NAV_H)
STATUS_AREA  = pygame.Rect(0, 0, SCREEN_W, STATUS_H)

# ---------------------------------------------------------------------------
# Colour palette — brutalist light theme
# ---------------------------------------------------------------------------

BG_COLOR       = (247, 245, 240)   # cream #F7F5F0
TEXT_COLOR      = (24,  24,  27)    # zinc-900
TEXT_MUTED      = (113, 113, 122)   # zinc-500
CARD_BG         = (255, 255, 255)   # white cards
NAV_BG          = (255, 255, 255)   # white nav
NAV_BORDER      = (0,   0,   0)     # black border
BORDER_COLOR    = (0,   0,   0)     # 2px black borders
SHADOW_COLOR    = (0,   0,   0)     # hard shadow
LCD_BG          = (18,  18,  18)    # LCD panel bg #121212
LCD_GREEN       = (57,  255, 20)    # LCD text #39ff14
SCREW_COLOR     = (161, 161, 170)   # zinc-400
GRID_COLOR      = (235, 233, 228)   # subtle grid lines

# Accent colours per electrical quantity
VOLTAGE_COLOR   = (239, 68,  68)    # red-500
CURRENT_COLOR   = (59,  130, 246)   # blue-500
POWER_COLOR     = (16,  185, 129)   # emerald-500
RESISTOR_TAN    = (232, 222, 194)   # #E8DEC2

# Legacy aliases used by some screens
ACCENT          = VOLTAGE_COLOR
GREEN           = (34,  197, 94)    # green-500
ORANGE          = CURRENT_COLOR     # current card is blue in ref
YELLOW          = (251, 191, 36)
RED             = (239, 68,  68)

# ---------------------------------------------------------------------------
# Nav bar configuration — 4 screens
# ---------------------------------------------------------------------------

_NAV_LABELS = ["Lab", "Triangle", "Calc", "Codes"]
_NAV_KEYS   = ["live_lab", "ohm_triangle", "ohm_calc", "calculator"]
_NAV_BTN_W  = SCREEN_W // 4   # 120 px each


# ---------------------------------------------------------------------------
# Drawing helpers (module-level, used by screens too)
# ---------------------------------------------------------------------------

def draw_hard_shadow_rect(surface, rect, color, radius=8, shadow_offset=2):
    """Draw a rect with hard black shadow, fill, and black border."""
    shadow = rect.move(shadow_offset, shadow_offset)
    pygame.draw.rect(surface, SHADOW_COLOR, shadow, border_radius=radius)
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, BORDER_COLOR, rect, width=2, border_radius=radius)


def draw_grid_background(surface, area):
    """Draw subtle grid lines over the content area."""
    for x in range(area.left, area.right, 20):
        pygame.draw.line(surface, GRID_COLOR, (x, area.top), (x, area.bottom))
    for y in range(area.top, area.bottom, 20):
        pygame.draw.line(surface, GRID_COLOR, (area.left, y), (area.right, y))


def draw_screws(surface, area):
    """Draw 4 decorative screws at the corners of the given area."""
    inset = 8
    positions = [
        (area.left + inset, area.top + inset),
        (area.right - inset, area.top + inset),
        (area.left + inset, area.bottom - inset),
        (area.right - inset, area.bottom - inset),
    ]
    for pos in positions:
        pygame.draw.circle(surface, SCREW_COLOR, pos, 3)
        pygame.draw.circle(surface, BORDER_COLOR, pos, 3, 1)


# ---------------------------------------------------------------------------
# UIManager
# ---------------------------------------------------------------------------

class UIManager:
    """Manages registered screens and dispatches events, updates, and draws.

    Construction:
        UIManager()          – hardware mode
        UIManager(surface)   – test/headless mode
    """

    def __init__(self, surface=None) -> None:
        self._test_mode = surface is not None

        if self._test_mode:
            pygame.font.init()
            self._surface = surface
            self.screen   = surface
            self.clock    = None
            self._init_fonts_safe()
        else:
            pygame.init()
            _flags = pygame.FULLSCREEN | getattr(pygame, "SCALED", 0)
            self.screen = pygame.display.set_mode(
                (SCREEN_W, SCREEN_H), _flags
            )
            pygame.display.set_caption("Resistor Station")
            self._surface = self.screen
            self.clock = pygame.time.Clock()
            self._init_fonts_safe()

        self._screens: dict[str, object] = {}
        self._active: str | None = None
        self._nav_rects: list[pygame.Rect] = []
        self._nav_pressed: int | None = None
        self.current_screen: str = "live_lab"

    # ------------------------------------------------------------------
    # Font loading
    # ------------------------------------------------------------------

    def _init_fonts_safe(self) -> None:
        """Load fonts with fallback to defaults."""
        def _load(family: str, size: int, bold: bool = False) -> pygame.font.Font:
            try:
                font = pygame.font.SysFont(family, size, bold=bold)
                if font is None:
                    raise RuntimeError("SysFont returned None")
                return font
            except Exception:
                return pygame.font.SysFont(None, size, bold=bold)

        self.title_font   = _load("dejavusans", 32, bold=True)
        self.heading_font = _load("dejavusans", 22, bold=True)
        self.body_font    = _load("dejavusans", 16)
        self.mono_font    = _load("dejavusansmono", 14)
        self.small_font   = _load("dejavusans", 13)
        self.tiny_font    = _load("dejavusansmono", 10)

    # ------------------------------------------------------------------
    # Screen registry
    # ------------------------------------------------------------------

    def register_screen(self, name: str, screen_obj) -> None:
        self._screens[name] = screen_obj

    def switch_to(self, name: str) -> None:
        if name not in self._screens:
            raise KeyError(f"Unknown screen: {name!r}")
        if self._active is not None and self._active != name:
            old = self._screens[self._active]
            if hasattr(old, "on_exit"):
                old.on_exit()
        self._active = name
        self.current_screen = name
        new = self._screens[name]
        if hasattr(new, "on_enter"):
            new.on_enter()

    def switch_screen(self, name: str) -> None:
        self.switch_to(name)

    # ------------------------------------------------------------------
    # Main-loop hooks
    # ------------------------------------------------------------------

    def handle_event(self, event) -> None:
        if self._active is not None:
            self._screens[self._active].handle_event(event)

    def handle_events(self) -> bool:
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
        if self._active is not None:
            self._screens[self._active].update(dt)

    def draw(self) -> None:
        if self._active is not None:
            active_screen = self._screens[self._active]
            active_screen.draw(self._surface)

        if not self._test_mode:
            self.draw_status_bar()
            self.draw_nav_bar()
            pygame.display.flip()
            if self.clock is not None:
                self.clock.tick(30)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def draw_status_bar(self) -> None:
        """Draw slim status bar at top of screen."""
        bar = STATUS_AREA
        pygame.draw.rect(self._surface, CARD_BG, bar)
        pygame.draw.line(self._surface, BORDER_COLOR,
                         (0, STATUS_H - 1), (SCREEN_W, STATUS_H - 1), 1)

        # Left: status dot + label
        dot_x = 8
        dot_y = STATUS_H // 2
        pygame.draw.circle(self._surface, RED, (dot_x, dot_y), 4)
        self.draw_text("SYSTEM ACTIVE", self.tiny_font, TEXT_COLOR,
                       dot_x + 8, dot_y, anchor="midleft")

        # Right: resolution label
        self.draw_text("480x320_MODE", self.tiny_font, TEXT_MUTED,
                       SCREEN_W - 6, dot_y, anchor="midright")

    # ------------------------------------------------------------------
    # Nav bar
    # ------------------------------------------------------------------

    def draw_nav_bar(self) -> None:
        """Draw bottom nav bar with 4 screen-switching buttons."""
        nav_y = SCREEN_H - NAV_H

        # White background
        nav_rect = pygame.Rect(0, nav_y, SCREEN_W, NAV_H)
        pygame.draw.rect(self._surface, NAV_BG, nav_rect)

        # 2px black top border
        pygame.draw.line(self._surface, NAV_BORDER,
                         (0, nav_y), (SCREEN_W - 1, nav_y), 2)

        self._nav_rects = []
        for i, (label, key) in enumerate(zip(_NAV_LABELS, _NAV_KEYS)):
            rect = pygame.Rect(i * _NAV_BTN_W, nav_y + 2, _NAV_BTN_W, NAV_H - 2)
            self._nav_rects.append(rect)

            is_active = (key == self._active)
            label_color = TEXT_COLOR if is_active else TEXT_MUTED

            self.draw_text(label, self.body_font, label_color,
                           rect.centerx, rect.centery - 4, anchor="center")

            # Active indicator: 4px black rounded pill at bottom
            if is_active:
                pill_w = 32
                pill_h = 4
                pill_x = rect.centerx - pill_w // 2
                pill_y = rect.bottom - pill_h - 4
                pill_rect = pygame.Rect(pill_x, pill_y, pill_w, pill_h)
                pygame.draw.rect(self._surface, BORDER_COLOR, pill_rect,
                                 border_radius=2)

    def _nav_hit(self, pos) -> str | None:
        for rect, key in zip(self._nav_rects, _NAV_KEYS):
            if rect.collidepoint(pos):
                if key in self._screens:
                    self.switch_to(key)
                return key
        return None

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def draw_rounded_rect(self, surface, rect, color, radius=8, width=0):
        pygame.draw.rect(surface, color, rect, width=width, border_radius=radius)

    def draw_text(self, text, font, color, x, y, anchor="topleft"):
        surf = font.render(text, True, color)
        rect = surf.get_rect()
        setattr(rect, anchor, (x, y))
        self.screen.blit(surf, rect)
        return rect

    def draw_button(self, text, rect, color, text_color, pressed=False):
        if pressed:
            color = tuple(max(0, int(c * 0.75)) for c in color)
        draw_hard_shadow_rect(self._surface, rect, color)
        self.draw_text(text, self.body_font, text_color,
                       rect.centerx, rect.centery, anchor="center")
        return pygame.Rect(rect)

    def draw_resistor(self, surface, x, y, w, h, bands):
        """Draw a 4-band resistor illustration with brutalist style."""
        if not bands or len(bands) < 4:
            return

        lead_w   = int(w * 0.15)
        body_x   = x + lead_w
        body_w   = int(w * 0.70)
        body_y   = y
        cy       = y + h // 2

        lead_color = TEXT_COLOR
        pygame.draw.line(surface, lead_color, (x, cy), (body_x, cy), 2)
        pygame.draw.line(surface, lead_color,
                         (body_x + body_w, cy), (x + w, cy), 2)

        body_rect = pygame.Rect(body_x, body_y, body_w, h)
        radius = max(2, h // 3)

        # Hard shadow + fill + border
        shadow = body_rect.move(2, 2)
        pygame.draw.rect(surface, SHADOW_COLOR, shadow, border_radius=radius)
        pygame.draw.rect(surface, RESISTOR_TAN, body_rect, border_radius=radius)

        band_w      = max(2, int(w * 0.06))
        half_band   = band_w // 2
        centres_pct = [0.20, 0.40, 0.60, 0.80]

        for i, band in enumerate(bands[:4]):
            rgb = band.get("rgb", (128, 128, 128))
            centre_x = int(body_x + centres_pct[i] * body_w)
            bx = centre_x - half_band
            bx = max(body_x, min(bx, body_x + body_w - band_w))
            band_rect = pygame.Rect(bx, body_y, band_w, h)
            band_rect = band_rect.clip(body_rect)
            if band_rect.width > 0 and band_rect.height > 0:
                pygame.draw.rect(surface, rgb, band_rect)

        pygame.draw.rect(surface, BORDER_COLOR, body_rect,
                         width=2, border_radius=radius)
