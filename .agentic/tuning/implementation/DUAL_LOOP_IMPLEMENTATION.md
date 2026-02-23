# Dual-Loop PID Calibration System - Implementation Summary

**Date**: February 22, 2026  
**Status**: ✅ Complete and Tested

## Overview

Implemented a complete dual-loop PID tuning system for SimpleFOC that separately calibrates:
1. **Velocity Controller** (inner loop) - for smooth speed response
2. **Angle Controller** (outer loop) - for accurate positioning

## What Changed

### 1. Calibration Script (`test/calibrate_pid.py`)

**New Methods**:
- `relay_test(controller_type='angle'|'velocity')` - Separate relay tests for each loop
- Enhanced to use `HighSpeedMonitor` (100+ Hz sampling) for both angle and velocity tuning

**New CLI Modes**:
```bash
python3 test/calibrate_pid.py                 # Full dual-loop (all phases)
python3 test/calibrate_pid.py --velocity-only # Tune inner loop only  
python3 test/calibrate_pid.py --angle-only    # Tune outer loop only
python3 test/calibrate_pid.py --ramp-only     # Sanity check only
python3 test/calibrate_pid.py --step-only     # Validation only
python3 test/calibrate_pid.py --monitor-only  # Real-time dynamics
```

**Updated Features**:
- Velocity relay test: 0% → 90% power @ 3 Hz (tunes speed response)
- Angle relay test: 25→95 CC# @ 2 Hz (tunes position control)
- Separate Ziegler-Nichols calculations for each controller
- Combined step response validation

### 2. Configuration File (`include/pid_config.h`)

**New Tuned Gains for Motor 0** (from relay calibration):

Velocity Controller (Inner Loop):
```cpp
#define MOTOR0_VELOCITY_P  5.439914f
#define MOTOR0_VELOCITY_I  31.561124f
#define MOTOR0_VELOCITY_D  0.234408f
```

Angle Controller (Outer Loop):
```cpp
#define MOTOR0_PID_P  8.257329f
#define MOTOR0_PID_I  31.197493f
#define MOTOR0_PID_D  0.546386f
```

**Better Documentation**:
- Explains cascade architecture
- References calibration workflow
- Shows SimpleFOC control loop structure

### 3. Test Suite (`test/test_suite_automated.py`)

**Optional High-Speed Monitor Mode**:
```bash
python3 test/test_suite_automated.py          # Basic tests (no monitor)
python3 test/test_suite_automated.py --enable-monitor  # Include TEST 5B
```

**Improvements**:
- Tests faster (no mandatory 5-second monitor)
- Monitor available on-demand for detailed diagnostics
- Format-agnostic parsing (old + new firmware output)

### 4. Firmware (`src/main.cpp`)

**Debug Output Rate Increased**:
- Changed: Every 1000ms (1 Hz) → Every 10ms (100 Hz)
- Format: Verbose "Angle: X rad..." → Compact "A=X.XX T=Y.YY"
- Enables true high-speed monitoring of both controllers

### 5. Documentation (`/tuning/guides/DUAL_LOOP_TUNING.md`)

**New Guide Includes**:
- Architecture diagram (cascade control)
- Step-by-step tuning workflow
- Current calibrated gains
- Troubleshooting guide
- Interpretation of relay test metrics
- Implementation notes

## Key Features

✅ **Separate calibration for both controllers**
- Inner loop (velocity) tuned for smooth speed tracking
- Outer loop (angle) tuned for accurate positioning
- Both can be tuned independently or together

✅ **100+ Hz high-speed monitoring**
- Real-time position and velocity capture
- Enables detailed dynamics analysis
- Available in all test/calibration modes

✅ **Backward compatible**
- Firmware parses both old and new debug formats
- Test suite works with any format
- Calibration script auto-detects motor responsiveness

✅ **Well-documented**
- Comprehensive tuning guide
- Ziegler-Nichols calculations explained
- Troubleshooting procedures provided

## Test Results

**Full Dual-Loop Calibration Output**:
```
✓ Phase 1 (Ramp):         342 samples @ 86 Hz
  Motor type: Endless
  Range: 4.44 rad (254°)

✓ Phase 2a (Velocity):    504 samples @ 101 Hz
  Oscillation: 2.90 Hz
  Ultimate Gain: 13.948
  
✓ Phase 2b (Angle):       496 samples @ 99 Hz  
  Oscillation: 1.89 Hz
  Ultimate Gain: 21.173

✓ Phase 3 (Step Response): 277 samples @ 138 Hz
  Overshoot: 4.4% (target: <5%)
  Settling: 2.48s
```

**Individual Mode Tests**:
- ✅ `--velocity-only`: Works, produces velocity gains
- ✅ `--angle-only`: Works, produces angle gains  
- ✅ `--ramp-only`: Works, characterizes motor
- ✅ `--monitor-only`: Works, captures dynamics

**Firmware Tests**:
- ✅ System connectivity: Device responsive
- ✅ Motor response to MIDI: Position tracking works
- ✅ High-speed monitor: 100+ Hz sampling achieved
- ✅ Test suite: Runs with/without optional monitor

## Architecture Details

### SimpleFOC Cascade Control
```
Position Error (rad)
        ↓
    [P_angle]
    Proportional gain for position
        ↓
    Velocity Command (rad/s)
        ↓
    [PID_velocity]
    Full PID for speed control
        ↓
    Voltage/Current Command
        ↓
    Motor
```

### Tuning Sequence (Why Order Matters)
1. **Tune velocity first** (inner loop)
   - Faster, tighter control loop
   - Affects how quickly motor responds to commands
   - Smaller oscillation period (~300ms)

2. **Then tune angle** (outer loop)
   - Uses velocity output from above
   - Controls final position accuracy
   - Larger oscillation period (~500ms)

3. **Validate together** (step response)
   - Both controllers working as unit
   - Measures combined system behavior
   - Confirms no instability

## File Changes Summary

| File | Changes | Purpose |
|------|---------|---------|
| `test/calibrate_pid.py` | +300 lines | Dual-loop relay tuning, separate velocity/angle tests |
| `include/pid_config.h` | +25 lines | New tuned gains, better documentation |
| `src/main.cpp` | -2 lines | Output rate: 1Hz→100Hz, compact format |
| `test/test_suite_automated.py` | +150 lines | Optional monitor, CLI flag support |
| `.agentic/DUAL_LOOP_TUNING.md` | NEW | Comprehensive tuning guide |

## Next Steps for Users

1. **To re-tune for different hardware**:
   ```bash
   python3 test/calibrate_pid.py
   # Copy new gains from output into include/pid_config.h
   # Rebuild: platformio run -e pico_1motor_endless
   ```

2. **To fine-tune specific loop**:
   ```bash
   python3 test/calibrate_pid.py --velocity-only  # Speed response
   python3 test/calibrate_pid.py --angle-only     # Position control
   ```

3. **To monitor motor behavior in real-time**:
   ```bash
   python3 test/test_suite_automated.py --enable-monitor
   # Or: python3 test/calibrate_pid.py --monitor-only
   ```

## Known Limitations

- Motor sweep test shows non-monotonic behavior (expected with high gains)
- Joystick output scaling not yet implemented (TEST 4 skipped)
- Conservative safety factor (0.65) ensures stability but may be tuned up
- Dual-motor configuration templates provided but not tested

## Lessons Learned

1. **Nested control requires sequential tuning** - Inner loop must stabilize first
2. **High-speed monitoring essential** - 1 Hz insufficient for controller analysis
3. **Separate relay tests per loop** - Different frequencies reveal each controller's dynamics
4. **Safety margins matter** - 0.65 factor prevents oscillation on real hardware

## References

- SimpleFOC Documentation: https://docs.simplefoc.com/motion_control
- Ziegler-Nichols Method: https://en.wikipedia.org/wiki/Ziegler%E2%80%93Nichols_method
- Cascade Control Theory: https://en.wikipedia.org/wiki/Cascade_control
- RP2040 SimpleFOC: https://docs.simplefoc.com/microcontrollers?q=rp2040

---

**Implementation Status**: ✅ Complete, tested, and documented
**Ready for**: Hardware validation and fine-tuning
**Tested With**: RP2040 Pico + AS5600 encoder + SimpleFOC 2.4.0
