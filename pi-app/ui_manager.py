"""
Resistor Station - Pygame Display Manager
Manages screen transitions, nav bar, and the main render loop.
"""


class UIManager:
    """Manages registered screens and dispatches events, updates, and draws.

    Screens are registered by name and activated via switch_to().  Only the
    active screen receives update() and draw() calls.  handle_event() is also
    forwarded exclusively to the active screen.

    Args:
        surface: A pygame.Surface (480x320) that screens render onto.
    """

    def __init__(self, surface):
        self._surface = surface
        self._screens = {}   # name -> screen object
        self._active = None  # name of the currently active screen

    # ------------------------------------------------------------------
    # Screen registry
    # ------------------------------------------------------------------

    def register_screen(self, name: str, screen) -> None:
        """Add a screen to the registry under the given name.

        Args:
            name:   Unique string key for the screen (e.g. 'live_lab').
            screen: An object implementing the Screen interface contract
                    (update, draw, handle_event).
        """
        self._screens[name] = screen

    def switch_to(self, name: str) -> None:
        """Activate the named screen.

        Args:
            name: Key previously passed to register_screen().

        Raises:
            KeyError: If name has not been registered.
        """
        if name not in self._screens:
            raise KeyError(f"Unknown screen: {name!r}")
        self._active = name

    # ------------------------------------------------------------------
    # Main-loop hooks
    # ------------------------------------------------------------------

    def handle_event(self, event) -> None:
        """Forward a pygame event to the active screen (if any)."""
        if self._active is not None:
            self._screens[self._active].handle_event(event)

    def update(self, dt: float) -> None:
        """Advance the active screen by dt seconds.

        Args:
            dt: Elapsed time in seconds since the last frame.
        """
        if self._active is not None:
            self._screens[self._active].update(dt)

    def draw(self) -> None:
        """Render the active screen onto the surface."""
        if self._active is not None:
            self._screens[self._active].draw()
