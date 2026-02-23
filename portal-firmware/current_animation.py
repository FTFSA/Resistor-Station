"""
Portal M4 - Current Flow Animation on LED Matrix

Animates 8 particles flowing clockwise around the circuit loop drawn
by matrix_display.draw_circuit_layout().  All state is pre-allocated at
module level; update() is fully non-blocking.

Path layout (clockwise):
  Segment 0 — top wire:    y=4,  x= 6..60   (55 steps, indices 0..54)
  Segment 1 — right side:  x=61, y= 5..26   (22 steps, indices 55..76)
  Segment 2 — bottom wire: y=27, x=60..6    (55 steps, indices 77..131)
  Segment 3 — left side:   x=2,  y=26..5    (22 steps, indices 132..153)

Total path length: 154 steps.

Resistor zone: top-wire steps where x=47..57 → path indices 41..51.
"""

import time
from matrix_display import set_pixel, refresh, COLOR

# ---------------------------------------------------------------------------
# Path construction — done once at module level, result is an immutable tuple
# ---------------------------------------------------------------------------

def _build_path():
    """Return the 154-step circuit loop as a tuple of (x,y) pairs."""
    coords = []

    # Segment 0: top wire, left→right, y=4, x=6..60
    for x in range(6, 61):
        coords.append((x, 4))

    # Segment 1: right vertical, top→bottom, x=61, y=5..26
    for y in range(5, 27):
        coords.append((61, y))

    # Segment 2: bottom wire, right→left, y=27, x=60..6
    for x in range(60, 5, -1):
        coords.append((x, 27))

    # Segment 3: left vertical, bottom→top, x=2, y=26..5
    for y in range(26, 4, -1):
        coords.append((2, y))

    return tuple(coords)


PATH = _build_path()
PATH_LEN = len(PATH)   # 154

# Resistor zone: top-wire steps covering x=47..57 (path indices 41..51)
_RESISTOR_START = 41
_RESISTOR_END   = 51   # inclusive

NUM_PARTICLES = 8

# Spacing: evenly distribute particles around the full loop
_PARTICLE_SPACING = PATH_LEN // NUM_PARTICLES   # 19


# ---------------------------------------------------------------------------
# Helper — inline to avoid function-call overhead in hot path
# ---------------------------------------------------------------------------

def _in_resistor_zone(idx):
    """Return True if path index idx falls within the resistor zone."""
    return _RESISTOR_START <= idx <= _RESISTOR_END


# ---------------------------------------------------------------------------
# Pre-allocated module-level state for idle animation
# ---------------------------------------------------------------------------

_idle_pos  = 0                     # single dot position (path index)
_idle_last = 0.0                   # last idle advance timestamp
_IDLE_INTERVAL = 0.08              # seconds between idle steps


# ---------------------------------------------------------------------------
# CurrentAnimation class
# ---------------------------------------------------------------------------

class CurrentAnimation:
    """State machine driving 8 particles around a circuit loop on the matrix."""

    def __init__(self):
        """Initialise particle positions evenly spaced; animation starts stopped."""
        # Fixed-size list of ints — allocated once, mutated in-place forever
        self._pos = [i * _PARTICLE_SPACING for i in range(NUM_PARTICLES)]

        # Fractional-step accumulators — one per particle, pre-allocated
        self._accum = [0.0] * NUM_PARTICLES

        self._speed  = 0.0            # steps per second
        self._last_t = time.monotonic()
        self._active = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_current(self, amps):
        """Map amps → particle speed (steps/sec). Clamps to [0, 0.5] A."""
        if amps < 0.0:
            amps = 0.0
        elif amps > 0.5:
            amps = 0.5

        if amps <= 0.0:
            self._speed  = 0.0
            self._active = False
        else:
            # 0.001 A → 20 steps/sec,  0.5 A → 120 steps/sec  (linear, clamped)
            raw = amps * 12000.0
            if raw < 20.0:
                raw = 20.0
            elif raw > 120.0:
                raw = 120.0
            self._speed  = raw
            self._active = True

    def update(self):
        """Advance animation one non-blocking step. Erase, move, redraw."""
        now = time.monotonic()
        dt  = now - self._last_t
        self._last_t = now

        if not self._active:
            return

        # Guard against very large dt (e.g. first call after long pause)
        if dt > 0.1:
            dt = 0.1

        # --- Erase old positions ----------------------------------------
        for i in range(NUM_PARTICLES):
            ox, oy = PATH[self._pos[i]]
            set_pixel(ox, oy, COLOR['black'])

        # --- Advance positions ------------------------------------------
        step_delta = self._speed * dt
        for i in range(NUM_PARTICLES):
            self._accum[i] += step_delta
            steps = int(self._accum[i])
            if steps > 0:
                self._pos[i] = (self._pos[i] + steps) % PATH_LEN
                self._accum[i] -= steps   # keep only fractional remainder

        # --- Draw new positions -----------------------------------------
        for i in range(NUM_PARTICLES):
            idx  = self._pos[i]
            x, y = PATH[idx]
            col  = COLOR['orange'] if _in_resistor_zone(idx) else COLOR['cyan']
            set_pixel(x, y, col)

        refresh()

    def idle_animation(self):
        """Single pulsing dot on top wire for 'no resistor connected' state.

        Designed to be called once per main-loop iteration; advances by one
        step only when the internal idle timer fires.
        """
        global _idle_pos, _idle_last

        now = time.monotonic()
        if now - _idle_last < _IDLE_INTERVAL:
            return
        _idle_last = now

        # Erase previous dot
        ox, oy = PATH[_idle_pos]
        set_pixel(ox, oy, COLOR['black'])

        # Only roam the top-wire segment (indices 0..54)
        _idle_pos = (_idle_pos + 1) % 55

        # Draw new dot in dim_white
        nx, ny = PATH[_idle_pos]
        set_pixel(nx, ny, COLOR['dim_white'])

        refresh()

    def stop(self):
        """Erase all particles and halt animation."""
        for i in range(NUM_PARTICLES):
            ox, oy = PATH[self._pos[i]]
            set_pixel(ox, oy, COLOR['black'])
        self._speed  = 0.0
        self._active = False
        refresh()
