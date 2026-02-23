"""
Resistor Station - Portal M4 Main Entry Point
Controls 32x64 HUB75 LED matrix, NeoPixel strips, and LED bulb (DAC on A0).
Receives measurement data from Pi over USB CDC serial.
"""

# TODO: Import displayio, rgbmatrix, framebufferio for HUB75 matrix
# TODO: Import neopixel for strip animations
# TODO: Import analogio for DAC bulb control on pins.BULB_DAC_PIN
# TODO: Import usb_cdc for serial receive from Pi
# TODO: Import pins for pin assignments
# TODO: Initialize SerialReceiver, MatrixDisplay, StripAnimation, BulbControl
# TODO: Main loop:
#   TODO: Check for incoming serial packet from Pi
#   TODO: Parse measurement data and update matrix display
#   TODO: Animate NeoPixel strips based on current value
#   TODO: Set bulb brightness via DAC
#   TODO: Handle BUTTON_UP / BUTTON_DOWN for mode switching
