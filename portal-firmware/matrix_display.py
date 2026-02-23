"""
Portal M4 - HUB75 32x64 LED Matrix Display Driver

Module-level init runs on import. Callers must not re-init hardware.
Exposes a flat pixel API (set_pixel, fill_rect, clear, refresh).

Palette layout (50 entries, bit_depth=3):
  0        : black (background)
  1-10     : electron blue, dim→bright
  11-20    : heated electron orange/red, dim→bright
  21       : resistor body base (cool dark green)
  22       : resistor body warmer
  23       : resistor edge
  24       : resistor cap
  25       : lead/terminal
  26-30    : resistor heat glow (increasing warmth)
  31-35    : heat particles (bright→dim)
  36       : wire base (dark blue-grey)
  37       : polarity marker (dim white-grey)
  38       : trail dim blue
  39       : trail dim orange
  40       : flow indicator (very dim blue)
  41-45    : blended electron colors (blue→orange transition)
  46-49    : spare black
"""

import board
import displayio
import framebufferio
import rgbmatrix

# ---------------------------------------------------------------------------
# Hardware init — runs once on import
# ---------------------------------------------------------------------------

displayio.release_displays()

mx = rgbmatrix.RGBMatrix(
    width=64,
    height=32,
    bit_depth=3,
    rgb_pins=[
        board.MTX_R1, board.MTX_G1, board.MTX_B1,
        board.MTX_R2, board.MTX_G2, board.MTX_B2,
    ],
    addr_pins=[
        board.MTX_ADDRA, board.MTX_ADDRB,
        board.MTX_ADDRC, board.MTX_ADDRD,
    ],
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE,
)

display = framebufferio.FramebufferDisplay(mx, auto_refresh=False)

# ---------------------------------------------------------------------------
# Palette — 50 entries, fixed at module level
# Indices match current_animation.py exactly; do not reorder.
# ---------------------------------------------------------------------------

NUM_COLORS = 50
palette = displayio.Palette(NUM_COLORS)

# 0: black
palette[0] = 0x000000

# 1-10: electron blue (dim to bright)
# Each step: r=20*(i+1)/10, g=80*(i+1)/10, b=255*(i+1)/10
palette[1]  = 0x020814   # 10%
palette[2]  = 0x041028   # 20%
palette[3]  = 0x06183D   # 30%
palette[4]  = 0x082051   # 40%
palette[5]  = 0x0A2866   # 50%
palette[6]  = 0x0C307A   # 60%
palette[7]  = 0x0E388E   # 70%
palette[8]  = 0x1040A3   # 80%
palette[9]  = 0x1248B7   # 90%
palette[10] = 0x1450CC   # 100% (brightest blue electron)

# 11-20: heated electron orange/red (dim to bright)
# Each step: r=255*(i+1)/10, g=80*(i+1)/10, b=20*(i+1)/10
palette[11] = 0x190802   # 10%
palette[12] = 0x330F03   # 20%
palette[13] = 0x4C1705   # 30%
palette[14] = 0x661F06   # 40%
palette[15] = 0x7F2808   # 50%
palette[16] = 0x993009   # 60%
palette[17] = 0xB2380B   # 70%
palette[18] = 0xCC400C   # 80%
palette[19] = 0xE6480E   # 90%
palette[20] = 0xFF5014   # 100% (brightest orange electron)

# 21: resistor body base
palette[21] = 0x283720
# 22: resistor body warmer
palette[22] = 0x3A3520
# 23: resistor edge
palette[23] = 0x282A1C
# 24: resistor cap
palette[24] = 0x1E261A
# 25: lead/terminal
palette[25] = 0x2D2D32

# 26-30: resistor heat glow (increasing warmth)
# t=(i+1)/5: r=35+t*140, g=50-t*25, b=30-t*18
palette[26] = 0x3B2F1C   # t=0.2
palette[27] = 0x5A2A16   # t=0.4
palette[28] = 0x792411   # t=0.6
palette[29] = 0x981E0B   # t=0.8
palette[30] = 0xB71906   # t=1.0

# 31-35: heat particles (bright to dim)
# bright=1-i*0.2: r=220*bright, g=60*bright, b=8*bright
palette[31] = 0xDC3C08   # 100%
palette[32] = 0xB03006   # 80%
palette[33] = 0x832405   # 60%
palette[34] = 0x571803   # 40%
palette[35] = 0x2A0C02   # 20%

# 36: wire base (dark blue-grey)
palette[36] = 0x121920
# 37: polarity marker (dim grey)
palette[37] = 0x303030
# 38: trail dim blue
palette[38] = 0x0A1830
# 39: trail dim orange
palette[39] = 0x301008
# 40: flow indicator (very dim blue)
palette[40] = 0x0C2038

# 41-45: blended electron transition (blue→orange)
# t=i/4: r=40*(1-t)+255*t, g=120*(1-t)+80*t, b=220*(1-t)+25*t
palette[41] = 0x2878DC   # t=0.0 (cool blue)
palette[42] = 0x5B7AAA   # t=0.25
palette[43] = 0x8E7C78   # t=0.5
palette[44] = 0xC17E46   # t=0.75
palette[45] = 0xFF5019   # t=1.0 (hot orange)

# 46-49: spare black
palette[46] = 0x000000
palette[47] = 0x000000
palette[48] = 0x000000
palette[49] = 0x000000

# ---------------------------------------------------------------------------
# Convenience name → index mapping for callers
# Maps legacy names to the closest palette entry.
# ---------------------------------------------------------------------------

COLOR = {
    'black':       0,
    'cyan':        10,   # brightest blue electron (was index 6)
    'orange':      20,   # brightest heated electron (was index 7)
    'wire':        36,   # wire base colour
    'polarity':    37,   # polarity marker
    'trail_blue':  38,
    'trail_orange': 39,
    'flow':        40,
    'blend_cool':  41,
    'blend_warm':  45,
    'res_body':    21,
    'res_edge':    23,
    'res_cap':     24,
    'res_lead':    25,
    'heat_glow_1': 26,
    'heat_glow_5': 30,
    'heat_p_bright': 31,
    'heat_p_dim':    35,
    # Legacy names kept for tiny_font.py compatibility
    'white':       37,   # closest available (dim grey used as white stand-in)
    'red':         20,   # hot orange doubles as red
    'green':       21,   # res_body green is closest
    'blue':        10,   # brightest blue
    'yellow':      45,   # warm blend
    'dark_green':  21,
    'dim_white':   37,
    'bright_cyan': 10,
    'pink':        35,
}

# ---------------------------------------------------------------------------
# Pixel buffer
# ---------------------------------------------------------------------------

bitmap = displayio.Bitmap(64, 32, NUM_COLORS)

# ---------------------------------------------------------------------------
# Display group
# ---------------------------------------------------------------------------

group = displayio.Group()
tile = displayio.TileGrid(bitmap, pixel_shader=palette)
group.append(tile)
display.root_group = group

# ---------------------------------------------------------------------------
# Pixel API
# ---------------------------------------------------------------------------

def set_pixel(x, y, color_index):
    """Set one pixel; silently ignore out-of-bounds coordinates."""
    if 0 <= x < 64 and 0 <= y < 32:
        bitmap[x, y] = color_index


def fill_rect(x, y, w, h, color_index):
    """Fill a rectangle with color_index; clips to bitmap bounds."""
    x0 = max(x, 0)
    y0 = max(y, 0)
    x1 = min(x + w, 64)
    y1 = min(y + h, 32)
    for py in range(y0, y1):
        for px in range(x0, x1):
            bitmap[px, py] = color_index


def clear(color_index=0):
    """Clear the entire bitmap to color_index."""
    bitmap.fill(color_index)


def refresh():
    """Push the current bitmap to the matrix panel."""
    display.refresh()
