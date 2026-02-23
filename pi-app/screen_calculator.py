"""
Resistor Station - Resistor Calculator Screen
Enter a target resistance, display nearest E24 value and color bands.
"""

import pygame

# These are imported at module level so tests can patch them via
# patch("screen_calculator.snap_to_e24") and patch("screen_calculator.resistance_to_bands").
from color_code import snap_to_e24, resistance_to_bands


class ScreenCalculator:
    """Resistor value calculator screen.

    Accepts keyboard digit input, snaps the entered value to the nearest E24
    series value (rounding up for safety), and looks up the corresponding
    resistor color bands.

    Args:
        surface: pygame.Surface to render onto (480x320).
    """

    def __init__(self, surface):
        self._surface = surface
        self.input_buffer = ""    # Digits typed by the user (string)
        self._result_bands = []   # Color bands from last calculation
        self._result_value = None # Snapped E24 value from last calculation

    def update(self, dt: float) -> None:
        """No-op: this screen has no time-based animation."""
        pass

    def draw(self) -> None:
        """Render the calculator UI onto the surface."""
        self._surface.fill((0, 0, 0))

    def handle_event(self, event) -> None:
        """Process keyboard input for the calculator.

        Handles:
        - K_BACKSPACE: remove the last character from input_buffer.
        - K_RETURN:    parse buffer as float, snap to E24, look up color bands.
        - Digit chars: append to input_buffer.
        - Everything else: ignored.

        Args:
            event: A pygame event object.
        """
        if event.type != pygame.KEYDOWN:
            return

        # Check special keys first (before inspecting unicode) so that
        # K_BACKSPACE is handled even when event.unicode is empty.
        if event.key == pygame.K_BACKSPACE:
            self.input_buffer = self.input_buffer[:-1]
            return

        if event.key == pygame.K_RETURN:
            if self.input_buffer:
                try:
                    value = float(self.input_buffer)
                    snapped = snap_to_e24(value)
                    self._result_value = snapped
                    self._result_bands = resistance_to_bands(snapped)
                except ValueError:
                    pass  # Malformed buffer — silently ignore
            return

        # Digit (and only digit) characters are appended to the buffer.
        if event.unicode.isdigit():
            self.input_buffer += event.unicode

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
    pygame.display.set_caption("Calculator - preview")
    clock = pygame.time.Clock()

    calc = ScreenCalculator(screen)

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            calc.handle_event(event)
        calc.update(dt)
        calc.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()
