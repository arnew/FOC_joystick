# Test Strategy: Observation-Based Fast Testing

**Date**: February 28, 2026  
**Supersedes**: Polling-based test approach in quality_goals_test_suite_v1

---

## Problem Statement

The v1 test suite was slow (~4 minutes for full run) because:
1. **Fixed timeouts**: 5s settle + 3s hold per position, even when stable in 0.3s
2. **Host-side statistics**: 5Hz telemetry parsed for variance → many samples needed
3. **Redundant phases**: separate wait/settle/hold phases re-read the same serial data
4. **No early termination**: if error met in several readings, still waited full duration

## Architecture v2

### Device Side: Rolling Statistics

Firmware computes statistics at FOC rate (~1kHz) in a 0.5s ring buffer:
- **target, actual, error** (signed shortest-path)
- **rolling variance** over 500-sample window  
- **settled flag**: error < 5° AND variance < (3°)² for 200 consecutive ticks (0.2s)

Outputs structured telemetry at 10Hz:
```
@T <millis>,<target_rad>,<actual_rad>,<error_rad>,<variance_rad²>,<settled 0|1>
```

### Host Side: Observation-Based Tests

1. **Observation**: one parsed `@T` line = target + actual + error + variance + settled
2. **Step**: send command → collect observations until criteria met (min/max time bounds)
3. **Analysis**: pure functions on collected observations → pass/fail

### Early Termination

`move_and_observe(target, min_sec, max_sec, n_settled)`:
- Always observes at least `min_sec`
- Exits early if `n_settled` consecutive observations show device settled flag
- Hard timeout at `max_sec`

### Timing Comparison

| Phase | v1 (per position) | v2 (per position) |
|-------|-------------------|-------------------|
| Settle wait | 5.0s fixed timeout | 0.3–5.0s (early exit) |
| Hold sample | 3.0s fixed | 0s (device variance suffices) |
| **Total** | **8.0s** | **0.5–2.0s typical** |

4 cardinal positions: v1 ~39s → v2 ~6s (6× faster)

## Test IDs

| ID | Name | What it measures | Data source |
|----|------|-----------------|-------------|
| A | Accuracy | Mean |error| at settled | settled observations |
| B | Speed | Time to first settled | settle_time from StepResult |
| C | Stability | Error stddev at settled | device variance + host check |
| D | Overshoot | Peak deviation during move | trajectory observations |
| E | Tame | 8-pos long-hold stability | extended min_sec |
| F | Fast | Rapid transitions | short max_sec |
| G | Random Walk | 20-pos robustness | count settled |
| H | Regression | Known problem positions | specific angles |

## Files

- `src/telemetry.h` / `.cpp` — device-side ring buffer and @T output
- `test/quality_goals_test_suite.py` — observation-based test runner
- `test/archive/quality_goals_test_suite_v1.py` — previous version
