"""
Resistor Station - Pi App Configuration
"""

# I2C / ADC
I2C_ADDRESS_ADS = 0x48

# Serial connection to Portal M4
SERIAL_PORT = '/dev/ttyACM0'
SERIAL_BAUD = 115200

# Touchscreen display
SCREEN_W = 480
SCREEN_H = 320

# Voltage divider circuit
R_KNOWN = 10000.0   # Known resistor in voltage divider (ohms)
V_IN    = 3.3       # Supply voltage (volts)
