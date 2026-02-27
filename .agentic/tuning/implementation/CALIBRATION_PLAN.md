# Calibration & Testing Integration Guide

## Status: Phase 2 Complete ✅

### Completed: Strict Test Validation + High-Speed Monitor
- ✅ Test suite validates motor angles **MUST** increase monotonically during sweep
- ✅ HighSpeedMonitor utility (100+ Hz sampling) integrated into test suite
- ✅ Optional TEST 5B shows actual motor dynamics

### In Progress / Planned

#### Phase 3: Holistic PID Tuning (angle vs velocity)
Currently, calibrate_pid.py applies Ziegler-Nichols only to **angle controller**.

SimpleFOC has **two nested loops**:
1. **Angle controller** (outer): P_angle feedback → velocity command
2. **Velocity controller** (inner): PID_velocity feedback → voltage command

For smooth, stable control, both need tuning:

**Angle Controller (currently tuned)**:
- Kp_angle: Proportional gain for angle error
- Ki_angle: Integral gain (typically 0 for position)
- Kd_angle: Derivative (damping)

**Velocity Controller (currently fixed at SimpleFOC defaults)**:
- Kp_vel: Proportional gain (default: 0.5)
- Ki_vel: Integral gain (default: 10.0) ← **Critical for smooth ramps!**
- Kd_vel: Derivative (default: 0.0)

#### Recommended Approach

1. **Tune angle controller first** (current relay method) → Kp_angle, Kd_angle
2. **Monitor velocity response** during step response tests
3. **If velocity overshoot present**: Increase Kp_vel, tune Ki_vel
4. **If velocity jerky/oscillating**: Increase Kd_vel

#### Integration Points

New calibration workflow:
```
  Phase 1: Ramp test
       ↓
  Phase 2a: Relay tune angle controller → Kp_angle, Kd_angle 
       ↓
  Phase 2b: Monitor velocity during step response
       ↓
  Phase 2c: If needed, relay-tune velocity controller
       ↓
  Phase 3: Validation with combined tuning
```

## Usage Reference

### Test Suite (Strict Validation)
```bash
   bash test/run_tests.sh pico_1motor_endless
```

**New behavior**:
- TEST 5 (Motor Sweep): **FAILS** if angles don't increase monotonically
- TEST 5B (optional): Captures high-speed dynamics at ~2 Hz (limited by serial output)

### Calibration Script (Planned Enhancements)
```bash
# Current (angle tuning only)
python3 test/calibrate_pid.py

# Future (with holistic approach)
python3 test/calibrate_pid.py --tune-velocity  # Add velocity tuning
python3 test/calibrate_pid.py --monitor-only   # Just capture dynamics
```

### High-Speed Monitor (Standalone)
```python
from test.motor_monitor import HighSpeedMonitor
import serial

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
monitor = HighSpeedMonitor(ser, buffer_size=1000)
samples = monitor.collect_samples(duration=5.0, target_hz=100)

stats = monitor.get_stats()
print(f"Sample rate: {stats['sample_rate']:.1f} Hz")
print(f"Velocity: {stats['velocity_mean']:.4f} rad/s (avg)")
```

## File Structure

```
test/
├── motor_monitor.py           # NEW: High-speed motor sampling utility
├── test_suite_automated.py    # UPDATED: Strict validation + high-speed test
├── calibrate_pid.py           # Will add: Holistic angle+velocity tuning
├── RAMP_TEST_GUIDE.md        # Ramp test documentation
└── run_tests.sh              # Build, upload, run tests

include/
└── pid_config.h              # PID gains (angle + velocity)
```

## Next Steps

1. **Integrate motor_monitor into calibrate_pid.py**
   - Replace slow serial parsing with HighSpeedMonitor
   - Add --monitor-only mode for dynamics capture
   
2. **Implement velocity controller tuning**
   - Detect velocity oscillation from step response
   - Auto-tune Ki_vel for smooth ramps
   - Separate angle vs velocity Ziegler-Nichols
   
3. **Add ramp test to calibration**
   - Use ramp_test() to characterize motor response
   - Measure max velocity from ramp dynamics
   - Inform velocity controller gains
   
4. **Holistic summary**
   - Report both angle and velocity PID values
   - Tuning quality metrics (overshoot %, rise time, settling time)
   - Confidence scoring based on oscillation detection

## Technical Notes

### Serial Output Rate Limitation
Device outputs debug at ~1 Hz (once per second), limiting HighSpeedMonitor to ~1.7 Hz effective sample rate in test suite. For higher-frequency tuning, would need internal firmware logging buffer.

### SimpleFOC Nested Control Architecture
```
MIDI CC → Angle Target
    ↓
[Angle Controller: P_angle.P/I/D]
    ↓
Velocity Target
    ↓
[Velocity Controller: PID_velocity.P/I/D]  
    ↓
Voltage Command  
    ↓
Motor Driver → Actual Angle
```

Each loop has different tuning requirements. Angle controller responds to target position, velocity controller responds to velocity error and ensures smooth motion.

