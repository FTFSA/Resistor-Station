"""
Resistor Station - Resistance to Color Band Conversion
Maps a resistance value to standard 4-band resistor color codes.
"""

import math
import sys
import os

# Allow running standalone or from within the pi-app directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from resistor_constants import E24_VALUES, COLOR_BANDS

# Ordered list of color names by digit value (index == digit)
_DIGIT_COLORS = [
    "black",   # 0
    "brown",   # 1
    "red",     # 2
    "orange",  # 3
    "yellow",  # 4
    "green",   # 5
    "blue",    # 6
    "violet",  # 7
    "grey",    # 8
    "white",   # 9
]

# Multiplier band: exponent -> color name
_MULTIPLIER_COLORS = {
    -2: "silver",   # x0.01
    -1: "gold",     # x0.1
     0: "black",    # x1
     1: "brown",    # x10
     2: "red",      # x100
     3: "orange",   # x1000
     4: "yellow",   # x10000
     5: "green",    # x100000
     6: "blue",     # x1000000
}


def snap_to_e24(resistance: float) -> float:
    """Return the smallest E24 standard value >= resistance.

    Rounds UP to the next E24 value for safety (never under-specifies).
    Handles the full range from sub-ohm to multi-megaohm values.
    """
    if resistance <= 0:
        return E24_VALUES[0]  # 1.0 Ohm minimum

    # Find the decade exponent so we can normalise to 1..10
    exponent = math.floor(math.log10(resistance))
    decade = 10 ** exponent
    normalised = resistance / decade  # value in [1.0, 10.0)

    # Find the first E24 mantissa that is >= normalised value
    for e24 in E24_VALUES:
        candidate = e24 * decade
        # Use a small epsilon to handle floating-point imprecision when the
        # input is already exactly an E24 value.
        if candidate >= resistance - 1e-9:
            return candidate

    # If we exhausted this decade, step up to the next one
    return E24_VALUES[0] * decade * 10


def resistance_to_bands(resistance: float) -> list:
    """Convert a resistance value to a list of four color name strings.

    Returns [digit1, digit2, multiplier, tolerance] where tolerance is always
    'gold' (±5%).  Assumes resistance is a positive E24 value.
    """
    if resistance <= 0:
        return ["black", "black", "black", "gold"]

    # Find the decade that gives us a two-digit mantissa in [10, 99]
    # e.g. 4700 -> mantissa=47, exponent=2 (multiplier=100)
    exponent = math.floor(math.log10(resistance)) - 1
    decade = 10 ** exponent
    mantissa = round(resistance / decade)  # should be in [10..99]

    # Handle edge cases where rounding pushes mantissa to 100
    if mantissa >= 100:
        mantissa = mantissa // 10
        exponent += 1
        decade = 10 ** exponent

    digit1 = mantissa // 10
    digit2 = mantissa % 10

    # Clamp digits to valid range
    digit1 = max(0, min(9, digit1))
    digit2 = max(0, min(9, digit2))

    multiplier_color = _MULTIPLIER_COLORS.get(exponent, "black")

    return [
        _DIGIT_COLORS[digit1],
        _DIGIT_COLORS[digit2],
        multiplier_color,
        "gold",  # ±5% tolerance
    ]


def bands_to_rgb(bands: list) -> list:
    """Map a list of color name strings to RGB tuples.

    Returns a list of (R, G, B) tuples, one per band.
    Unknown color names map to (128, 128, 128) gray.
    """
    result = []
    for name in bands:
        entry = COLOR_BANDS.get(name)
        if entry is not None:
            result.append(entry[1])
        else:
            result.append((128, 128, 128))
    return result
