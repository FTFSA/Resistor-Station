"""
Portal M4 - HUB75 32x64 LED Matrix Display Driver

Module-level init runs on import. Callers must not re-init hardware.
Exposes a flat pixel API (set_pixel, fill_rect, clear, refresh) plus
draw_circuit_layout() for the one-time static background paint.
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
    bit_depth=4,
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
# Palette — 16 entries, fixed at module level
# ---------------------------------------------------------------------------

palette = displayio.Palette(16)
palette[0]  = 0x000000   # black
palette[1]  = 0xFFFFFF   # white
palette[2]  = 0xDC0000   # red
palette[3]  = 0x00C800   # green
palette[4]  = 0x0000DC   # blue
palette[5]  = 0xDCC800   # yellow
palette[6]  = 0x00C8C8   # cyan
palette[7]  = 0xDC7800   # orange
palette[8]  = 0x005000   # dark_green
palette[9]  = 0x3C3C3C   # dim_white
palette[10] = 0x00FFFF   # bright_cyan
palette[11] = 0xC80064   # pink
palette[12] = 0x000000   # spare black
palette[13] = 0x000000   # spare black
palette[14] = 0x000000   # spare black
palette[15] = 0x000000   # spare black

# Convenience name → index mapping for callers
COLOR = {
    'black':       0,
    'white':       1,
    'red':         2,
    'green':       3,
    'blue':        4,
    'yellow':      5,
    'cyan':        6,
    'orange':      7,
    'dark_green':  8,
    'dim_white':   9,
    'bright_cyan': 10,
    'pink':        11,
}

# ---------------------------------------------------------------------------
# Pixel buffer
# ---------------------------------------------------------------------------

bitmap = displayio.Bitmap(64, 32, 16)

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


# ---------------------------------------------------------------------------
# Static circuit background
# ---------------------------------------------------------------------------

def draw_circuit_layout():
    """Paint the static circuit diagram once; call refresh() when done."""

    clear(COLOR['black'])

    green  = COLOR['green']
    yellow = COLOR['yellow']
    white  = COLOR['white']
    dim    = COLOR['dim_white']

    # ------------------------------------------------------------------
    # Wires
    # ------------------------------------------------------------------

    # Top horizontal wire  y=4, x=6..60
    for x in range(6, 61):
        set_pixel(x, 4, green)

    # Bottom horizontal wire  y=27, x=6..60
    for x in range(6, 61):
        set_pixel(x, 27, green)

    # Left vertical wire  x=2, y=4..27
    for y in range(4, 28):
        set_pixel(2, y, green)

    # Right vertical wire  x=61, y=4..27
    for y in range(4, 28):
        set_pixel(61, y, green)

    # Corner connectors — join the horizontals to the verticals
    # Top-left corner: x=2..6, y=4
    for x in range(2, 7):
        set_pixel(x, 4, green)
    # Top-right corner: x=60..62, y=4
    for x in range(60, 62):
        set_pixel(x, 4, green)
    # Bottom-left corner: x=2..6, y=27
    for x in range(2, 7):
        set_pixel(x, 27, green)
    # Bottom-right corner: x=60..62, y=27
    for x in range(60, 62):
        set_pixel(x, 27, green)

    # ------------------------------------------------------------------
    # Battery  (x=2–5, y=10–21)
    # Represented as two vertical yellow plates and polarity markers.
    # ------------------------------------------------------------------

    # Left plate: x=3, y=12..20
    for y in range(12, 21):
        set_pixel(3, y, yellow)

    # Right plate: x=5, y=12..20
    for y in range(12, 21):
        set_pixel(5, y, yellow)

    # Short horizontal connectors top of plates
    set_pixel(3, 12, yellow)
    set_pixel(4, 12, yellow)
    set_pixel(5, 12, yellow)

    # Short horizontal connectors bottom of plates
    set_pixel(3, 20, yellow)
    set_pixel(4, 20, yellow)
    set_pixel(5, 20, yellow)

    # '+' terminal dot above  (x=4, y=10)
    set_pixel(4, 10, white)

    # '-' terminal dot below  (x=4, y=22)
    set_pixel(4, 22, white)

    # ------------------------------------------------------------------
    # Resistor box  (x=47–57, y=1–7)
    # White outline rectangle 11 wide × 7 tall.
    # ------------------------------------------------------------------

    # Top edge y=1, x=47..57
    for x in range(47, 58):
        set_pixel(x, 1, white)

    # Bottom edge y=7, x=47..57
    for x in range(47, 58):
        set_pixel(x, 7, white)

    # Left edge x=47, y=1..7
    for y in range(1, 8):
        set_pixel(47, y, white)

    # Right edge x=57, y=1..7
    for y in range(1, 8):
        set_pixel(57, y, white)

    # Interior zigzag: 3 diagonal pixels suggesting a resistor symbol
    # Row 2 → col 49 (left-leaning)
    set_pixel(49, 2, white)
    # Row 3 → col 51 (right-leaning)
    set_pixel(51, 3, white)
    # Row 4 → col 53 (left-leaning)
    set_pixel(53, 4, white)
    # Row 5 → col 55 (right-leaning)
    set_pixel(55, 5, white)

    # Connector from top wire (y=4) down to resistor box top (y=1)
    # The resistor sits straddling y=4; draw a short stub at x=52, y=1..4
    for y in range(1, 5):
        set_pixel(52, y, green)

    # ------------------------------------------------------------------
    # Current-direction arrow-dots on wires
    # ------------------------------------------------------------------

    # Top wire (y=4): dots at x=20 and x=35 (current flows left→right)
    set_pixel(20, 4, dim)
    set_pixel(35, 4, dim)

    # Bottom wire (y=27): dots at x=35 and x=20 (current flows right→left)
    set_pixel(35, 27, dim)
    set_pixel(20, 27, dim)

    # ------------------------------------------------------------------
    # Done — push to panel
    # ------------------------------------------------------------------

    display.refresh()
