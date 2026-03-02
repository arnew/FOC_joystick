# Motor Sweep Test Failure - Troubleshooting Guide

**Status**: Motor not responding to MIDI CC#64 commands (all angles read 0.0 rad)

## Problem Summary

The hardware test `test_motor_sweep()` sends MIDI CC#64 commands across a range (0-64) and expects the motor to move with excursion ≥ 0.06 rad (~3.4°). Instead, all angle readings remain at 0.0 rad, indicating the motor is not moving.

### Test Flow
1. Send MIDI CC#64 = 0 → target_angle should be 0.0 rad
2. Switch MIDI CC#64 = 16 → target_angle should be 0.504 rad (~28.8°)
3. Switch MIDI CC#64 = 32/48/64 → target angles should increase monotonically
4. Measure actual motor angle from debug output
5. **FAIL**: All readings are 0.0 rad, excursion = 0.0 rad (need ≥ 0.06)

## Diagnostic Output Added (Commit 9525cda)

The firmware now prints initialization and operation diagnostics:

```
[MOTOR 0] Initializing driver...
[MOTOR] Driver OK
[MOTOR] Initializing sensor...
[MOTOR] Sensor init complete
[MOTOR] Angle voltage limit: 2.0
[MOTOR] PID P=10.0 I=0.0 D=0.5
[MOTOR] Running motor->init()...
[MOTOR] Motor init complete
[MOTOR] Running motor->initFOC() - sensor calibration...
[MOTOR] Motor shaft_angle after initFOC: 0.000
[MOTOR] Initialization complete
```

**During operation with stuck motor warnings:**
```
[MOTOR] WARNING: Motor angle stuck at 0.0 with target T=0.504
```

## Diagnosis Tree

### Check 1: Motor Initialization (From Serial Output)

**If `[MOTOR] Initialization complete` appears:**
- ✓ Motor hardware is detected
- ✓ Driver (PWM) initialized
- ✓ Sensor I2C communication working
- Go to Check 2

**If motor init hangs or errors appear:**
- ✗ Hardware initialization failed
- Likely cause: I2C bus broken, sensor not connected, driver pins misconfigured
- Action: Verify hardware connections (see Hardware Checklist below)

### Check 2: Sensor Calibration After initFOC()

**Expected**: `[MOTOR] Motor shaft_angle after initFOC: 0.000` (or very small value)

This indicates SimpleFOC has:
- Found the motor commutation phase
- Calibrated the AS5600 sensor zero position

**If shaft_angle is reasonable (close to 0):**
- ✓ Sensor is reading motor position
- ✓ FOC calibration completed
- Go to Check 3

**If shaft_angle is far from expected position or always 0:**
- ✗ Sensor not reading actual motor position OR motor never initialized
- Likely causes:
  - Motor shaft not physically connected to encoder
  - AS5600 magnet misaligned with sensor IC
  - I2C address conflict
- Action: See Hardware Checklist

### Check 3: Motor Response to Commands

**Expected during test**: Shaft angle increases monotonically as CC values change (0→16→32→48→64)

**If angle stays at 0.0 despite target changes:**
- ✗ Motor not responding to move() commands
- Likely causes:
  - Motor not powered (no +12V to motor supply)
  - Motor windings disconnected or shorted
  - PWM driver not outputting voltage (pins misconfigured)
  - SimpleFOC voltage_limit = 0 or insufficient
- **Check voltage_limit in output**: Should be "Angle voltage limit: 2.0"

**If motor_angle updates but doesn't track commands:**
- ✗ Sensor works, but motor control loop not closed
- Likely causes:
  - PID gains too low (P, I, D all too small)
  - Motor has high friction/load
  - Encoder resolution mismatch
  - Current/voltage limit too low

## Hardware Checklist

### Power Supply
- [ ] +12V power connected to motor driver (XT60 or screw terminal)
- [ ] RP2040 Pico power via USB (GND is common)
- [ ] Multimeter check: 12V present at driver VDD pins
- [ ] No smoke or burns on PCB (indicator of short)

### Motor & Encoder
- [ ] BLDC motor shaft mechanically connected to AS5600 magnet
- [ ] AS5600 magnet properly seated in encoder (within ~1mm of IC)
- [ ] Magnet polarity correct (N-pole facing IC side of BLDC)
- [ ] Motor can rotate freely by hand (no mechanical binding)

### I2C Bus (Sensor)
- [ ] SDA (GPIO pin 4?), SCL (GPIO pin 5?) connected to AS5600
- [ ] 10kΩ pull-up resistors on SDA/SCL (SimpleFOC wiring diagram)
- [ ] No shorts on I2C bus
- [ ] AS5600 I2C address is 0x36 (default)

### PWM Driver
- [ ] PWM pins (13, 12, 11) connected to DRV8313 or equiv gate drivers
- [ ] Enable pin (10) pulled high or connected appropriately
- [ ] Motor phase pins (A, B, C) soldered to BLDC windings
- [ ] No continuity between any two motor phases (shouldn't all be shorted)

### Firmware
- [ ] Correct environment selected: `[env:pico_1motor_endless]` (NOT `_dummy`)
- [ ] Build succeeded: "4.3% flash usage" ✓
- [ ] Serial output visible in test runner

## Next Steps

1. **Run test again** with diagnostic firmware (commit af1974a or later)
2. **Collect full serial output** from device during initialization
3. **Share with logs showing**:
   - Initialization diagnostics (`[MOTOR]` prefixed messages)
   - Motor stuck warnings
   - MIDI CC messages received
   - Angle readings (should be blank or 0 if sensor not working)

4. **If motor still stuck at 0.0**:
   - Check hardware connections physically (see item 1-3 in Hardware Checklist)
   - Test AS5600 sensor independently (SimpleFOC sensor example sketch)
   - Verify motor can rotate with direct PWM (bypass FOC control)

## Related Configuration

- **Motor profiles**: `src/config.h` - MOTOR_0 definition, voltage limits
- **PID tuning**: `include/pid_config.h` - MOTOR0_PID_P/I/D gains
- **Hardware mapping**: `src/motor_control.cpp` - Pin definitions for driver/sensor

---

## Motor Control Theory (For Reference)

When `set_motor_target(0, target_angle)` is called:
1. Target angle stored in `target_angle[0]`
2. Each loop iteration, `update_motor(0)` executes:
   - `motor->loopFOC()` - reads current angle from sensor, adjusts voltage
   - `current_angle[0] = motor->shaft_angle` - samples the actual position
   - `motor->move(target_angle[0])` - commands motor to reach target via PID

If `shaft_angle` stays at 0, the sensor loop is broken (check hardware) or motor never initialized (check logs).

---

**Last updated**: Feb 28, 2026  
**Related commits**: 9525cda (diagnostics), de76c17 (dummy mode), 3fae6a1 (rate strategy)  
**Environment**: pico_1motor_endless (single RP2040, one BLDC motor, AS5600 encoder)
