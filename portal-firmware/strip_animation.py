"""
Portal M4 - NeoPixel Strip Animation

Animates a NeoPixel strip to visualise electron flow.  Color transitions
from blue (low current) to orange (high / full-scale current).  Lit pixels
chase along the strip at a speed and density that both increase with current.

All mutable state is pre-allocated in __init__; update() is non-blocking.

Public API
----------
    strip = StripAnimation(num_pixels=30)
    strip.set_current(amps)   # update target current; clamps to [0, 0.5 A]
    strip.update()            # advance one animation step and write to strip
    strip.off()               # fill black, show, reset phase
"""

import neopixel
import pins

# Full-scale reference current (3.3 V / 100 Ohm = 0.033 A)
_FULL_SCALE_AMPS = 0.033

# Maximum current accepted by set_current()
_MAX_AMPS = 0.5

# Number of lit "electron" pixels active at once
_NUM_DOTS = 4

# Default spacing between lit pixels (shrinks as current rises)
_SPACING_MAX = 10   # low current  — electrons are sparse
_SPACING_MIN = 4    # full current — electrons are dense


class StripAnimation:
    """Flowing electron animation on the NeoPixel strip."""

    def __init__(self, num_pixels=30):
        """Initialise NeoPixel strip and pre-allocate animation state."""
        try:
            self._strip = neopixel.NeoPixel(
                pins.NEOPIXEL_PIN,
                num_pixels,
                auto_write=False,
                brightness=0.3,
            )
        except Exception as e:
            print("StripAnimation: NeoPixel init failed: %s" % str(e))
            self._strip = None

        self._num_pixels = num_pixels
        self._amps = 0.0
        self._phase = 0   # integer 0..num_pixels-1; advances each update()

        # Pre-allocate the RGB tuple that is reused for every lit pixel.
        # _color is a plain list [r, g, b] — mutated in-place by _compute_color().
        self._color = [0, 0, 0]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_current(self, amps):
        """Store target current; clamps to [0, _MAX_AMPS]."""
        if amps < 0.0:
            amps = 0.0
        elif amps > _MAX_AMPS:
            amps = _MAX_AMPS
        self._amps = amps

    def update(self):
        """Advance animation one step and push to strip; non-blocking."""
        if self._strip is None:
            return

        amps = self._amps
        num  = self._num_pixels

        # -- Speed: 1 step (near 0 A) up to 8 steps (full scale) --
        step = int(amps * 200)
        if step < 1:
            step = 1
        elif step > 8:
            step = 8

        self._phase = (self._phase + step) % num

        # -- Color: blue (0 A) -> orange (>= _FULL_SCALE_AMPS) --
        self._compute_color(amps)
        r = self._color[0]
        g = self._color[1]
        b = self._color[2]
        lit_color   = (r, g, b)
        black       = (0, 0, 0)

        # -- Spacing: _SPACING_MAX (0 A) -> _SPACING_MIN (full scale) --
        t = amps / _FULL_SCALE_AMPS
        if t > 1.0:
            t = 1.0
        # Integer interpolation — no float in hot path
        spacing = _SPACING_MAX - int(t * (_SPACING_MAX - _SPACING_MIN))

        # -- Write pixels --
        strip  = self._strip
        phase  = self._phase

        for px in range(num):
            # A pixel is lit if (px - phase) mod spacing == 0
            dist = (px - phase) % spacing
            strip[px] = lit_color if dist == 0 else black

        strip.show()

    def idle_update(self):
        """Single dim blue dot drifts along the strip; call in idle state."""
        if self._strip is None:
            return
        strip = self._strip
        num = self._num_pixels
        self._phase = (self._phase + 1) % num
        for px in range(num):
            if px == self._phase:
                strip[px] = (0, 0, 40)
            else:
                strip[px] = (0, 0, 0)
        strip.show()

    def off(self):
        """Fill strip with black, push immediately, and reset phase."""
        if self._strip is None:
            return
        self._strip.fill((0, 0, 0))
        self._strip.show()
        self._phase = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_color(self, amps):
        """Interpolate color from blue to orange; mutate self._color in place."""
        t = amps / _FULL_SCALE_AMPS
        if t > 1.0:
            t = 1.0

        # t is a float 0..1; convert to integer 0..256 for fixed-point blend
        t256 = int(t * 256)
        inv  = 256 - t256

        # Blue  = (  0,   0, 255)
        # Orange = (255, 100,   0)
        self._color[0] = (255 * t256) >> 8          # 0   -> 255
        self._color[1] = (100 * t256) >> 8          # 0   -> 100
        self._color[2] = (255 * inv)  >> 8          # 255 -> 0
