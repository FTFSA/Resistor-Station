"""
Portal M4 Pin Assignments
SAMD51 main processor pin definitions.
Note: A0 has a true 12-bit DAC (not PWM) on the SAMD51.
"""
import board

NEOPIXEL_PIN  = board.A1          # NeoPixel data out
BULB_DAC_PIN  = board.A0          # Analog out to LED bulb driver (true DAC)
BUTTON_UP     = board.BUTTON_UP   # Portal M4 onboard up button
BUTTON_DOWN   = board.BUTTON_DOWN # Portal M4 onboard down button
