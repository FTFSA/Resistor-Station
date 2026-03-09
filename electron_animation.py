#!/usr/bin/env python3
"""Electron flow animation — particles drift through a wire, heat up
inside a glowing resistor-shaped zone, then disperse outward and fade."""

import sys
import math
import random
import pygame

# ── constants ────────────────────────────────────────────────────────
FPS = 60
BG_COLOR = (10, 10, 30)
BG_ALPHA = 50  # translucent overlay each frame for trails
WIRE_COLOR = (50, 55, 75)
GLOW_BASE = (255, 80, 20)
ZONE_TINT = (255, 120, 50)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


# ── layout (recomputed on resize) ───────────────────────────────────
class Layout:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.wire_y = h // 2
        self.wire_r = max(16, int(h * 0.04))
        self.res_x = int(w * 0.35)
        self.res_w = int(w * 0.30)
        self.res_h = self.wire_r * 3


# ── electron ─────────────────────────────────────────────────────────
class Electron:
    def __init__(self, layout: Layout):
        self.L = layout
        self._reset()

    def _reset(self):
        L = self.L
        self.x = random.uniform(-L.w, 0)
        self.y = L.wire_y + random.uniform(-L.wire_r * 0.3, L.wire_r * 0.3)
        self.speed = random.uniform(2, 6)
        self.base_speed = self.speed
        self.size = random.uniform(2, 6)
        self.base_alpha = random.randint(150, 255)
        self.alpha = self.base_alpha
        self.base_color = (
            random.randint(50, 200),
            random.randint(100, 255),
            random.randint(200, 255),
        )
        self.offset = random.uniform(0, math.tau)
        self.heat = 0.0
        self.in_heat_zone = False
        self.dispersing = False
        self.disperse_dir = 0  # +1 or -1

    def update(self, frame: int):
        L = self.L
        in_zone = L.res_x <= self.x <= L.res_x + L.res_w
        self.in_heat_zone = in_zone and not self.dispersing

        if self.dispersing:
            # fly away from wire vertically, slow horizontal drift, fade
            self.y += self.disperse_dir * random.uniform(1.5, 3.5)
            self.x += self.speed * 0.3
            self.alpha = lerp(self.alpha, 0, 0.02)
            self.heat = lerp(self.heat, 0, 0.01)

        elif in_zone:
            # heat zone — slow down, wider oscillation
            self.speed = lerp(self.speed, self.base_speed * 0.3, 0.05)
            self.y += math.sin(frame * 0.12 + self.offset) * 4
            self.heat = lerp(self.heat, 1, 0.05)

            # hot enough? chance to break free
            if self.heat > 0.7 and random.random() < 0.01:
                self.dispersing = True
                self.disperse_dir = 1 if self.y > L.wire_y else -1

        else:
            # normal wire flow
            self.speed = lerp(self.speed, self.base_speed, 0.05)
            self.y += math.sin(frame * 0.05 + self.offset) * 1.5
            self.heat = lerp(self.heat, 0, 0.05)

        if not self.dispersing:
            self.x += self.speed

        # reset when faded, off-screen right, or drifted too far vertically
        if (
            self.alpha < 5
            or self.x > L.w
            or self.y < -100
            or self.y > L.h + 100
        ):
            self._reset()

    def draw(self, surface: pygame.Surface):
        cool = self.base_color
        hot = (255, 110, 15)
        r, g, b = lerp_color(cool, hot, self.heat)
        a = max(0, min(255, int(self.alpha)))

        dot = pygame.Surface((int(self.size * 2), int(self.size * 2)), pygame.SRCALPHA)
        pygame.draw.circle(
            dot,
            (r, g, b, a),
            (int(self.size), int(self.size)),
            int(self.size),
        )
        surface.blit(dot, (int(self.x - self.size), int(self.y - self.size)))


# ── drawing helpers ──────────────────────────────────────────────────
def draw_rounded_rect_alpha(surface, color, rect, radius, alpha):
    """Draw a filled rounded rectangle with per-surface alpha."""
    x, y, w, h = rect
    tmp = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(tmp, (*color, alpha), (0, 0, w, h), border_radius=radius)
    surface.blit(tmp, (x, y))


def draw_circuit(surface, layout, particles, frame):
    L = layout

    # full-width wire (behind everything)
    wire_surf = pygame.Surface((L.w, L.wire_r * 2), pygame.SRCALPHA)
    wire_surf.fill((*WIRE_COLOR, 255))
    surface.blit(wire_surf, (0, L.wire_y - L.wire_r))

    # heat glow — layered rounded rects
    heat_count = sum(1 for e in particles if e.in_heat_zone)
    gi = max(0, min(110, int(110 * heat_count / 60)))
    cr = L.res_h // 2

    for g in range(4, 0, -1):
        a = max(0, gi // g)
        if a < 1:
            continue
        draw_rounded_rect_alpha(
            surface,
            GLOW_BASE,
            (
                L.res_x - g * 10,
                L.wire_y - L.res_h // 2 - g * 8,
                L.res_w + g * 20,
                L.res_h + g * 16,
            ),
            cr + g * 8,
            a,
        )

    # faint zone outline (always visible)
    draw_rounded_rect_alpha(
        surface,
        ZONE_TINT,
        (L.res_x, L.wire_y - L.res_h // 2, L.res_w, L.res_h),
        cr,
        12,
    )


# ── main ─────────────────────────────────────────────────────────────
def main():
    pygame.init()

    info = pygame.display.Info()
    width, height = info.current_w, info.current_h
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    pygame.display.set_caption("Electron Flow")

    clock = pygame.time.Clock()
    layout = Layout(width, height)

    # translucent overlay for trail effect
    trail = pygame.Surface((width, height), pygame.SRCALPHA)
    trail.fill((*BG_COLOR, BG_ALPHA))

    particles = [Electron(layout) for _ in range(300)]
    frame = 0
    fullscreen = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_f:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode(
                            (0, 0), pygame.FULLSCREEN
                        )
                        width = screen.get_width()
                        height = screen.get_height()
                    else:
                        width, height = 800, 600
                        screen = pygame.display.set_mode(
                            (width, height), pygame.RESIZABLE
                        )
                    layout = Layout(width, height)
                    trail = pygame.Surface((width, height), pygame.SRCALPHA)
                    trail.fill((*BG_COLOR, BG_ALPHA))
                    for p in particles:
                        p.L = layout
                        p._reset()

            elif event.type == pygame.VIDEORESIZE:
                width, height = event.w, event.h
                screen = pygame.display.set_mode(
                    (width, height), pygame.RESIZABLE
                )
                layout = Layout(width, height)
                trail = pygame.Surface((width, height), pygame.SRCALPHA)
                trail.fill((*BG_COLOR, BG_ALPHA))
                for p in particles:
                    p.L = layout
                    p._reset()

        # trail overlay instead of full clear — gives the motion-blur effect
        screen.blit(trail, (0, 0))

        draw_circuit(screen, layout, particles, frame)

        for p in particles:
            p.update(frame)
            p.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)
        frame += 1


if __name__ == "__main__":
    main()
