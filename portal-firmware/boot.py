"""
Portal M4 Boot Configuration
Enables the USB CDC data serial port so the Pi can send data to the Portal.
Must run before code.py; CircuitPython executes boot.py first at startup.

console=False disables the REPL serial port so the data port becomes the
only CDC device — it enumerates as /dev/ttyACM0 on the Pi, matching config.py.
To debug via REPL, temporarily change console=True (the data port will then
be /dev/ttyACM1 and config.py must match).
"""
import usb_cdc

usb_cdc.enable(console=False, data=True)
