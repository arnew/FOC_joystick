# Motor Control Tuning Report
**Date**: 2026-02-28  
**Device**: /dev/ttyACM0 (RP2040 + AS5600 + BLDC Motor)  
**Test Suite Version**: quality_goals_test_suite.py + diagnostic_tuning_report.py

---

## Executive Summary

**Motor Status**: ✅ Motor responds to commands and moves  
**Control Quality**: ❌ **FAILS quality goals** - Significant tuning required  
**Success Rate**: 8% of tests passing (2/24 matrix tests)

### Key Findings:
- ✅ Motor physically moves in response to SimpleFOC Commander 'T' commands
- ✅ Overshoot minimal on simple cardinal sequences (0.0-0.7°)
- ❌ High steady-state error (avg 9.07°, target: <1°)
- ❌ Only 25% of positions settle within tolerance
- ❌ Large overshoot on some positions (up to 350°)
- ❌ SimpleFOC Commander PID query returning corrupt data

---

## Current Configuration (from pid_config.h)

```cpp
// Angle Controller PID
MOTOR0_PID_P:  10.0   // (20.0 * 0.5)
MOTOR0_PID_I:  0.0
MOTOR0_PID_D:  0.5

// Velocity Controller PID  
MOTOR0_VELOCITY_P:  0.125  // (0.5 * 0.25)
MOTOR0_VELOCITY_I:  0.0    // (10.0 * 0.0)
MOTOR0_VELOCITY_D:  0.0

// Limits
MOTOR0_VOLTAGE_LIMIT:  2.0V
MOTOR0_CURRENT_LIMIT:  2.0A
MOTOR0_ACCELERATION:   10.0 rad/s²
MOTOR0_LPF_ANGLE_TF:   0.005s (5ms)
```

**Angle Limits**: Configured (max ~350°), but readings show wrap/clamp behavior

---

## Test Results

### Matrix Test (24 tests across 6 sequences):

| Sequence | Positions | Test A (Res) | Test B (Speed) | Test C (Hold) | Test D (Overshoot) | Score |
|----------|-----------|--------------|----------------|---------------|--------------------|-------|
| 1_cardinal | 0,90,180,270 | ✗ Timeout | ✗ Stats fail | ✗ Timeout | ✅ 0.0° | **1/4** |
| 2_full_grid | 0,45,90,135,180,225,270,315 | ✗ Timeout | ✗ Stats fail | ✗ Timeout | ✅ 0.0-0.7° | **1/4** |
| 3_tame_slow | 0,90,180,270 (8s hold) | ✗ Timeout | ✗ Stats fail | ✗ Timeout | ✗ | 0/4 |
| 4_fast_rapid | 0,180,45,225,90,270 | ✗ Timeout | ✗ Stats fail | ✗ Timeout | ✗ | 0/4 |
| 5_random_walk | 20 random | ✗ Timeout | ✗ Stats fail | ✗ Timeout | ✗ | 0/4 |
| 6_boundary | 355,359,0,1,5 | ✗ Timeout | ✗ Stats fail | ✗ Timeout | ✗ | 0/4 |

**Overall**: 2/24 tests passed (8%)

### Diagnostic Settling Test (8 positions):

| Target | Final Error | Settled? | Settle Time | Overshoot | RMS Error |
|--------|-------------|----------|-------------|-----------|-----------|
| 0°     | 14.73°      | ✗        | N/A         | **350.65°** | 95.78° |
| 45°    | 0.48°       | ✅       | 1195ms      | 0.26°     | 15.79° |
| 90°    | 12.08°      | ✗        | N/A         | 0.00°     | 24.53° |
| 135°   | 14.68°      | ✗        | N/A         | 0.00°     | 29.63° |
| 180°   | 10.40°      | ✗        | N/A         | 0.00°     | 29.29° |
| 225°   | 0.97°       | ✅       | 1176ms      | 0.00°     | 24.93° |
| 270°   | 6.21°       | ✗        | N/A         | 0.00°     | 19.72° |
| 315°   | 13.05°      | ✗        | N/A         | 0.00°     | 23.81° |

**Statistics**:
- Settled: 2/8 (25%)
- Average final error: **9.07°** (target: <1°)
- Average overshoot: **43.86°** (target: <5°)
- Average settle time: **1185ms** (for positions that settled)
- Oscillation detected: 1/8 positions

---

## Tolerance Analysis

### Achieved vs. Target:

| Quality Goal | Target | Achieved | Status |
|--------------|--------|----------|--------|
| **Resolution** | ±1° | ~9-15° typical, 0.5-1° at 2 positions | ❌ **9x worse** |
| **Speed** | ≥60 rpm (360° ≤ 6s) | Unable to measure reliably | ❌ **Not tested** |
| **Position Hold** | ±1°, <1° variance | Unable to hold within tolerance | ❌ **Failed** |
| **Overshoot** | <5° | 0-0.7° on simple moves, **350°** on wrap | ⚠️ **Inconsistent** |
| **Settling Time** | <2s (implied) | ~1.2s for 25% of positions | ⚠️ **Partial** |

---

## Root Cause Analysis

### 1. **High Steady-State Error (9.07° average)**

**Symptoms**:
- Motor stops far from target (6-15° typical)
- Only 25% of positions reach ±1° tolerance
- Suggests insufficient control authority

**Likely Causes**:
- **P gain too low** (10.0 may be insufficient for this motor/load)
- **I gain is zero** (no integral correction for steady-state error)
- **Friction/cogging** exceeding control authority
- **Sensor alignment issues** (mechanical offset)

### 2. **Massive Overshoot at 0° (350°)**

**Symptoms**:
- 350° overshoot when targeting 0°
- Suggests wrap-around or limit boundary issue

**Likely Causes**:
- **Angle wrapping near 0°/360° boundary** not handled properly
- Motor may be taking "long way around" (359° → 0° via 180°)
- Limit configuration may be causing unexpected behavior

### 3. **Inconsistent Performance**

**Symptoms**:
- 45° and 225° settle well (0.48°, 0.97°)
- Other positions fail badly (6-15° error)
- Suggests position-dependent behavior

**Likely Causes**:
- **Mechanical cogging** at certain rotor positions
- **Sensor calibration issues** (AS5600 offset/gain)
- **Magnetic field non-uniformity**
- **Gravity/load effects** if motor is oriented vertically

### 4. **Statistics Query Failure**

**Symptoms**:
- 'S' command returns position data instead of statistics
- PID query returns nonsense values (angle_D=6.12, voltage_limit=0.0)

**Likely Causes**:
- Commander interface not properly parsing 'S' command
- Statistics print output not being captured correctly
- Serial buffer timing issues

---

## Tuning Recommendations

### Priority 1: Fix Steady-State Error

**Current**: P=10.0, I=0.0, D=0.5

**Option A - Increase P gain** (aggressive response):
```cpp
MOTOR0_PID_P:  15.0  // Increase from 10.0
MOTOR0_PID_I:  0.0
MOTOR0_PID_D:  0.5
```
- **Pros**: Faster response, more control authority
- **Cons**: May increase overshoot and oscillation
- **Test**: Monitor for oscillation, adjust D if needed

**Option B - Add I gain** (eliminate steady-state error):
```cpp
MOTOR0_PID_P:  10.0  // Keep current
MOTOR0_PID_I:  0.3   // Add integral action
MOTOR0_PID_D:  0.5
```
- **Pros**: Eliminates steady-state error, P gain stays conservative
- **Cons**: Can cause windup, slower settling
- **Test**: Monitor for overshoot and windup

**Option C - Balanced approach** (recommended):
```cpp
MOTOR0_PID_P:  12.0  // Moderate increase
MOTOR0_PID_I:  0.2   // Small integral term
MOTOR0_PID_D:  0.8   // Increase damping
```
- **Pros**: Addresses both response and steady-state error
- **Cons**: Requires more testing iterations
- **Test**: This is the recommended starting point

### Priority 2: Fix 0° Wrap-Around Issue

**Investigation needed**:
1. Check limit mode configuration (wrap vs clamp)
2. Verify AS5600 angle wrapping behavior
3. Test if SimpleFOC handles 359° → 0° transitions correctly

**Potential fixes**:
```cpp
// In motor_control.cpp, ensure shortest path logic
float error = target - current;
if (error > PI) error -= 2*PI;
if (error < -PI) error += 2*PI;
```

### Priority 3: Increase Control Authority

**Current voltage limit is conservative**:
```cpp
MOTOR0_VOLTAGE_LIMIT:  3.0f  // Increase from 2.0V (if motor supports)
```

**Check motor specifications**:
- Most small BLDC motors handle 5-12V
- Gradual increase: 2.0V → 3.0V → 4.0V → test each step
- Monitor motor temperature

### Priority 4: Velocity Controller Tuning

**Current velocity loop is disabled** (I=0):
```cpp
MOTOR0_VELOCITY_P:  0.25   // Increase from 0.125
MOTOR0_VELOCITY_I:  5.0    // Re-enable (was 0.0)
MOTOR0_VELOCITY_D:  0.0
```

This will smooth transitions and reduce jerk.

### Priority 5: Sensor Calibration

**AS5600 may need calibration**:
1. Run SimpleFOC sensor alignment routine
2. Check for mechanical offset (0° position)
3. Verify magnetic field strength (AS5600 AGC register)
4. Test sensor resolution (should be 12-bit = 0.09° resolution)

**Command to check sensor**:
```bash
# Via SimpleFOC Commander
M0.sensor?  # Should return sensor type and resolution
```

---

## Immediate Action Plan

### Step 1: Apply Balanced PID Tuning (15 minutes)

Edit `include/pid_config.h`:
```cpp
#define MOTOR0_PID_P  12.0f    // Was 10.0
#define MOTOR0_PID_I  0.2f     // Was 0.0
#define MOTOR0_PID_D  0.8f     // Was 0.5

#define MOTOR0_VOLTAGE_LIMIT  3.0f  // Was 2.0 (if motor supports)
```

Rebuild and test:
```bash
platformio run --environment pico_1motor_endless --target upload
python3 test/diagnostic_tuning_report.py
```

**Expected improvement**: Steady-state error should drop to 2-4° range

### Step 2: Fix Wrap-Around Handling (30 minutes)

Investigate `motor_control.cpp` target setting logic:
- Add shortest-path angle calculation
- Test 355° → 5° transitions specifically
- Verify limit mode is set correctly

### Step 3: Re-run Full Test Suite (5 minutes)

```bash
python3 test/quality_goals_test_suite.py --matrix --json results_after_tuning.json
```

Compare before/after metrics.

### Step 4: Iterate (repeat as needed)

Based on new results:
- If still high error: increase P to 15.0
- If oscillating: reduce P to 10.0, increase D to 1.2
- If slow: increase voltage limit to 4.0V

---

## Expected Outcomes After Tuning

### Realistic Targets (after 2-3 tuning iterations):

| Metric | Current | After Basic Tuning | After Advanced Tuning |
|--------|---------|-------------------|----------------------|
| **Settled positions** | 25% (2/8) | 75% (6/8) | >90% (7-8/8) |
| **Average error** | 9.07° | 2-3° | <1° |
| **Overshoot** | 0-350° | <10° | <5° |
| **Settle time** | 1200ms | 800ms | <500ms |

### Quality Goal Achievement Forecast:

| Goal | Current | After Tuning | Achievable? |
|------|---------|--------------|-------------|
| Resolution ±1° | ❌ 8% | ⚠️ 60-70% | ✅ Yes (with calibration) |
| Speed ≥60rpm | ❌ N/A | ✅ Yes | ✅ Yes (motor capable) |
| Hold <1° variance | ❌ Failed | ⚠️ Marginal | ✅ Yes (with I term) |
| Overshoot <5° | ⚠️ 8% | ✅ 70-80% | ✅ Yes (with D tuning) |

---

## Hardware Considerations

### Potential Issues to Check:

1. **AS5600 Sensor**:
   - Magnet distance from sensor (should be 0.5-3mm)
   - Magnetic field strength (check AGC register, target: 64-255)
   - Sensor alignment (rotation axis centered)

2. **Motor Mechanical**:
   - Bearing friction (should spin freely by hand)
   - Cogging torque (magnets creating detents)
   - Load/inertia (test with no load first)

3. **Electrical**:
   - Power supply stability (voltage sag under load)
   - Motor phase resistance (affects voltage limit choice)
   - PWM frequency (SimpleFOC default usually fine)

4. **SimpleFOC Configuration**:
   - Sensor direction (CW vs CCW)
   - Motor pole pairs (must match actual motor)
   - Electrical vs mechanical angle (ratio = pole_pairs)

---

## Tools and Next Steps

### Diagnostic Tools Available:

✅ Already created:
- `test/quality_goals_test_suite.py` - Comprehensive matrix testing
- `test/diagnostic_tuning_report.py` - Settling analysis with traces
- `.agentic/QUALITY_GOALS_TEST_PLAN.md` - Test specifications

🔧 Next tools to create:
- `test/pid_auto_tune.py` - Ziegler-Nichols auto-tuning
- `test/sensor_calibration.py` - AS5600 diagnostic and calibration
- `tools/plot_traces.py` - Visualize position traces from diagnostic

### Testing Workflow:

```bash
# 1. Apply tuning changes in pid_config.h
# 2. Rebuild and upload
platformio run --environment pico_1motor_endless --target upload

# 3. Wait for device ready (5s)
sleep 5

# 4. Run diagnostic
python3 test/diagnostic_tuning_report.py --output results_v2.json

# 5. Compare results
python3 -m json.tool results_v2.json | grep -A 20 summary

# 6. If good, run full matrix
python3 test/quality_goals_test_suite.py --matrix --json matrix_v2.json
```

---

## Conclusion

The motor control system is **functional but requires tuning**. The motor responds to commands and can achieve good performance at certain positions (45°, 225°), indicating the hardware is capable. The main issues are:

1. **Insufficient P gain** and **missing I term** causing high steady-state error
2. **Wrap-around logic** issue at 0°/360° boundary
3. **Position-dependent performance** suggesting sensor or mechanical issues

**Recommended immediate action**: Apply the balanced PID tuning (P=12, I=0.2, D=0.8) and re-test. This should improve from 25% to 75% success rate within 30 minutes of work.

**Long-term**: Investigate sensor calibration and mechanical issues for the remaining problem positions. With proper tuning and calibration, all quality goals are achievable with this hardware.

---

## References

- SimpleFOC Documentation: https://docs.simplefoc.com/tuning
- Ziegler-Nichols Tuning: https://en.wikipedia.org/wiki/Ziegler–Nichols_method
- AS5600 Datasheet: https://ams.com/as5600
- Test Results: `diagnostic_tuning_report.json`, `test_results_matrix.json`
