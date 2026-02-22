# Dual-Loop PID Tuning Guide

## Architecture Overview

SimpleFOC uses a cascade/nested control structure:

```
Target Position (CC#64 MIDI)
        ↓
    [P_angle] → Outer Loop (Position Control)
        ↓
    Target Velocity
        ↓
    [PID_velocity] → Inner Loop (Speed Control)
        ↓
    Target Voltage
        ↓
    Motor
```

**Key Insight**: Both controllers work together:
- **Outer Loop (P_angle)**: Takes position error → outputs velocity commands
- **Inner Loop (PID_velocity)**: Takes velocity error → outputs voltage commands

## Tuning Strategy

### Phase 1: Tune Inner Loop (Velocity Controller) FIRST
- **Test**: `python3 test/calibrate_pid.py --velocity-only`
- **What it does**: Sends speed commands (0% → 90% power @ 3 Hz)
- **Goal**: Optimize smooth, stable velocity tracking
- **Updates**: `MOTOR0_VELOCITY_P`, `MOTOR0_VELOCITY_I`, `MOTOR0_VELOCITY_D`
- **Period**: Fast (~300ms oscillation at limit)

### Phase 2: Tune Outer Loop (Angle Controller) SECOND
- **Test**: `python3 test/calibrate_pid.py --angle-only`
- **What it does**: Sends position commands (25→95 CC# @ 2 Hz)
- **Goal**: Accurate position control with minimal overshoot
- **Updates**: `MOTOR0_PID_P`, `MOTOR0_PID_I`, `MOTOR0_PID_D`
- **Period**: Slower (~500ms oscillation at limit)

### Phase 3: Validate Combined System
- **Test**: `python3 test/calibrate_pid.py --step-only`
- **What it does**: Sends 45° step input, measures settle time
- **Goal**: Confirm both loops work well together
- **Check**: <5% overshoot, <2s settling time

### Full Calibration (All at Once)
```bash
python3 test/calibrate_pid.py
```

Runs all three phases and outputs final configuration for `pid_config.h`.

## Current Tuned Gains (Motor 0)

### Velocity Controller (Inner Loop)
```cpp
#define MOTOR0_VELOCITY_P  5.439914f   // Fast speed tracking
#define MOTOR0_VELOCITY_I  31.561124f  // Steady-state accuracy
#define MOTOR0_VELOCITY_D  0.234408f   // Smooth response
```

### Angle Controller (Outer Loop)  
```cpp
#define MOTOR0_PID_P  8.257329f    // Position tracking gain
#define MOTOR0_PID_I  31.197493f   // Position steady-state
#define MOTOR0_PID_D  0.546386f    // Position damping
```

## Usage Examples

### Run Complete Dual-Loop Calibration
```bash
python3 test/calibrate_pid.py
```
**Output**: Recommended gains for both controllers, step response validation

### Tune Only Velocity (Inner Loop)
```bash
python3 test/calibrate_pid.py --velocity-only
```
**Use when**: Motor speed response seems sluggish or oscillates excessively

### Tune Only Angle (Outer Loop)
```bash
python3 test/calibrate_pid.py --angle-only
```
**Use when**: Position control overshoots or settles too slowly

### Monitor Motor Dynamics
```bash
python3 test/calibrate_pid.py --monitor-only
```
**Output**: High-speed position/velocity data (100+ Hz sampling)

### Ramp Test Only (Sanity Check)
```bash
python3 test/calibrate_pid.py --ramp-only
```
**Use when**: Verifying motor is responsive before full calibration

## Interpreting Relay Test Results

### Key Metrics from Relay Test Output

```
Period (Pu): 0.345s      ← Ultimate period (1/frequency)
Frequency: 2.90 Hz       ← Oscillation frequency
Amplitude: 2.330 rad     ← Peak-to-peak response magnitude
Ultimate Gain (Ku): 13.948 ← System's critical gain
```

**Interpretation**:
- **Smaller Pu** = Faster, more responsive system (lower period → higher frequency)
- **Larger Ku** = More stable system (easier to control)
- **Amplitude** = Motor's movement range during square wave

### Ziegler-Nichols Calculation

Gains are computed automatically using:
```
Kp = 0.6 * Ku * 0.65        (proportional)
Ki = 1.2 * Ku / Pu * 0.65   (integral)
Kd = 3.0 * Ku * Pu / 40 * 0.65  (derivative)
```

The `0.65` factor is a conservative safety margin to prevent oscillation.

## Troubleshooting

### Motor Not Responding to MIDI Commands
- Check MIDI port connectivity
- Verify encoder is wired correctly (I2C, address 0x36)
- Ensure motor power supply is sufficient (>5V)

### Calibration Hangs or Timeouts
- Motor may not be responding to MIDI
- Try `--ramp-only` to verify motor moves at all
- Check serial connection (115200 baud)

### Aggressive Oscillations After Tuning
- Reduce `Kp` and `Ki` for the affected controller
- Increase `Kd` (derivative) for damping
- Re-run calibration with `--debug` flag for verbose output

### Slow Position Tracking
- Increase outer loop `MOTOR0_PID_P`
- Ensure inner loop velocity controller is tuned first
- Check for mechanical friction or load

## Implementation Notes

### Firmware Structure
- **main.cpp line 378-380**: Applies angle PID gains
- **main.cpp line 382-384**: Applies velocity PID gains
- **include/pid_config.h**: Central configuration file

### High-Speed Monitoring
- HighSpeedMonitor achieves 100+ Hz sampling rate
- Firmware outputs compact "A=X.XX T=Y.YY" format every 10ms
- Enables detailed dynamics analysis for both controllers

### Calibration Workflow Phases
1. **Phase 1 (Ramp)**: Motor characterization (endless vs limited)
2. **Phase 2a (Velocity Relay)**: Inner loop tuning (smooth speed response)
3. **Phase 2b (Angle Relay)**: Outer loop tuning (accurate positioning)
4. **Phase 3 (Step Response)**: Combined system validation

## References

- **SimpleFOC Docs**: https://docs.simplefoc.com/motion_control
- **Ziegler-Nichols Method**: https://en.wikipedia.org/wiki/Ziegler%E2%80%93Nichols_method
- **Cascade Control**: https://en.wikipedia.org/wiki/Cascade_control
- **SimpleFOC Nested Loops**: Angle loop outputs velocity command to velocity loop

## Future Enhancements

- [ ] Auto-detect motor bounds and linearize response curve
- [ ] Support for soft-start ramp (configurable MOTOR0_ACCELERATION)
- [ ] Real-time tuning via SimpleFOCStudio integration
- [ ] Velocity feedforward terms for disturbance rejection
- [ ] Estimated current mode for sensorless operation
