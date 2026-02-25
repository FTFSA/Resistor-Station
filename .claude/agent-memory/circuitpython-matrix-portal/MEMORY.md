# CircuitPython Matrix Portal M4 — Agent Memory

## Project layout
- `portal-firmware/matrix_display.py` — hardware init + pixel API (bit_depth=3, 50-color palette)
- `portal-firmware/current_animation.py` — CurrentAnimation class, electron flow + heat particles
- `portal-firmware/tiny_font.py` — 3x5 bitmap font, number formatting without f-strings
- `portal-firmware/strip_animation.py` — StripAnimation class, NeoPixel flowing electron animation
- `portal-firmware/bulb_control.py` — BulbControl class, linear DAC brightness from current
- `portal-firmware/code.py` — main entry point, IDLE/ACTIVE state machine + button debounce
- `portal-firmware/serial_receiver.py` — SerialReceiver, non-blocking USB CDC packet reader
- `portal-firmware/pins.py` — NEOPIXEL_PIN=A1, BULB_DAC_PIN=A0, BUTTON_UP/DOWN

## Palette (bit_depth=3, 50 entries) — matrix_display.py
- 0: black
- 1-10: electron blue dim→bright (r=20*(i+1)/10, g=80*(i+1)/10, b=255*(i+1)/10)
- 11-20: heated electron orange/red dim→bright (r=255, g=80, b=20 scaled)
- 21: resistor body base (0x283720), 22: warmer, 23: edge, 24: cap, 25: lead
- 26-30: resistor heat glow increasing warmth
- 31-35: heat particles bright→dim
- 36: wire base (0x121920), 37: polarity marker (0x303030)
- 38: trail dim blue, 39: trail dim orange, 40: flow indicator
- 41-45: blended electron colors blue→orange transition
- 46-49: spare black
- COLOR dict maps legacy names (cyan=10, orange=20, wire=36, etc.)

## CurrentAnimation architecture (current_animation.py)
- Single class: `CurrentAnimation`
- `__init__`: pre-allocates all state — no allocs in update()
  - 5x lists of length NUM_ELECTRONS=20: _ex, _ey, _ebase_y, _ephase, _eheat
  - 5x lists of length MAX_HEAT_PARTICLES=12: _hpx, _hpy, _hpvx, _hpvy, _hplife
- Module-level sin_table: bytearray(629), values = int(sin(i/100)*100) + 100
  - Read as: sin_table[phase % 629] - 100  (offset to stay unsigned)
- Module-level _bmp, _dsp: direct refs to matrix_display.bitmap and .display
- Module-level _sp(x,y,c) and _spb(x,y,c) helpers (bounds check, brighter-only)
- Public API: set_params(V, R), set_current(amps), update(), idle_animation(), stop()
- update() calls: _bmp.fill(0), _draw_static, _update_electrons, _update_heat_particles,
  _draw_flow_indicators, _dsp.refresh(minimum_frames_per_second=0)

## Resistor geometry (current_animation.py)
- RES_X1=20, RES_X2=43 (body x span, 24px wide)
- RES_Y1=10, RES_Y2=21 (body y span, 12px tall)
- WIRE_Y1=14, WIRE_Y2=17 (wire rows, 4px tall)
- Wire center y = (14+17)//2 = 15 (for idle dot)

## Speed / current mapping (new animation)
- Wire speed: int((6.0 + current * 4.0) * 100) // 3 px per frame
- Resistor speed: int((2.5 + current * 1.2) * 100) // 3 px per frame
- set_current(amps) → derives R = 3.3 / amps, sets _active=True
- Zero current (< 0.00001 A) → R=330000, _active=False

## set_params vs set_current
- set_params(voltage, resistance): direct control, used by Pi serial packet handler
- set_current(amps): backward compat, assumes V_IN=3.3, derives R
- Both clamp inputs to safe ranges

## Memory patterns confirmed effective
- sin_table as bytearray(629) with +100 offset: ~629 bytes vs ~5000 for list of ints
- Local variable aliasing inside methods: ex=self._ex etc. before hot loops
- bitmap.fill(0) for full clear: faster than pixel-by-pixel loop
- Electron arrays as plain lists (not array.array): acceptable on SAMD51 for len=20
- Deterministic flicker via (tick + x*3 + y*7) % 11: no random() in hot path
- _spb (brighter-only) prevents electron trails overwriting hotter electrons

## Hardware quirks
- auto_refresh=False on FramebufferDisplay — must call display.refresh() explicitly
- bit_depth=3 (not 4) — allows 50-color palette while staying within SRAM budget
- display.refresh(minimum_frames_per_second=0) suppresses the "too slow" warning
- draw_circuit_layout() removed — CurrentAnimation.update() draws everything each frame

## Key API contracts
- matrix_display exports: bitmap, display, group, palette, COLOR
  and functions set_pixel(x,y,ci), fill_rect(x,y,w,h,ci), clear(ci=0), refresh()
- current_animation imports matrix_display at module level; grabs _bmp and _dsp refs
- tiny_font.draw_values(bitmap, resistance, current, voltage) — caller passes matrix_display.bitmap
