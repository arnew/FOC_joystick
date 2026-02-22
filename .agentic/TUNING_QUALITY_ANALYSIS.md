# Tuning Quality Evaluation & Recommendations

## Overview

The enhanced `step_response_test()` now evaluates **tuning quality** across five dimensions:

1. **Overshoot** - How much the position overshoots the target
2. **Settling Time** - How fast it reaches steady state
3. **Position Noise** - High-frequency jitter/oscillation during steady state
4. **Position Drift** - Low-frequency wandering away from setpoint
5. **Steady-State Stability** - Percentage of time position is within ±2.9° of target

## Current Motor Status

**Overall Score: 28.4/100 (POOR)**

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Overshoot | 0.0% | <5% | ✓ OK |
| Settling Time | 3.49s | <1.5s | ⚠ Slow |
| Position Noise | 13.53° | <0.5° | ✗ **VERY HIGH** |
| Position Drift | 24.64° | <0.2° | ✗ **SEVERE** |
| Stability | 52.1% | >90% | ✗ **POOR** |

## Problem Diagnosis

### Primary Issue: Excessive Position Jitter (13.53° noise)

**Symptoms:**
- Motor oscillates around setpoint rather than holding steady
- Encoder readings jump around significantly
- Motor "buzzes" or "hums" noticeably

**Root Causes (in order of likelihood):**
1. **Too much proportional gain (Kp)** - Motor over-reacts to small position errors
2. **Too little derivative gain (Kd)** - No damping to slow down corrections
3. **Encoder noise** - I2C sampling or electrical noise from motor power
4. **Mechanical slack** - Gearbox or coupling play causing feedback jitter

**Fixes to Try:**
```bash
# Option A: Reduce Kp, increase Kd
# In pid_config.h:
MOTOR0_PID_KP = 4.0   # Reduce from 8.257
MOTOR0_PID_KD = 2.0   # Increase from 0.546

# Option B: Run calibration with stricter safety margin
python3 test/calibrate_pid.py --motor 0 --safety-factor 0.5  # More conservative tuning
```

### Secondary Issue: Large Position Drift (24.64° over 5s)

**Symptoms:**
- Position slowly walks away from setpoint
- Motor won't return to original position if hand-disturbed
- Setpoint seems to "forget" over time

**Root Causes:**
1. **Insufficient integral gain (Ki)** - Can't generate enough sustained force to hold position
2. **Ki is zero or very low** - No I-action to accumulate error and correct drift
3. **Mechanical friction** - Motor needs constant velocity to overcome load

**Fixes to Try:**
```bash
# In pid_config.h:
MOTOR0_PID_KI = 10.0  # Increase from 31.197 (or tune properly with auto-tuning)

# Run calibration to auto-tune both loops:
python3 test/calibrate_pid.py --motor 0 --angle-only  # Retune outer loop for Ki
```

### Tertiary Issue: Slow Settling (3.49s)

**Symptom:** Takes 3.5 seconds to reach target (target is <1.5s)

**Cause:** Low proportional gain

**Fix:** Slightly increase Kp (but carefully - opposite to noise issue!)
```bash
MOTOR0_PID_KP = 6.0  # Modest increase
```

## Recommended Tuning Strategy

### Step 1: Reduce Noise (Highest Priority)
The 13.53° jitter is unacceptable. This is the main problem the user is experiencing.

```bash
# Build with more conservative Kp/Kd ratio
# Edit src/pid_config.h:
```

**Conservative Tuning Template:**
```cpp
// Voltage controller (inner velocity loop)
#define MOTOR0_VELOCITY_KP 3.0      // Reduced from 5.440
#define MOTOR0_VELOCITY_KI 10.0     // Reduced from 31.561
#define MOTOR0_VELOCITY_KD 1.5      // Reduced from 0.234 (increase damping)

// Angle controller (outer position loop)
#define MOTOR0_PID_KP 4.0           // Reduced from 8.257
#define MOTOR0_PID_KI 15.0          // Tuned Ki for drift
#define MOTOR0_PID_KD 2.5           // Increased from 0.546 (strong damping)
```

### Step 2: Re-Run Auto-Tuning
```bash
# Re-run with intermediate safety factor
platformio run -e pico_1motor_limited && \
  platformio run -e pico_1motor_limited --target upload && \
  python3 test/calibrate_pid.py --motor 0 --safety-factor 0.45
```

### Step 3: Validate Quality
```bash
# Run step response test to verify improvement
python3 test/calibrate_pid.py --motor 0 --step-only
```

**Success Criteria:**
- ✓ Noise <1.0° (aim for <0.5°)
- ✓ Drift <0.1°
- ✓ Stability >85%
- ✓ Settling <2.5s

## Tuning Trade-offs

```
Increase Kp → Faster response BUT more overshoot & noise
Increase Kd → Damping (reduces noise) BUT slower response & sluggish feel
Increase Ki → Better drift correction BUT can cause oscillation

The current tuning is OVER-AGGRESSIVE:
- High Ki (31.2) trying to force position holding → causes jitter
- Low Kd (0.546) can't damp the oscillations → noise persists
```

## Hardware Checks

If adjusting gains doesn't fix the noise, check hardware:

### 1. Encoder Connection
```bash
# Test encoder responsiveness:
python3 test/debug_joystick.py --monitor
# Manually rotate motor by hand
# Position should change smoothly without jumps
```

**Signs of bad encoder:**
- Large position jumps (>0.5° per sample)
- Periodic noise at specific rotation angles
- I2C timeouts in debug output

### 2. Power Supply
```bash
# Check for voltage sag under load
# Motor should have dedicated stable 12V supply
# Verify total current budget: dual motors ~2-3A at full torque
```

**Signs of bad power:**
- Noise increases with motor velocity
- Oscillation at specific frequencies (noise ripple)
- Motor loses position when other devices power on

### 3. Mechanical Slack
```bash
# Manual test: Try rotating motor shaft by hand
# Feel for play/backlash in coupling or gearbox
# Notches or discontinuities = mechanical slack
```

## Reference: Quality Score Calculation

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

## Next Steps

1. **Apply conservative tuning** from Step 1 above
2. **Build & upload**: `platformio run -e pico_1motor_limited --target upload`
3. **Test**: `python3 test/calibrate_pid.py --motor 0 --step-only`
4. **If still poor**: Increase Kd more aggressively
5. **If overshoot appears**: Reduce Kp or increase Kd/Ki ratio
6. **If drift returns**: Increase Ki slightly

## Testing Protocol

Each tuning iteration:

```bash
# 1. Update pid_config.h with new gains
# 2. Rebuild and upload
platformio run -e pico_1motor_limited --target upload

# 3. Wait 5 seconds for motor to cool/settle
sleep 5

# 4. Run quality test (same as user manual test)
python3 test/calibrate_pid.py --motor 0 --step-only

# 5. Record Quality Score trend (should go UP)
# 6. Circle back to step 1 until score >60
```

---

**Status**: User reported motor is "quite noisy and won't hold position if disturbed"
- ✓ Root cause identified: Quality score 28.4/100 (POOR)
- ✓ Noise identified as PRIMARY issue (13.53°)
- ✓ Drift identified as SECONDARY issue (24.64°)
- 🔄 **Next**: Apply tuning fixes above and re-evaluate
