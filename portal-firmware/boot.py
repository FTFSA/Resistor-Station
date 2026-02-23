"""
Portal M4 Boot Configuration
Enables the secondary USB CDC serial port so the Pi can send data to the Portal.
Must run before code.py; CircuitPython executes boot.py first at startup.
"""
import usb_cdc

usb_cdc.enable(data=True)
