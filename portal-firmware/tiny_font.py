"""
Portal M4 - Tiny Pixel Font

3x5 bitmap font. Each glyph is 5 bytes; each byte encodes one row of
3 pixels, MSB-first: bit2=left, bit1=centre, bit0=right.

Only imports matrix_display.bitmap at draw time — no other runtime deps.
"""

# ---------------------------------------------------------------------------
# Glyph table
#
# Encoding reminder:
#   bit pattern  binary  decimal
#   "XXX"  ->  0b111  -> 7
#   "X.X"  ->  0b101  -> 5
#   ".X."  ->  0b010  -> 2
#   "XX."  ->  0b110  -> 6
#   ".XX"  ->  0b011  -> 3
#   "X.."  ->  0b100  -> 4
#   "..X"  ->  0b001  -> 1
#   "..."  ->  0b000  -> 0
# ---------------------------------------------------------------------------

GLYPHS = {
    # ---- Digits -------------------------------------------------------
    # 0: 111 / 101 / 101 / 101 / 111
    '0': bytes([7, 5, 5, 5, 7]),

    # 1: .X. / XX. / .X. / .X. / XXX
    '1': bytes([2, 6, 2, 2, 7]),

    # 2: 111 / ..X / 111 / X.. / 111
    '2': bytes([7, 1, 7, 4, 7]),

    # 3: 111 / ..X / 111 / ..X / 111
    '3': bytes([7, 1, 7, 1, 7]),

    # 4: X.X / X.X / 111 / ..X / ..X
    '4': bytes([5, 5, 7, 1, 1]),

    # 5: 111 / X.. / 111 / ..X / 111
    '5': bytes([7, 4, 7, 1, 7]),

    # 6: 111 / X.. / 111 / X.X / 111
    '6': bytes([7, 4, 7, 5, 7]),

    # 7: 111 / ..X / ..X / .X. / .X.
    '7': bytes([7, 1, 1, 2, 2]),

    # 8: 111 / X.X / 111 / X.X / 111
    '8': bytes([7, 5, 7, 5, 7]),

    # 9: 111 / X.X / 111 / ..X / 111
    '9': bytes([7, 5, 7, 1, 7]),

    # ---- Uppercase letters --------------------------------------------
    # A: .X. / X.X / 111 / X.X / X.X
    'A': bytes([2, 5, 7, 5, 5]),

    # B: XX. / X.X / XX. / X.X / XX.
    'B': bytes([6, 5, 6, 5, 6]),

    # C: .XX / X.. / X.. / X.. / .XX
    'C': bytes([3, 4, 4, 4, 3]),

    # D: XX. / X.X / X.X / X.X / XX.
    'D': bytes([6, 5, 5, 5, 6]),

    # E: 111 / X.. / 111 / X.. / 111
    'E': bytes([7, 4, 7, 4, 7]),

    # F: 111 / X.. / 111 / X.. / X..
    'F': bytes([7, 4, 7, 4, 4]),

    # G: .XX / X.. / X.X / X.X / .XX
    'G': bytes([3, 4, 5, 5, 3]),

    # H: X.X / X.X / 111 / X.X / X.X
    'H': bytes([5, 5, 7, 5, 5]),

    # I: 111 / .X. / .X. / .X. / 111
    'I': bytes([7, 2, 2, 2, 7]),

    # J: ..X / ..X / ..X / X.X / .X.
    'J': bytes([1, 1, 1, 5, 2]),

    # K: X.X / X.X / XX. / X.X / X.X
    'K': bytes([5, 5, 6, 5, 5]),

    # L: X.. / X.. / X.. / X.. / 111
    'L': bytes([4, 4, 4, 4, 7]),

    # M: X.X / 111 / X.X / X.X / X.X
    'M': bytes([5, 7, 5, 5, 5]),

    # N: X.X / 111 / 111 / X.X / X.X
    'N': bytes([5, 7, 7, 5, 5]),

    # O: .X. / X.X / X.X / X.X / .X.
    'O': bytes([2, 5, 5, 5, 2]),

    # P: 111 / X.X / 111 / X.. / X..
    'P': bytes([7, 5, 7, 4, 4]),

    # Q: .X. / X.X / X.X / X.X / .11  (bottom-right dot marks tail)
    # .X. / X.X / X.X / XX. / .XX
    'Q': bytes([2, 5, 5, 6, 3]),

    # R: 111 / X.X / 111 / XX. / X.X
    'R': bytes([7, 5, 7, 6, 5]),

    # S: .XX / X.. / .X. / ..X / XX.
    'S': bytes([3, 4, 2, 1, 6]),

    # T: 111 / .X. / .X. / .X. / .X.
    'T': bytes([7, 2, 2, 2, 2]),

    # U: X.X / X.X / X.X / X.X / 111
    'U': bytes([5, 5, 5, 5, 7]),

    # V: X.X / X.X / X.X / X.X / .X.
    'V': bytes([5, 5, 5, 5, 2]),

    # W: X.X / X.X / X.X / 111 / X.X
    'W': bytes([5, 5, 5, 7, 5]),

    # X: X.X / X.X / .X. / X.X / X.X
    'X': bytes([5, 5, 2, 5, 5]),

    # Y: X.X / X.X / .X. / .X. / .X.
    'Y': bytes([5, 5, 2, 2, 2]),

    # Z: 111 / ..X / .X. / X.. / 111
    'Z': bytes([7, 1, 2, 4, 7]),

    # ---- Specials -----------------------------------------------------
    # Omega (Ω): .X. / X.X / X.X / .X. / X.X  (stylised omega)
    'Ω': bytes([2, 5, 5, 2, 5]),

    # k: X.. / X.X / XX. / X.X / X.X
    'k': bytes([4, 5, 6, 5, 5]),

    # m: ... / ... / 111 / X.X / X.X   (lowercase m, 3-wide is tight)
    # Use: ... / X.X / 111 / X.X / X.X
    'm': bytes([0, 5, 7, 5, 5]),

    # M (already defined above as uppercase — 'm' is the SI milli prefix)

    # dot (.): ... / ... / ... / ... / .X.
    '.': bytes([0, 0, 0, 0, 2]),

    # colon (:): ... / .X. / ... / .X. / ...
    ':': bytes([0, 2, 0, 2, 0]),

    # space ( ): all blank
    ' ': bytes([0, 0, 0, 0, 0]),
}

# ---------------------------------------------------------------------------
# Draw functions
# ---------------------------------------------------------------------------

def draw_char(bitmap, x, y, ch, color_index):
    """Draw a single 3x5 character onto bitmap at pixel position (x, y)."""
    glyph = GLYPHS.get(ch)
    if glyph is None:
        return
    for row in range(5):
        bits = glyph[row]
        for col in range(3):
            if bits & (4 >> col):
                px = x + col
                py = y + row
                if 0 <= px < 64 and 0 <= py < 32:
                    bitmap[px, py] = color_index


def draw_string(bitmap, x, y, text, color_index):
    """Draw a string left-to-right; each character occupies 4px (3+1 gap)."""
    cx = x
    for ch in text:
        draw_char(bitmap, cx, y, ch, color_index)
        cx += 4


# ---------------------------------------------------------------------------
# Scratch buffer for draw_values — pre-allocated, reused each call.
# Maximum formatted string length observed: "4.7kΩ" = 5 visible chars,
# "99.9mA" = 6 visible chars, "9.9V" = 4 visible chars.
# We size the buffer for 12 characters safely.
# ---------------------------------------------------------------------------

_FMT_BUF = bytearray(12)   # raw ASCII scratch; reused every call


def _uint_to_buf(buf, offset, value, digits):
    """Write 'digits' decimal digits of value into buf starting at offset.

    Fills right-to-left so leading zeros appear if value < 10^(digits-1).
    Returns offset + digits (the position after the last written digit).
    """
    pos = offset + digits - 1
    while pos >= offset:
        buf[pos] = 48 + (value % 10)   # ord('0') == 48
        value //= 10
        pos -= 1
    return offset + digits


def draw_values(bitmap, resistance, current, voltage, white=1, cyan=6):
    """Render R, I, V readings in the bottom-left area of the 64x32 matrix.

    Row y=22: resistance string  (white, palette index 1)
    Row y=28: current + voltage  (cyan,  palette index 6)

    Arguments:
        bitmap      -- displayio.Bitmap to draw into (pass matrix_display.bitmap)
        resistance  -- ohms as a float (or int)
        current     -- amps as a float
        voltage     -- volts as a float
        white       -- palette index for white  (default 1)
        cyan        -- palette index for cyan   (default 6)
    """
    bm = bitmap

    # ------------------------------------------------------------------
    # Format resistance into _FMT_BUF
    # Avoid f-strings and string concatenation; build into bytearray.
    # ------------------------------------------------------------------
    r_int = int(resistance)
    pos = 0

    if r_int >= 1000000:
        # X MΩ  — show whole megohms only (single digit likely in range)
        meg = r_int // 1000000
        pos = _uint_to_buf(_FMT_BUF, pos, meg, 1)
        _FMT_BUF[pos] = ord('M'); pos += 1
    elif r_int >= 1000:
        # X.XkΩ
        k_whole = r_int // 1000
        k_tenth = (r_int % 1000) // 100
        pos = _uint_to_buf(_FMT_BUF, pos, k_whole, 1)
        _FMT_BUF[pos] = ord('.'); pos += 1
        pos = _uint_to_buf(_FMT_BUF, pos, k_tenth, 1)
        _FMT_BUF[pos] = ord('k'); pos += 1
    else:
        # XXX Ω  (up to 999 ohms — show at most 3 digits)
        if r_int >= 100:
            pos = _uint_to_buf(_FMT_BUF, pos, r_int, 3)
        elif r_int >= 10:
            pos = _uint_to_buf(_FMT_BUF, pos, r_int, 2)
        else:
            pos = _uint_to_buf(_FMT_BUF, pos, r_int, 1)

    _FMT_BUF[pos] = ord('O'); pos += 1   # 'O' stands in for Ω (font has Ω but we use string iteration)

    r_len = pos   # number of characters in resistance string

    # Draw resistance row at y=22
    cx = 0
    for i in range(r_len):
        ch = chr(_FMT_BUF[i])
        # Map 'O' back to Ω for the font lookup
        if ch == 'O':
            ch = 'Ω'
        draw_char(bm, cx, 22, ch, white)
        cx += 4

    # ------------------------------------------------------------------
    # Format current  →  X.XXmA
    # current is in amps; display as milliamps with 2 decimal places.
    # ------------------------------------------------------------------
    ma_total = int(current * 100000)   # tenths of microamps → gives us mA * 100
    # We want X.XX mA: integer mA and two fractional mA digits
    ma_whole = ma_total // 100
    ma_frac  = ma_total % 100

    pos = 0
    if ma_whole >= 10:
        pos = _uint_to_buf(_FMT_BUF, pos, ma_whole, 2)
    else:
        pos = _uint_to_buf(_FMT_BUF, pos, ma_whole, 1)
    _FMT_BUF[pos] = ord('.'); pos += 1
    pos = _uint_to_buf(_FMT_BUF, pos, ma_frac, 2)
    _FMT_BUF[pos] = ord('m'); pos += 1
    _FMT_BUF[pos] = ord('A'); pos += 1

    i_len = pos

    # Draw current starting at x=0, y=28
    cx = 0
    for i in range(i_len):
        draw_char(bm, cx, 28, chr(_FMT_BUF[i]), cyan)
        cx += 4

    # ------------------------------------------------------------------
    # Format voltage  →  X.XV
    # ------------------------------------------------------------------
    v_total = int(voltage * 10)   # tenths of a volt
    v_whole = v_total // 10
    v_tenth = v_total % 10

    pos = 0
    if v_whole >= 10:
        pos = _uint_to_buf(_FMT_BUF, pos, v_whole, 2)
    else:
        pos = _uint_to_buf(_FMT_BUF, pos, v_whole, 1)
    _FMT_BUF[pos] = ord('.'); pos += 1
    pos = _uint_to_buf(_FMT_BUF, pos, v_tenth, 1)
    _FMT_BUF[pos] = ord('V'); pos += 1

    v_len = pos

    # Place voltage to the right of the current string (with 1px gap)
    # current string is i_len chars × 4px wide
    vx = i_len * 4 + 2
    for i in range(v_len):
        draw_char(bm, vx, 28, chr(_FMT_BUF[i]), cyan)
        vx += 4
