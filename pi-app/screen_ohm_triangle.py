"""
Resistor Station - Ohm's Law Triangle Screen
Interactive V=IR triangle: tap a segment to solve for that variable.
"""

import pygame


class ScreenOhmTriangle:
    """Ohm's Law interactive triangle screen.

    Provides a calculate() method to solve for V, I, or R given the other two
    values, and a basic draw() implementation that fills the surface.

    Args:
        surface: pygame.Surface to render onto (480x320).
    """

    def __init__(self, surface):
        self._surface = surface

    def update(self, dt: float) -> None:
        """No-op: this screen animates on user interaction only."""
        pass

    def draw(self) -> None:
        """Render the Ohm's Law triangle onto the surface."""
        self._surface.fill((0, 0, 0))

    def handle_event(self, event) -> None:
        """Handle touch/click events on the triangle segments."""
        pass

    def calculate(self, solve_for: str, **kwargs) -> float:
        """Solve Ohm's Law for the requested variable.

        Args:
            solve_for: One of 'V', 'I', or 'R'.
            **kwargs:  The two known values as keyword arguments:
                       - 'V' (volts), 'I' (amps), 'R' (ohms).

        Returns:
            The computed value as a float.

        Raises:
            ZeroDivisionError: If a divisor is zero.
            ValueError:        If solve_for is not 'V', 'I', or 'R'.
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
            raise ValueError(f"Unknown variable to solve for: {solve_for!r}. "
                             f"Expected 'V', 'I', or 'R'.")

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

    pygame.init()
    screen = pygame.display.set_mode((480, 320))
    pygame.display.set_caption("Ohm Triangle - preview")
    clock = pygame.time.Clock()

    ohm = ScreenOhmTriangle(screen)

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            ohm.handle_event(event)
        ohm.update(dt)
        ohm.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()
