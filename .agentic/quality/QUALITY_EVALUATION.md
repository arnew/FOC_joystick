# Quality Evaluation System

**Purpose**: Comprehensive tuning quality assessment combining automated scoring, diagnostics, and actionable recommendations.

**Status**: Implemented Feb 22, 2026

---

## System Overview

The quality evaluation system measures PID tuning effectiveness across five orthogonal metrics, providing a 0-100 composite score with automated recommendations.

### Five Quality Metrics

| Metric | Description | Excellent | Poor |
|--------|-------------|-----------|------|
| **Overshoot** | Peak deviation from target | <5% | >20% |
| **Settling Time** | Time to reach steady state | <1.5s | >5s |
| **Position Noise** | High-frequency jitter (σ) | <0.5° | >3° |
| **Position Drift** | Low-frequency wandering | <0.2° | >11.5° |
| **Stability** | % time within tolerance | >90% | <50% |

### Quality Score Scale

- **90-100**: EXCELLENT - Production-ready tuning
- **70-89**: GOOD - Acceptable for normal use
- **50-69**: FAIR - Needs improvement
- **0-49**: POOR - Unacceptable, must retune

---

## Implementation

### Enhanced Step Response Test

The `step_response_test()` in `test/calibrate_pid.py` performs:

1. **Step Command** - Commands motor to move specific angle
2. **Response Capture** - Records position at 100+ Hz during movement
3. **Settling Detection** - Identifies when position stabilizes
4. **Steady-State Monitoring** - Observes 5 seconds after settling to measure noise/drift
5. **Quality Scoring** - Calculates composite 0-100 score
6. **Automated Diagnosis** - Provides specific recommendations if poor

### Code Changes

**File**: `test/calibrate_pid.py`

**New Methods**:
- `_calculate_tuning_quality()` - Composite scoring algorithm
- `_print_tuning_quality_report()` - Formatted output with recommendations

**Enhanced Methods**:
- `step_response_test()` - Now includes 5-second steady-state phase
- Robust overshoot calculation (handles near-zero and negative steps)
- Improved settling time detection (robust to encoder noise)

### Output Format

```
✓ Steady-State Stability (monitoring 5.0s after settling):
  Position drift: X.XX rad
  Position noise (σ): X.XX rad
  Stability: XX.X% (within ±2.9°)

TUNING QUALITY ASSESSMENT
Overall Score: XX.X/100.0 [✓ EXCELLENT / ⚠ FAIR / ✗ POOR]

Breakdown:
  Overshoot: X.X% (target: <5%)
  Settling Time: X.XX s (target: <1.5s)
  Position Noise: X.XX° (target: <0.5°)
  Position Drift: X.XX° over NNN samples
  Steady-State Stability: XX.X% (target: >90%)

RECOMMENDATION: [Specific tuning adjustments or hardware checks]
```

---

## Current Motor Status

### Initial Baseline (Pre-Fix)

**Overall Quality Score: 28.4/100 ✗ POOR**

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Overshoot | 0.0% | <5% | ✓ OK |
| Settling Time | 3.49s | <1.5s | ⚠ Slow |
| Position Noise | 13.53° | <0.5° | ✗ **VERY HIGH** |
| Position Drift | 24.64° | <0.2° | ✗ **SEVERE** |
| Stability | 52.1% | >90% | ✗ **POOR** |

### Post-Fix Results

See [FIX_RESULTS.md](FIX_RESULTS.md) for latest measurements (72.9/100 GOOD after applying fixes).

---

## Problem Diagnosis

### Primary Issue: Excessive Position Jitter

**Symptoms**:
- Motor oscillates around setpoint rather than holding steady
- Encoder readings jump around significantly
- Motor "buzzes" or "hums" noticeably
- Noise: 13.53° (target <0.5°)

**Root Causes** (in order of likelihood):
1. **Too much proportional gain (Kp)** - Motor over-reacts to small position errors
2. **Too little derivative gain (Kd)** - No damping to slow down corrections
3. **Encoder noise** - I2C sampling or electrical noise from motor power
4. **Mechanical slack** - Gearbox or coupling play causing feedback jitter

**Fixes to Try**:
```cpp
// In pid_config.h:
MOTOR0_PID_KP = 4.0   // Reduce from 8.257
MOTOR0_PID_KD = 2.0   // Increase from 0.546
```

Or run calibration with stricter safety margin:
```bash
python3 test/calibrate_pid.py --motor 0 --safety-factor 0.5
```

### Secondary Issue: Large Position Drift

**Symptoms**:
- Position slowly walks away from setpoint (24.64° over 5s)
- Motor won't return to original position if hand-disturbed
- Setpoint seems to "forget" over time

**Root Causes**:
1. **Insufficient integral gain (Ki)** - Can't generate enough sustained force to hold position
2. **Ki is zero or very low** - No I-action to accumulate error and correct drift
3. **Mechanical friction** - Motor needs constant velocity to overcome load

**Fixes**:
```cpp
// In pid_config.h:
MOTOR0_PID_KI = 10.0  // Increase to add integral action
```

Or retune outer loop:
```bash
python3 test/calibrate_pid.py --motor 0 --angle-only
```

### Tertiary Issue: Slow Settling

**Symptom**: Takes 3.49 seconds to reach target (target <1.5s)

**Cause**: Low proportional gain

**Fix**: Slightly increase Kp (carefully - opposite to noise issue!)
```cpp
MOTOR0_PID_KP = 6.0  // Modest increase
```

---

## Recommended Tuning Strategy

### Step 1: Reduce Noise (Highest Priority)

The 13.53° jitter is unacceptable - this is the main user complaint.

**Conservative Tuning Template**:
```cpp
// Voltage controller (inner velocity loop)
#define MOTOR0_VELOCITY_KP 3.0      // Reduced from 5.440
#define MOTOR0_VELOCITY_KI 10.0     // Reduced from 31.561
#define MOTOR0_VELOCITY_KD 1.5      // Increased from 0.234 (damping)

// Angle controller (outer position loop)
#define MOTOR0_PID_KP 4.0           // Reduced from 8.257
#define MOTOR0_PID_KI 15.0          // Tuned Ki for drift
#define MOTOR0_PID_KD 2.5           // Increased from 0.546 (strong damping)
```

### Step 2: Re-Run Auto-Tuning

```bash
# Build with conservative values
platformio run -e pico_1motor_limited --target upload

# Re-run calibration with safety factor
python3 test/calibrate_pid.py --motor 0 --safety-factor 0.45
```

### Step 3: Validate Quality

```bash
# Run step response test to verify improvement
python3 test/calibrate_pid.py --motor 0 --step-only
```

**Success Criteria**:
- ✓ Noise <1.0° (aim for <0.5°)
- ✓ Drift <0.1°
- ✓ Stability >85%
- ✓ Settling <2.5s
- ✓ Overall Score >60/100

---

## Tuning Trade-offs

```
Increase Kp → Faster response BUT more overshoot & noise
Increase Kd → Damping (reduces noise) BUT slower & sluggish
Increase Ki → Better drift correction BUT can cause oscillation
```

**Current Tuning is OVER-AGGRESSIVE**:
- High Ki (31.2) trying to force position holding → causes jitter
- Low Kd (0.546) can't damp the oscillations → noise persists

**Solution**: Balance gains for stability over speed.

---

## Hardware Diagnostics

If adjusting gains doesn't fix noise, check hardware:

### 1. Encoder Connection

```bash
python3 test/debug_joystick.py --monitor
# Manually rotate motor by hand
# Position should change smoothly without jumps
```

**Signs of bad encoder**:
- Large position jumps (>0.5° per sample)
- Periodic noise at specific rotation angles
- I2C timeouts in debug output

### 2. Power Supply

**Check for voltage sag under load**:
- Motor should have dedicated stable 12V supply
- Verify total current budget: dual motors ~2-3A at full torque

**Signs of bad power**:
- Noise increases with motor velocity
- Oscillation at specific frequencies (noise ripple)
- Motor loses position when other devices power on

### 3. Mechanical Slack

**Manual test**:
- Try rotating motor shaft by hand
- Feel for play/backlash in coupling or gearbox
- Notches or discontinuities = mechanical slack

---

## Testing Protocol

Each tuning iteration:

```bash
# 1. Update pid_config.h with new gains

# 2. Rebuild and upload
platformio run -e pico_1motor_limited --target upload

# 3. Wait for motor to settle
sleep 5

# 4. Run quality test
python3 test/calibrate_pid.py --motor 0 --step-only

# 5. Record Quality Score trend (should increase)

# 6. Repeat until score >70
```

---

## Usage

```bash
# Run step response test with quality evaluation
python3 test/calibrate_pid.py --motor 0 --step-only

# Run full calibration (includes quality check at end)
python3 test/calibrate_pid.py --motor 0

# Full test suite shows overall status
python3 test/test_suite_automated.py
```

---

## Quality Score Calculation Reference

```python
Quality Score = weighted average of 5 factors (0-100):

Overshoot Score:
  0% overshoot      = 100 pts ✓ (perfect)
  5-10%            = 75 pts  (acceptable)
  20%+             = 0 pts   (unacceptable)

Settling Time Score:
  <1.0s           = 100 pts ✓ (excellent)
  1.5-2.5s        = 60 pts  (acceptable)
  >5.0s           = 0 pts   (unacceptable)

Noise (Position σ):
  <0.01 rad (0.5°)    = 100 pts ✓ (excellent)
  0.05 rad (3°)       = 50 pts  (fair)
  >0.1 rad (5.7°)     = 0 pts   (unacceptable)

Drift:
  <0.02 rad (1°)      = 100 pts ✓ (excellent)
  0.1 rad (5.7°)      = 50 pts  (fair)
  >0.2 rad (11.5°)    = 0 pts   (unacceptable)

Stability (% time within ±2.9°):
  100%            = 100 pts ✓ (perfect)
  85%             = 70 pts  (good)
  50%             = 0 pts   (unacceptable)

Overall = (overshoot + settling + noise + drift + stability) / 5.0
```

---

## Evolution

**Initial State** (Feb 22, 2026):
- User complaint: "Motor is quite noisy and won't hold position if disturbed"
- Quality Score: 28.4/100 POOR
- Root cause: Aggressive Kp, low Kd, insufficient Ki

**Post-Fix State**:
- Applied recommended tuning adjustments
- Quality Score: 72.9/100 GOOD
- See [FIX_RESULTS.md](FIX_RESULTS.md) for details

**Current State**:
- Motor performs acceptably for normal use
- Further optimization possible (target 85+/100)

---

## Success Criteria Summary

Original Issue: "Motor is quite noisy and won't hold position if disturbed"

✅ **Issue Identified**: Quality Score 28.4/100 (POOR)
- Root causes: Aggressive Kp, low Kd, insufficient Ki
- Specific metrics: 13.53° noise, 24.64° drift, 52.1% stability

✅ **Tuning Fixes Applied**: Conservative gains
- Reduced Kp/Ki for stability
- Increased Kd for damping

✅ **Motor Performance Improved**: Quality Score 72.9/100 (GOOD)
- Smooth, quiet operation
- Holds position acceptably
- Further optimization possible
