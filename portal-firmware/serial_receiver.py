"""
Portal M4 - USB Serial Receiver

Reads measurement packets from the Pi via the USB CDC data serial port
(usb_cdc.data, enabled by boot.py).

Packet format (ASCII, newline-terminated):
    R:<ohms>,<b1>,<b2>,<b3>,<b4>\\n

Example:
    R:4700.0,yellow,violet,red,gold\\n

IMPORTANT: boot.py must contain usb_cdc.enable(data=True) and the Portal
must be hard-reset (not just soft-reloaded) after any change to boot.py.
Without that call, usb_cdc.data is None and this module will not function.

CircuitPython constraints observed here:
- No threading; the main loop calls read_packet() each iteration.
- time.monotonic() is used (time.time() is not available).
- usb_cdc.data.in_waiting gives the byte count ready to read without
  blocking; we only request that many bytes so reads never stall.
- Memory is limited: the line buffer is cleared promptly after each
  complete packet.  If the buffer grows beyond a safety cap (e.g.
  because a newline is never delivered) it is discarded.
"""

import time

import usb_cdc

# Maximum bytes to accumulate before discarding the buffer.  A well-formed
# packet is at most ~60 bytes; 256 bytes gives plenty of headroom while
# protecting against runaway growth from a malfunctioning sender.
_MAX_BUFFER = 256


class SerialReceiver:
    """Non-blocking reader for Pi→Portal measurement packets.

    Typical usage inside the main CircuitPython loop::

        receiver = SerialReceiver()
        while True:
            packet = receiver.read_packet()
            if packet:
                display_resistance(packet['resistance'], packet['bands'])
    """

    def __init__(self) -> None:
        """Acquire a reference to the USB CDC data port.

        If usb_cdc.data is None it means boot.py did not enable the data
        port (or the Portal was soft-reloaded rather than hard-reset after a
        boot.py change).  The object is still created but read_packet() will
        always return None.
        """
        self._port = usb_cdc.data
        if self._port is None:
            print(
                "SerialReceiver: usb_cdc.data is None — "
                "ensure boot.py calls usb_cdc.enable(data=True) "
                "and the Portal has been hard-reset."
            )
        else:
            # Non-blocking: read() returns immediately with whatever bytes
            # are available (possibly zero).
            self._port.timeout = 0

        # Accumulate incoming bytes here until a newline arrives.
        self._buf = bytearray()

        # Time of the last successfully parsed packet, or None if we have
        # not yet received one.  Used by callers to detect connection loss.
        self.last_received_time = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_packet(self):
        """Read any available bytes and return a parsed packet if complete.

        Non-blocking.  Should be called frequently from the main loop.

        If the buffer contains multiple complete lines (e.g. because the
        loop was slow), the *most recent* line is parsed and earlier ones
        are discarded so stale data is never displayed.

        Returns:
            A dict with keys 'resistance' (float) and 'bands' (list of four
            strings) if a complete, valid packet was received, otherwise None.
        """
        if self._port is None:
            return None

        # Read only the bytes already in the OS buffer to avoid blocking.
        waiting = self._port.in_waiting
        if waiting > 0:
            self._buf.extend(self._port.read(waiting))

        # Safety valve: discard if the buffer grows unreasonably large
        # (indicates missing newlines or a badly misbehaving sender).
        if len(self._buf) > _MAX_BUFFER:
            print(
                "SerialReceiver: buffer overflow (%d bytes), discarding"
                % len(self._buf)
            )
            self._buf = bytearray()
            return None

        # Check for one or more complete lines.
        if b"\n" not in self._buf:
            return None

        # Split on newlines.  If multiple complete lines are present, keep
        # only the last one and discard earlier (stale) data.
        lines = self._buf.split(b"\n")
        # lines[-1] is everything after the final '\n' (may be empty or a
        # partial next line); keep it as the new buffer.
        self._buf = lines[-1]

        # Work backwards through complete lines to find the latest valid one.
        # "Complete lines" are all entries except the last (which is the
        # partial tail we just preserved).
        complete = lines[:-1]
        for raw in reversed(complete):
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            result = self._parse(line)
            if result is not None:
                self.last_received_time = time.monotonic()
                return result
            else:
                print("SerialReceiver: parse error on line: %r" % line)

        return None

    def is_connected(self):
        """Return True if a packet was received within the last 3 seconds."""
        if self.last_received_time is None:
            return False
        return (time.monotonic() - self.last_received_time) < 3.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse(self, line):
        """Parse a single packet line into a measurement dict.

        Expected format::

            R:<ohms>,<b1>,<b2>,<b3>,<b4>

        The leading "R:" prefix is validated; the resistance is converted to
        float; the four band names are returned as a list of strings.

        Args:
            line: Stripped text line (no trailing newline or whitespace).

        Returns:
            {'resistance': float, 'bands': [str, str, str, str]} on success,
            None on any format or value error.
        """
        try:
            if not line.startswith("R:"):
                return None

            payload = line[2:]  # strip "R:"
            parts = payload.split(",")

            # Expect exactly 5 fields: ohms + 4 band names.
            if len(parts) != 5:
                return None

            resistance = float(parts[0])
            bands = [parts[1], parts[2], parts[3], parts[4]]

            return {"resistance": resistance, "bands": bands}

        except (ValueError, IndexError):
            return None
