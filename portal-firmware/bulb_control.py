"""
Portal M4 - LED Bulb Control via DAC

Uses the SAMD51 true 12-bit DAC on A0 to set LED bulb brightness.
Current is mapped linearly to a 16-bit DAC value (0-65535).
Scale: 0 A -> 0, 0.033 A (3.3V / 100 Ohm) -> 65535 (full bright).
"""

import analogio
import pins

# Full-scale reference current (3.3 V / 100 Ohm = 0.033 A)
_FULL_SCALE_AMPS = 0.033

# Maximum 16-bit DAC value
_DAC_MAX = 65535


class BulbControl:
    """Controls LED bulb brightness through the SAMD51 DAC on board.A0."""

    def __init__(self):
        """Initialize AnalogOut on pins.BULB_DAC_PIN; start with output at 0."""
        try:
            self._dac = analogio.AnalogOut(pins.BULB_DAC_PIN)
            self._dac.value = 0
        except Exception as e:
            print("BulbControl: DAC init failed: %s" % str(e))
            self._dac = None

    def set_current(self, amps):
        """Set bulb brightness proportional to current; clamp to [0, 65535].

        Scale: 0 A -> DAC 0; 0.033 A -> DAC 65535 (full bright).
        Any current above the full-scale reference saturates at full brightness.
        """
        if self._dac is None:
            return

        if amps < 0.0:
            amps = 0.0

        # Normalise to [0.0, 1.0] — clamp at 1.0 for any over-range current
        t = amps / _FULL_SCALE_AMPS
        if t > 1.0:
            t = 1.0

        self._dac.value = int(t * _DAC_MAX)

    def off(self):
        """Set DAC output to 0 (bulb off)."""
        if self._dac is None:
            return
        self._dac.value = 0
