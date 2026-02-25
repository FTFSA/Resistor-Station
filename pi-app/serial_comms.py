"""
Resistor Station - USB Serial Communication to Portal M4

Sends measurement packets from the Pi to the Portal over /dev/ttyACM0 (or
/dev/ttyACM1) at 115200 baud.

Packet format (ASCII, newline-terminated):
    R:<ohms>,<b1>,<b2>,<b3>,<b4>\n

Example:
    R:4700.0,yellow,violet,red,gold\n

The four band names come from color_code.resistance_to_bands() and are sent
as plain lowercase strings.  The Portal parses them directly for display.

Threading note: PortalSerial is NOT thread-safe by design — the caller is
expected to serialise access (e.g. a single sender thread).  If multiple
threads need to send, wrap calls in an external threading.Lock.

Testing note: Pass a pre-opened mock object to the port parameter (anything
with .write() / .is_open / .close()) to test without hardware.  Alternatively
patch serial.Serial in unit tests.
"""

from __future__ import annotations
import glob

import logging
import time

import serial

log = logging.getLogger(__name__)


class PortalSerial:
    """Manages the USB serial connection from the Pi to the Portal M4.

    Usage::

        with PortalSerial() as s:
            s.send_measurement(4700.0, ['yellow', 'violet', 'red', 'gold'])
    """

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        baud: int = 115200,
        timeout: float = 1.0,
        write_timeout: float = 0.05,
    ) -> None:
        """Open the serial port.

        If the port cannot be opened (device not present, permission error,
        etc.) a warning is logged and self._ser is set to None.  The object
        is still usable — subsequent send calls will attempt a reconnect.

        Args:
            port:    Serial device path, e.g. '/dev/ttyACM0'.
            baud:    Baud rate; must match the Portal firmware (115200).
            timeout: Read timeout in seconds passed to serial.Serial.  Write
                     operations are effectively non-blocking for small packets,
                     but this is kept for consistency.
            write_timeout: Max seconds a write() call may block before raising
                     SerialTimeoutException. Keeps the UI loop responsive.
        """
        self._port = port
        self._configured_port = port
        self._baud = baud
        self._timeout = timeout
        self._write_timeout = write_timeout

        # Timestamp of the last reconnect *attempt* — used for cooldown.
        self._last_reconnect_attempt: float = 0.0
        # Minimum seconds to wait between reconnect attempts.
        self._reconnect_cooldown: float = 2.0

        self._ser: serial.Serial | None = None
        self._open_port()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_measurement(self, resistance: float, bands: list[str]) -> bool:
        """Send a resistance measurement packet to the Portal.

        Builds the packet::

            R:<ohms>,<b1>,<b2>,<b3>,<b4>\\n

        Args:
            resistance: Raw measured resistance in ohms (float).
            bands:      List of exactly four colour-band name strings,
                        e.g. ['yellow', 'violet', 'red', 'gold'].

        Returns:
            True if the packet was written successfully, False otherwise.
        """
        if not self.is_connected():
            log.debug("send_measurement: not connected, attempting reconnect")
            if not self._reconnect():
                return False

        packet = f"R:{resistance:.1f},{','.join(bands)}\n"
        return self._write(packet)

    def is_connected(self) -> bool:
        """Return True if the serial port is open and ready."""
        return self._ser is not None and self._ser.is_open

    def close(self) -> None:
        """Close the serial port and release the resource."""
        if self._ser is not None:
            try:
                if self._ser.is_open:
                    self._ser.close()
                    log.debug("Serial port %s closed", self._port)
            except serial.SerialException as exc:
                log.warning("Error closing serial port %s: %s", self._port, exc)
            finally:
                self._ser = None

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "PortalSerial":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_port(self) -> bool:
        """Try to open the serial port.  Returns True on success."""
        for candidate_port in self._candidate_ports():
            try:
                self._ser = serial.Serial(
                    candidate_port,
                    self._baud,
                    timeout=self._timeout,
                    write_timeout=self._write_timeout,
                )
                self._port = candidate_port
                log.info("Opened serial port %s at %d baud", self._port, self._baud)
                return True
            except (serial.SerialException, FileNotFoundError, OSError) as exc:
                log.warning(
                    "Could not open serial port %s: %s — Portal not connected?",
                    candidate_port,
                    exc,
                )

        self._ser = None
        return False

    def _reconnect(self) -> bool:
        """Attempt to reopen the serial port, respecting a cooldown period.

        Returns:
            True if the port is now open, False if the attempt failed or is
            still inside the cooldown window.
        """
        now = time.monotonic()
        if now - self._last_reconnect_attempt < self._reconnect_cooldown:
            log.debug(
                "Reconnect cooldown active (%.1fs remaining)",
                self._reconnect_cooldown - (now - self._last_reconnect_attempt),
            )
            return False

        self._last_reconnect_attempt = now
        log.info("Attempting to reconnect to %s …", self._port)

        # Close gracefully first so the OS releases the file descriptor.
        if self._ser is not None:
            try:
                self._ser.close()
            except serial.SerialException:
                pass
            self._ser = None

        success = self._open_port()
        if success:
            log.info("Reconnected to %s successfully", self._port)
        else:
            log.warning("Reconnect to %s failed", self._port)
        return success

    def _write(self, packet: str) -> bool:
        """Encode *packet* to UTF-8 and write it to the serial port.

        Args:
            packet: The fully-formed ASCII packet string including trailing
                    newline.

        Returns:
            True on success, False on serial error (triggers reconnect).
        """
        try:
            self._ser.write(packet.encode("utf-8"))
            log.debug("Sent: %r", packet.rstrip())
            return True
        except (serial.SerialException, serial.SerialTimeoutException) as exc:
            log.warning("Write failed on %s: %s", self._port, exc)
            self._ser = None
            # Schedule a reconnect on the next send attempt (do not block
            # here — the caller's main loop should continue unimpeded).
            return False

    def _candidate_ports(self) -> list[str]:
        """Return ordered candidate serial device paths."""
        candidates = [self._configured_port]
        patterns = [
            "/dev/ttyACM*",
            "/dev/ttyUSB*",
            "/dev/tty.usbmodem*",
            "/dev/tty.usbserial*",
            "/dev/cu.usbmodem*",
            "/dev/cu.usbserial*",
        ]
        for pattern in patterns:
            for path in sorted(glob.glob(pattern)):
                if path not in candidates:
                    candidates.append(path)
        return candidates
