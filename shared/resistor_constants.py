"""
Resistor Station - Shared Constants
Used by both pi-app (color_code.py) and portal-firmware (matrix_display.py).
"""

# E24 series standard resistor values (1-decade, multiply by power of 10)
E24_VALUES = [
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
    3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
]

# 4-band resistor color code: color name -> (digit value, RGB tuple)
COLOR_BANDS = {
    "black":  (0, (0,   0,   0  )),
    "brown":  (1, (139, 69,  19 )),
    "red":    (2, (220, 20,  20 )),
    "orange": (3, (255, 140, 0  )),
    "yellow": (4, (255, 220, 0  )),
    "green":  (5, (0,   160, 0  )),
    "blue":   (6, (0,   80,  200)),
    "violet": (7, (148, 0,   211)),
    "grey":   (8, (160, 160, 160)),
    "white":  (9, (255, 255, 255)),
    # Multiplier-only colors
    "gold":   (None, (212, 175, 55 )),  # x0.1
    "silver": (None, (192, 192, 192)),  # x0.01
}

# Tolerance band colors (4th band)
TOLERANCE_BANDS = {
    "brown":  1.0,   # ±1%
    "red":    2.0,   # ±2%
    "gold":   5.0,   # ±5%
    "silver": 10.0,  # ±10%
}
