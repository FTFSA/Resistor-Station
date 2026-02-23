# USB Serial Protocol — Agent Memory

## Packet format (locked)
```
R:<ohms>,<b1>,<b2>,<b3>,<b4>\n
```
- `<ohms>` formatted with `:.1f` on the Pi side (e.g. `4700.0`)
- `<b1>`..`<b4>` are lowercase colour-band name strings from `color_code.resistance_to_bands()`
- Always exactly 5 comma-separated fields after stripping the `R:` prefix
- See details.md for rationale

## File ownership
- Pi side:     `pi-app/serial_comms.py`       — `PortalSerial` class, pyserial
- Portal side: `portal-firmware/serial_receiver.py` — `SerialReceiver` class, usb_cdc
- Boot config: `portal-firmware/boot.py`      — must contain `usb_cdc.enable(data=True)`

## Port assignment
- Pi opens `/dev/ttyACM0` (default) or `/dev/ttyACM1` — the data CDC port
- Portal: `usb_cdc.data` is the secondary port enabled by boot.py (index 1)
- Hard reset required after any boot.py change (soft reload does NOT re-run boot.py)

## Key design decisions
- Reconnect cooldown: 2 seconds (avoids busy-loop when Portal is unplugged)
- Pi-side is NOT thread-safe by design; caller must serialise access
- Portal buffer cap: 256 bytes (discard on overflow; max packet ~60 bytes)
- Portal reads only `in_waiting` bytes per call — never blocks
- On multiple buffered lines, Portal parses the MOST RECENT and discards stale ones
- `is_connected()` on Portal: True if packet received within last 3.0 seconds

## See also
- `details.md` for deeper notes on CircuitPython constraints and reconnect patterns
