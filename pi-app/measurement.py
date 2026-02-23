from __future__ import annotations

"""
Resistor Station - ADC Reading and Resistance Calculation

Reads voltage from ADS1115 (16-bit ADC) over I2C and computes the unknown
resistance in a voltage-divider circuit:

    3.3V → R_known (10kΩ) → ADS1115 A0 → R_unknown → GND

Formula (verified, ±1.1% accuracy):
    R_unknown = R_known × Vmid / (Vin - Vmid)

Hardware:
    - Raspberry Pi 4
    - ADS1115 at I2C address 0x48 (SDA=GPIO2, SCL=GPIO3)
    - Gain = 1  →  ±4.096 V full-scale (covers 0–3.3 V)

Dependencies:
    adafruit-circuitpython-ads1x15
    adafruit-blinka
"""

import math

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

VREF: float = 3.3          # Supply / reference voltage (volts)
R_KNOWN: float = 10_000.0  # Known series resistor (ohms)
SHORT_THRESHOLD: float = 0.03   # Voltages below this → short circuit
OPEN_THRESHOLD: float = 3.20    # Voltages above this → open circuit

# E24 series base mantissas (one decade, 1.0 – 9.1)
_E24_BASE = [
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0,
    2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3,
    4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
]

# Pre-computed full E24 table from 1 Ω (10^0) through 10 MΩ (10^7).
# Decade exponents 0..6 give values 1 Ω → 9.1 MΩ; we cap at 10 MΩ.
_E24_TABLE: list[float] = []
for _exp in range(7):          # 10^0 = 1, 10^6 = 1_000_000
    _decade = 10 ** _exp
    for _base in _E24_BASE:
        _E24_TABLE.append(round(_base * _decade, 10))
_E24_TABLE.append(10_000_000.0)  # explicit 10 MΩ cap sentinel


# ---------------------------------------------------------------------------
# Module-level snap_to_e24 — importable by color_code.py and others
# ---------------------------------------------------------------------------

def snap_to_e24(ohms: float) -> float:
    """Return the nearest E24 standard resistance value for *ohms*.

    Uses logarithmic (ratio-based) distance so that matching is proportionally
    correct across all decades — a 5 % ratio error at 100 Ω is treated the
    same as a 5 % ratio error at 100 kΩ.

    Range: 1 Ω – 10 MΩ.
      - ohms <= 0      → returns 1.0
      - ohms > 10 MΩ   → returns 10_000_000.0

    Args:
        ohms: Resistance in ohms to snap.

    Returns:
        Nearest E24 standard value as a float.
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


# ---------------------------------------------------------------------------
# ResistanceMeter class
# ---------------------------------------------------------------------------

class ResistanceMeter:
    """Measures an unknown resistance using a voltage-divider and ADS1115 ADC.

    Circuit:
        3.3V → R_known → [A0 node] → R_unknown → GND

    The midpoint voltage at A0 is read via the ADS1115 over I2C; the unknown
    resistance is calculated from the voltage-divider formula.

    Args:
        i2c_address: I2C address of the ADS1115 (default 0x48).
        r_known:     Reference resistor value in ohms (default 10000.0).
        v_in:        Supply voltage in volts (default 3.3).
    """

    def __init__(
        self,
        i2c_address: int = 0x48,
        r_known: float = R_KNOWN,
        v_in: float = VREF,
    ) -> None:
        self.r_known = r_known
        self.v_in = v_in

        # Import hardware libraries here so that the module can be imported on
        # non-Pi hosts (e.g. for unit testing with mocks) without raising an
        # ImportError at module load time.
        import board
        import busio
        import adafruit_ads1x15.ads1115 as ADS
        from adafruit_ads1x15.analog_in import AnalogIn

        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c, address=i2c_address)
        ads.gain = 1  # ±4.096 V full-scale — covers 0–3.3 V

        self._channel = AnalogIn(ads, ADS.P0)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def read_voltage(self, samples: int = 32) -> float:
        """Return a noise-filtered voltage reading from ADS1115 channel A0.

        Takes *samples* raw readings, sorts them, discards the lowest 4 and
        highest 4 (trimmed mean), and returns the mean of the remaining
        readings.  This rejects occasional ADC glitches and I2C errors that
        produce outlier values.

        Args:
            samples: Total number of samples to take (must be > 8).

        Returns:
            Trimmed-mean voltage in volts.
        """
        readings: list[float] = []
        for _ in range(samples):
            readings.append(self._channel.voltage)

        readings.sort()
        trimmed = readings[4:-4]  # discard lowest 4 and highest 4
        return sum(trimmed) / len(trimmed)

    def measure(self) -> dict | None:
        """Measure the unknown resistance and return a result dictionary.

        Reads the midpoint voltage, applies the voltage-divider formula, and
        snaps to the nearest E24 standard value.

        Returns:
            dict with keys:
                'status'             – 'present', 'short', or 'open'
                'resistance'         – raw calculated resistance (float, ohms)
                'standard_resistance'– nearest E24 value (float, ohms)
                'current'            – circuit current (float, amps)
                'voltage'            – measured midpoint voltage (float, volts)
                'value_string'       – human-readable label e.g. '4.7kΩ'
            Returns only {'status': 'short'} or {'status': 'open'} for those
            conditions.  Returns None if an unexpected hardware error occurs.
        """
        try:
            v = self.read_voltage()
        except Exception:
            return None

        if v < SHORT_THRESHOLD:
            return {"status": "short"}

        if v > OPEN_THRESHOLD:
            return {"status": "open"}

        # Guard against division by zero when Vmid ≈ Vin (should be caught by
        # OPEN_THRESHOLD, but defensive programming is warranted here because
        # the formula blows up asymptotically as v → v_in).
        denom = self.v_in - v
        if denom <= 0:
            return {"status": "open"}

        r_unknown = self.r_known * v / denom
        standard = self.snap_to_e24(r_unknown)
        current = self.v_in / (self.r_known + r_unknown)

        return {
            "status": "present",
            "resistance": r_unknown,
            "standard_resistance": standard,
            "current": current,
            "voltage": v,
            "value_string": self.format_value(standard),
        }

    def is_present(self) -> bool:
        """Return True if a resistor appears to be inserted.

        Takes a single (non-averaged) voltage reading for speed.  Suitable for
        polling in a UI loop to detect insertion/removal without the latency of
        32-sample averaging.

        Returns:
            True if the midpoint voltage is within the 'present' window.
        """
        try:
            v = self._channel.voltage
        except Exception:
            return False
        return SHORT_THRESHOLD < v < OPEN_THRESHOLD

    def snap_to_e24(self, ohms: float) -> float:
        """Return the nearest E24 standard value for *ohms*.

        Thin wrapper around the module-level :func:`snap_to_e24` function so
        that callers using a ``ResistanceMeter`` instance don't need to import
        the module-level function separately.

        Args:
            ohms: Resistance in ohms.

        Returns:
            Nearest E24 standard value as a float.
        """
        return snap_to_e24(ohms)

    def format_value(self, ohms: float) -> str:
        """Format a resistance value as a human-readable string.

        Rules:
            >= 1_000_000 → MΩ  (e.g. '1MΩ', '2.2MΩ')
            >=     1_000 → kΩ  (e.g. '4.7kΩ', '27kΩ')
            <      1_000 → Ω   (e.g. '330Ω', '100Ω')

        Trailing '.0' is stripped so '10.0kΩ' becomes '10kΩ'.

        Args:
            ohms: Resistance value in ohms (should be a standard E24 value).

        Returns:
            Formatted string with SI prefix and Ω symbol.
        """
        if ohms >= 1_000_000:
            scaled = ohms / 1_000_000
            unit = "MΩ"
        elif ohms >= 1_000:
            scaled = ohms / 1_000
            unit = "kΩ"
        else:
            scaled = ohms
            unit = "Ω"

        # Format with up to one decimal place, then strip trailing '.0'
        formatted = f"{scaled:.1f}"
        if formatted.endswith(".0"):
            formatted = formatted[:-2]

        return f"{formatted}{unit}"
