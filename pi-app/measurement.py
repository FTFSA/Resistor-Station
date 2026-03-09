from __future__ import annotations

"""
Resistor Station - Arduino Serial Measurement

Reads an ADC ratio from an Arduino connected via USB serial. The Arduino
performs the ADC reading and sends the ratio (0.0–1.0) over serial as:

    A:<ratio>\n

Example:
    A:0.0909\n

The ratio equals Vmid/VCC, which is independent of the actual supply voltage.
The Pi computes the unknown resistance from the voltage-divider formula:

    VCC → R_known (10kΩ) → [midpoint] → R_unknown → GND
    ratio = R_unknown / (R_known + R_unknown)
    R_unknown = R_known × ratio / (1 - ratio)

Hardware:
    - Arduino Uno connected via USB → /dev/ttyUSB0 or /dev/ttyACM*
    - Arduino reads ADC and sends ratio lines at 115200 baud

Dependencies:
    pyserial
"""

import logging
import math
import time
from typing import Optional

import serial

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

R_KNOWN: float = 10_000.0  # Known series resistor (ohms)
SHORT_THRESHOLD: float = 0.006  # Ratios below this → short circuit
OPEN_THRESHOLD: float = 0.98   # Ratios above this → open circuit

# E24 series base mantissas (one decade, 1.0 – 9.1)
_E24_BASE = [
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0,
    2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3,
    4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
]

# Pre-computed full E24 table from 1 Ω (10^0) through 10 MΩ (10^7).
_E24_TABLE: list[float] = []
for _exp in range(7):
    _decade = 10 ** _exp
    for _base in _E24_BASE:
        _E24_TABLE.append(round(_base * _decade, 10))
_E24_TABLE.append(10_000_000.0)


# ---------------------------------------------------------------------------
# Module-level snap_to_e24 — importable by color_code.py and others
# ---------------------------------------------------------------------------

def snap_to_e24(ohms: float) -> float:
    """Return the nearest E24 standard resistance value for *ohms*.

    Uses logarithmic (ratio-based) distance so that matching is proportionally
    correct across all decades.

    Range: 1 Ω – 10 MΩ.
      - ohms <= 0      → returns 1.0
      - ohms > 10 MΩ   → returns 10_000_000.0
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
    """Measures an unknown resistance by reading ADC ratio from an Arduino over USB serial.

    The Arduino reads its ADC and sends lines in the format ``A:<ratio>\\n``
    where ratio is ADC_value / 1023 (0.0 to 1.0). This equals Vmid/VCC,
    making the measurement independent of the actual supply voltage.

    Args:
        port:    Serial device path for the Arduino (e.g. '/dev/ttyUSB0').
        baud:    Baud rate (must match Arduino sketch, default 115200).
        r_known: Reference resistor value in ohms (default 10000.0).
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baud: int = 115200,
        r_known: float = R_KNOWN,
    ) -> None:
        self.r_known = r_known
        self._port = port
        self._baud = baud

        self._ser: Optional[serial.Serial] = None
        self._last_ratio: Optional[float] = None

        self._open_port()

    def _open_port(self) -> None:
        """Open the Arduino serial port."""
        try:
            self._ser = serial.Serial(
                self._port,
                self._baud,
                timeout=0.1,
            )
            # Arduino resets on serial open — give it time to start sending
            time.sleep(2.0)
            # Flush any startup garbage
            self._ser.reset_input_buffer()
            log.info("Arduino connected on %s at %d baud", self._port, self._baud)
        except (serial.SerialException, FileNotFoundError, OSError) as exc:
            self._ser = None
            raise RuntimeError(f"Cannot open Arduino on {self._port}: {exc}") from exc

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def read_ratio(self) -> Optional[float]:
        """Read the latest ADC ratio from the Arduino.

        Drains all available lines from the serial buffer and returns the
        most recent valid ``A:<float>`` value. This ensures we always use
        the freshest reading without blocking.

        Returns:
            ADC ratio (0.0–1.0) as a float, or None if no valid reading.
        """
        if self._ser is None or not self._ser.is_open:
            return None

        latest = None
        try:
            while self._ser.in_waiting:
                line = self._ser.readline().decode("utf-8", errors="ignore").strip()
                if line.startswith("A:"):
                    try:
                        latest = float(line[2:])
                    except ValueError:
                        pass
        except (serial.SerialException, OSError) as exc:
            log.warning("Arduino read error: %s", exc)
            return self._last_ratio

        if latest is not None:
            self._last_ratio = latest

        return self._last_ratio

    def measure(self) -> dict | None:
        """Measure the unknown resistance and return a result dictionary.

        Reads the latest ADC ratio from the Arduino and computes resistance:
            R_unknown = R_known × ratio / (1 - ratio)

        Returns:
            dict with keys:
                'status'             – 'present', 'short', or 'open'
                'resistance'         – raw calculated resistance (float, ohms)
                'standard_resistance'– nearest E24 value (float, ohms)
                'current'            – circuit current (float, amps)
                'ratio'              – ADC ratio Vmid/VCC (float, 0–1)
                'value_string'       – human-readable label e.g. '4.7kΩ'
            Returns only {'status': 'short'} or {'status': 'open'} for those
            conditions.  Returns None if no reading is available.
        """
        ratio = self.read_ratio()
        if ratio is None:
            return None

        if ratio < SHORT_THRESHOLD:
            return {"status": "short"}

        if ratio > OPEN_THRESHOLD:
            return {"status": "open"}

        denom = 1.0 - ratio
        if denom <= 0:
            return {"status": "open"}

        r_unknown = self.r_known * ratio / denom
        standard = self.snap_to_e24(r_unknown)
        # Estimate voltage/current using nominal 5V for UI display
        voltage = 5.0 * ratio
        current = 5.0 / (self.r_known + r_unknown)

        return {
            "status": "present",
            "resistance": r_unknown,
            "standard_resistance": standard,
            "current": current,
            "voltage": voltage,
            "ratio": ratio,
            "value_string": self.format_value(standard),
        }

    def is_present(self) -> bool:
        """Return True if a resistor appears to be inserted.

        Uses the most recent cached ratio for speed (no serial read).
        """
        r = self._last_ratio
        if r is None:
            return False
        return SHORT_THRESHOLD < r < OPEN_THRESHOLD

    def snap_to_e24(self, ohms: float) -> float:
        """Return the nearest E24 standard value for *ohms*."""
        return snap_to_e24(ohms)

    def format_value(self, ohms: float) -> str:
        """Format a resistance value as a human-readable string.

        Rules:
            >= 1_000_000 → MΩ  (e.g. '1MΩ', '2.2MΩ')
            >=     1_000 → kΩ  (e.g. '4.7kΩ', '27kΩ')
            <      1_000 → Ω   (e.g. '330Ω', '100Ω')
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

        formatted = f"{scaled:.1f}"
        if formatted.endswith(".0"):
            formatted = formatted[:-2]

        return f"{formatted}{unit}"

    def close(self) -> None:
        """Close the Arduino serial port."""
        if self._ser is not None:
            try:
                self._ser.close()
                log.info("Arduino serial port closed")
            except serial.SerialException:
                pass
            self._ser = None
