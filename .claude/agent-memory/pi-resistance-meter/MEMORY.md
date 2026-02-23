# Pi Resistance Meter — Agent Memory

## File Ownership
- `pi-app/measurement.py` — this agent owns this file entirely
- `pi-app/color_code.py` — this agent owns this file entirely
- Do NOT touch UI, serial, web, or any other files

## Architecture Decisions

### snap_to_e24: two separate implementations exist
- `measurement.py` has a module-level `snap_to_e24(ohms)` using **log-ratio** (nearest match)
- `color_code.py` has its own `snap_to_e24` that rounds **up** (safety margin), importing from `resistor_constants`
- These are intentionally different and must not be merged; each serves its own caller

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

## Links
- See `debugging.md` for any future I2C / ADC reliability notes
