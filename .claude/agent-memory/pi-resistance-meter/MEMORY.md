# Pi Resistance Meter — Agent Memory

## File Ownership
- `pi-app/measurement.py` — this agent owns this file entirely
- `pi-app/color_code.py` — this agent owns this file entirely
- Do NOT touch UI, serial, web, or any other files

## Architecture Decisions

### snap_to_e24: one canonical implementation, exported from both files
- `measurement.py` has the original module-level `snap_to_e24(ohms)` using **log-ratio** (nearest match)
- `color_code.py` now has its own identical log-ratio `snap_to_e24` (same algorithm, same table)
- Both are importable independently; no cross-import between these two files (avoids circular deps)
- The old `color_code.py` version that rounded **up** via `resistor_constants` has been replaced

### Hardware imports are deferred into __init__
- `board`, `busio`, `adafruit_ads1x15` are imported inside `ResistanceMeter.__init__`
- Reason: allows `measurement.py` to be imported on non-Pi hosts for unit testing without ImportError at module load
- The module-level `snap_to_e24` and `format_value` are always available without hardware

### E24 table construction
- `_E24_TABLE` is pre-computed at module level: 7 decades (10^0 through 10^6) × 24 values + sentinel 10_000_000.0
- Total 169 entries; linear scan is fast enough for this use case

## Verified Thresholds (from spec + tests)
- SHORT: v < 0.03V (strict less-than)
- OPEN:  v > 3.20V (strict greater-than)
- Boundary values (exactly 0.03 or 3.20) → 'present'
- Second denom guard (`denom <= 0`) catches floating-point edge above OPEN_THRESHOLD

## Formula
R_unknown = R_known × Vmid / (Vin - Vmid)
- Never alter without explicit instruction
- Division-by-zero guard required even though OPEN_THRESHOLD should catch it first

## read_voltage trimming
- 32 samples total, sort, slice [4:-4] = 24 samples used
- If samples parameter is changed, ensure at least 9 samples (> 8 to make trim valid)

## format_value behavior
- Uses f"{scaled:.1f}" then strips trailing ".0"
- 10000 → "10kΩ" (not "10.0kΩ"), 4700 → "4.7kΩ", 2200000 → "2.2MΩ"

## Confirmed test vectors (all passing)
- snap_to_e24(4650) → 4700.0  (log-ratio prefers 4.7k over 4.3k at midpoint)
- snap_to_e24(0) → 1.0,  snap_to_e24(-5) → 1.0,  snap_to_e24(15e6) → 10e6
- format_value(10000000) → "10MΩ"
- Voltage-divider formula is algebraically exact in floating point for round-trip test

### color_code.py resistance_to_bands verified vectors
- 4700   → Yellow(4)-Violet(7)-Red(2)-Gold  PASS
- 330    → Orange(3)-Orange(3)-Brown(1)-Gold PASS
- 10000  → Brown(1)-Black(0)-Orange(3)-Gold  PASS
- 100    → Brown(1)-Black(0)-Brown(1)-Gold   PASS
- 1000000→ Brown(1)-Black(0)-Green(5)-Gold   PASS

### color_code.py band encoding notes
- mantissa = ohms / 10^(exponent-1), not /10^exponent; gives 2-digit value in [10,100)
- multiplier = exponent - 1 (trailing zeros), clamped 0–8
- Band 4 dict has key 'tolerance' (float fraction, e.g. 0.05), not 'digit'
- bands_to_description reconstructs ohms as (d1*10+d2)*10^multiplier then calls _format_value
- _format_value is a private copy of measurement.py's format_value; no cross-import needed

## KNOWN BUGS (from 2026-02-25 audit)

### BUG 1 (REAL): color_code.py line 137 — float truncation gives wrong d2 for 11 E24 values
- `int(mantissa)` truncates instead of rounds → wrong second digit for:
  1.2, 2.4, 3.3, 4.3, 5.1, 5.6, 8.2, 9.1 Ω (first decade, all sub-10Ω so unreachable from circuit)
  plus 510kΩ (d2=0 not 1), 820kΩ (d2=1 not 2), 8.2MΩ (d2=1 not 2) — these ARE reachable
- Fix: change `int(mantissa)` to `round(mantissa)` on line 137

### BUG 2: color_code.py — sub-10Ω multiplier clamped to 0 (Gold ×0.1 not representable)
- exponent=0 → mult=exponent-1=-1, clamped to 0 → wrong encoding for [1Ω, 9.9Ω]
- Mitigating: circuit threshold means measure() never produces ohms < ~92Ω; BUT screen_calculator.py may call resistance_to_bands() directly
- Fix: detect ohms < 10 and use Gold multiplier band (×0.1) — requires special-casing

### BUG 3 (hardware limit): OPEN_THRESHOLD=3.20V → max measurable R ≈ 320kΩ
- 330kΩ and above reads as 'open' (V_mid=3.20V at 320kΩ with 10kΩ divider)
- Not a code bug; this is physics. Document it. To measure up to 1MΩ, use R_KNOWN=100kΩ.

### BUG 4 (minor): read_voltage() has no guard against samples <= 8
- samples=8 → readings[4:-4]=[] → ZeroDivisionError
- Fix: add `if samples <= 8: raise ValueError("samples must be > 8")`

## Cross-file RGB Mismatch (out of scope — flag to portal/UI team)
- shared/resistor_constants.py and color_code.py define DIFFERENT RGB tuples for same colors
- Red: shared=(220,20,20) vs color_code=(255,0,0); Gold: shared=(212,175,55) vs (255,215,0)
- Portal firmware uses shared/; Pi UI uses color_code.py → colors differ across displays

## Links
- See `debugging.md` for any future I2C / ADC reliability notes
