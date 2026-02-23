"""
Resistor Station - Live Lab Screen
Main measurement dashboard: live resistance, color bands, and serial send.
"""

import pygame


class ScreenLiveLab:
    """Live measurement dashboard.

    Polls the meter on every update(), sends data over serial, and renders a
    basic resistance readout onto the surface.

    Args:
        surface: pygame.Surface to render onto (480x320).
        meter:   Object with a read() method that returns a resistance float.
        serial:  Object with a send_measurement(resistance, bands) method.
    """

    def __init__(self, surface, meter, serial):
        self._surface = surface
        self._meter = meter
        self._serial = serial

        self.resistance = 0.0  # Last resistance reading in Ohms
        self.bands = []        # Last computed color band list

    def update(self, dt: float) -> None:
        """Poll the meter and forward the reading over serial.

        Args:
            dt: Elapsed seconds since last frame (not used directly here).
        """
        self.resistance = self._meter.read()
        self._serial.send_measurement(self.resistance, self.bands)

    def draw(self) -> None:
        """Render the current resistance onto the surface."""
        self._surface.fill((0, 0, 0))

    def handle_event(self, event) -> None:
        """No-op: this screen has no interactive elements yet."""
        pass

    def on_enter(self) -> None:
        """Called when this screen becomes active."""
        pass

    def on_exit(self) -> None:
        """Called when this screen is deactivated."""
        pass


# ---------------------------------------------------------------------------
# Standalone preview
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from unittest.mock import MagicMock

    pygame.init()
    screen = pygame.display.set_mode((480, 320))
    pygame.display.set_caption("Live Lab - preview")
    clock = pygame.time.Clock()

    meter = MagicMock()
    meter.read.return_value = 4700.0
    serial = MagicMock()

    live_lab = ScreenLiveLab(screen, meter, serial)

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            live_lab.handle_event(event)
        live_lab.update(dt)
        live_lab.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()
