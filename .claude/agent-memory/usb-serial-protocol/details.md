# USB Serial Protocol — Detailed Notes

## Packet format decisions

The format `R:<ohms>,<b1>,<b2>,<b3>,<b4>\n` was chosen over the system-prompt
spec (`R:<ohms>,I:<amps>,V:<volts>,S:<status>\n`) because the Portal display
needs colour-band names directly, not current/voltage.  The Pi does the
`color_code.resistance_to_bands()` call before sending.

Resistance uses `:.1f` formatting.  The Portal parser uses `float()` which
handles any float representation, so if the format ever changes to `:.2e` the
receiver does not need updating.

## CircuitPython usb_cdc notes

- `usb_cdc.data` is None if:
  a) boot.py was not run (soft Ctrl+D reload instead of hard reset), or
  b) boot.py does not call `usb_cdc.enable(data=True)`
- Setting `usb_cdc.data.timeout = 0` makes `read()` non-blocking
- `in_waiting` is the correct attribute to check bytes available (not `readable()`)
- `time.time()` is NOT available in CircuitPython; always use `time.monotonic()`

## Pi-side reconnect pattern

`_open_port()` catches `serial.SerialException`, `FileNotFoundError`, and
`OSError` (the latter covers permission denied and similar OS-level errors on
Linux).  `_reconnect()` enforces a 2-second cooldown so that a missing Portal
does not spin the CPU.  The cooldown timer is reset each attempt, not on
success, so repeated failures stay throttled.

`_write()` sets `self._ser = None` on SerialException (rather than calling
`_reconnect()` inline) so the main loop is not blocked mid-iteration.  The
reconnect happens at the top of the next `send_measurement()` call.

## Testing without hardware

Pi side: `PortalSerial` accepts any object with `.write()`, `.is_open`, and
`.close()` as its internal `_ser`.  You cannot pass it to `__init__` directly
(the constructor calls `serial.Serial()`), but you can:
  1. Instantiate with a bogus port (catches the exception, sets `_ser=None`)
  2. Assign a mock: `s._ser = MockSerial()`
Or patch `serial.Serial` in unit tests before construction.

Portal side: replace `usb_cdc.data` at the top of the module with a mock
object that exposes `.in_waiting`, `.read()`, and `.timeout` attributes.
