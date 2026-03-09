"""
Resistor Station - Pi App Configuration
"""

# Arduino serial (measurement ADC)
ARDUINO_PORT = '/dev/ttyUSB0'
ARDUINO_BAUD = 115200

# Serial connection to Portal M4
SERIAL_PORT = '/dev/ttyACM0'
SERIAL_BAUD = 115200

# Touchscreen display
SCREEN_W = 480
SCREEN_H = 320

# Voltage divider circuit
R_KNOWN = 10000.0   # Known resistor in voltage divider (ohms)
V_IN    = 5.0       # Supply voltage (volts) — Arduino Uno 5V
