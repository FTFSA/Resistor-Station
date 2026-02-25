from __future__ import annotations

"""
Resistor Station - Resistance to Color Band Conversion

Maps a resistance value to standard 4-band resistor color codes (E24 series).
All public functions return structured dicts so callers do not need to keep
their own color look-up tables.

Exports:
    snap_to_e24          – nearest E24 value by log-ratio distance
    resistance_to_bands  – resistance → list of 4 band dicts
    bands_to_description – band list → human-readable string
"""

import math

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Significant-digit and multiplier band colors (index == digit value).
BAND_COLORS: dict[int, dict] = {
    0: {"name": "Black",  "rgb": (0,   0,   0  )},
    1: {"name": "Brown",  "rgb": (139, 69,  19 )},
    2: {"name": "Red",    "rgb": (255, 0,   0  )},
    3: {"name": "Orange", "rgb": (255, 140, 0  )},
    4: {"name": "Yellow", "rgb": (255, 255, 0  )},
    5: {"name": "Green",  "rgb": (0,   200, 0  )},
    6: {"name": "Blue",   "rgb": (0,   0,   255)},
    7: {"name": "Violet", "rgb": (139, 0,   255)},
    8: {"name": "Gray",   "rgb": (128, 128, 128)},
    9: {"name": "White",  "rgb": (255, 255, 255)},
}

# Tolerance band colors (key == tolerance as a fraction, e.g. 0.05 = 5 %).
TOLERANCE_BANDS: dict[float, dict] = {
    0.05: {"name": "Gold",   "rgb": (255, 215, 0  )},
    0.10: {"name": "Silver", "rgb": (192, 192, 192)},
}

# E24 base mantissas for one decade (values in [1.0, 9.1]).
_E24_BASE: list[float] = [
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0,
    2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3,
    4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
]

# Pre-computed full E24 table: 1 Ω (10^0) through 9.1 MΩ, capped at 10 MΩ.
_E24_TABLE: list[float] = []
for _exp in range(7):          # exponents 0..6  →  decades 1, 10, …, 1 000 000
    _decade = 10 ** _exp
    for _base in _E24_BASE:
        _E24_TABLE.append(round(_base * _decade, 10))
_E24_TABLE.append(10_000_000.0)  # explicit 10 MΩ sentinel / cap


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_value(ohms: float) -> str:
    """Format *ohms* as a compact SI string (Ω / kΩ / MΩ), stripping '.0'."""
    if ohms >= 1_000_000:
        scaled, unit = ohms / 1_000_000, "MΩ"
    elif ohms >= 1_000:
        scaled, unit = ohms / 1_000, "kΩ"
    else:
        scaled, unit = ohms, "Ω"

    formatted = f"{scaled:.1f}"
    if formatted.endswith(".0"):
        formatted = formatted[:-2]
    return f"{formatted}{unit}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def snap_to_e24(ohms: float) -> float:
    """Return the nearest E24 standard resistance for *ohms* using log-ratio distance.

    Uses logarithmic (ratio-based) distance so that matching is proportionally
    correct across all decades.  Range is 1 Ω – 10 MΩ.

    Edge cases:
        ohms <= 0         → 1.0
        ohms > 10_000_000 → 10_000_000.0
    """
    if ohms <= 0:
        return 1.0
    if ohms > 10_000_000.0:
        return 10_000_000.0

    best_value = _E24_TABLE[0]
    best_log_dist = abs(math.log(ohms / _E24_TABLE[0]))

    for candidate in _E24_TABLE[1:]:
        log_dist = abs(math.log(ohms / candidate))
        if log_dist < best_log_dist:
            best_log_dist = log_dist
            best_value = candidate

    return best_value


def resistance_to_bands(ohms: float, tolerance: float = 0.05) -> list[dict]:
    """Convert *ohms* to a list of 4 band dicts (digit, name, rgb / tolerance).

    Snaps to the nearest E24 value first, so digit values are always clean.

    Band layout:
        [0] First significant digit
        [1] Second significant digit
        [2] Multiplier  (number of trailing zeros, 0–8)
        [3] Tolerance   (Gold = 5 %, Silver = 10 %)

    Each of bands 0–2 is:  {'digit': int, 'name': str, 'rgb': tuple}
    Band 3 is:             {'name': str, 'rgb': tuple, 'tolerance': float}
    """
    # --- edge-case clamping -------------------------------------------------
    if ohms <= 0:
        ohms = 1.0
    elif ohms > 10_000_000:
        ohms = 10_000_000.0

    # Snap to E24 so digits are always a clean pair from the series.
    ohms = snap_to_e24(ohms)

    # --- significant digits -------------------------------------------------
    # exponent such that 10^(exponent-1) <= ohms < 10^exponent.
    # mantissa = ohms / 10^(exponent-1)  is a 2-digit number in [10, 100).
    exponent = math.floor(math.log10(ohms))
    mantissa = ohms / (10 ** (exponent - 1))  # in [10.0, 100.0)

    mantissa_int = round(mantissa)
    digit1 = mantissa_int // 10
    digit2 = mantissa_int % 10

    # Clamp to valid digit range (defensive; E24 values never need this).
    digit1 = max(0, min(9, digit1))
    digit2 = max(0, min(9, digit2))

    # --- multiplier ---------------------------------------------------------
    # multiplier = number of trailing zeros = exponent - 1.
    multiplier = exponent - 1
    multiplier = max(0, min(8, multiplier))  # valid range for a 4-band code

    # --- tolerance ----------------------------------------------------------
    tol_info = TOLERANCE_BANDS.get(tolerance, TOLERANCE_BANDS[0.05])

    # --- assemble bands -----------------------------------------------------
    def _digit_band(digit: int) -> dict:
        return {
            "digit": digit,
            "name":  BAND_COLORS[digit]["name"],
            "rgb":   BAND_COLORS[digit]["rgb"],
        }

    band_multiplier: dict = {
        "digit": multiplier,
        "name":  BAND_COLORS[multiplier]["name"],
        "rgb":   BAND_COLORS[multiplier]["rgb"],
    }

    band_tolerance: dict = {
        "name":      tol_info["name"],
        "rgb":       tol_info["rgb"],
        "tolerance": tolerance if tolerance in TOLERANCE_BANDS else 0.05,
    }

    return [
        _digit_band(digit1),
        _digit_band(digit2),
        band_multiplier,
        band_tolerance,
    ]


def bands_to_description(bands: list[dict]) -> str:
    """Return a human-readable description of *bands*, e.g. 'Yellow-Violet-Red-Gold (4.7kΩ ±5%)'.

    Reconstructs the resistance from digit and multiplier bands, then formats
    it with SI prefix (Ω / kΩ / MΩ).
    """
    name_str = "-".join(b["name"] for b in bands)

    # Reconstruct ohms from the digit and multiplier bands.
    digit1     = bands[0]["digit"]
    digit2     = bands[1]["digit"]
    multiplier = bands[2]["digit"]
    ohms       = (digit1 * 10 + digit2) * (10 ** multiplier)

    value_str = _format_value(float(ohms))

    tol_pct = int(bands[3]["tolerance"] * 100)

    return f"{name_str} ({value_str} \u00b1{tol_pct}%)"


# ---------------------------------------------------------------------------
# Self-test (run with: python color_code.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cases = [
        (4700,   "Yellow-Violet-Red-Gold"),
        (330,    "Orange-Orange-Brown-Gold"),
        (10000,  "Brown-Black-Orange-Gold"),
        (100,    "Brown-Black-Brown-Gold"),
        (510000, "Green-Brown-Yellow-Gold"),    # was failing: float truncation
        (820000, "Gray-Red-Yellow-Gold"),       # was failing: float truncation
        (8200000,"Gray-Red-Green-Gold"),        # was failing: float truncation
    ]

    all_pass = True
    for ohms, expected_bands in cases:
        bands = resistance_to_bands(ohms)
        band_names = "-".join(b["name"] for b in bands)
        desc = bands_to_description(bands)
        status = "PASS" if band_names == expected_bands else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"{status}  {ohms:>10,}Ω  got={band_names!r:<40}  expected={expected_bands!r}")
        print(f"       description: {desc}")

    # Extra verification cases
    extra = [
        (1_000_000, "Brown-Black-Green-Gold"),
    ]
    for ohms, expected_bands in extra:
        bands = resistance_to_bands(ohms)
        band_names = "-".join(b["name"] for b in bands)
        desc = bands_to_description(bands)
        status = "PASS" if band_names == expected_bands else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"{status}  {ohms:>10,}Ω  got={band_names!r:<40}  expected={expected_bands!r}")
        print(f"       description: {desc}")

    print()
    print("All tests passed." if all_pass else "SOME TESTS FAILED.")
