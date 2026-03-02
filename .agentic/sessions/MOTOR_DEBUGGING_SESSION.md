# Motor Control Debugging Session - 2026-02-28

## Status: First CI Success Achieved ✓, Motor Control Broken ❌

### Session Summary

**Date**: 2026-02-28  
**Branch**: `dev`  
**Last Commit**: `699d546` (Device testing guide)  
**Status**: Basic hardware tests passing 5/5, motor movement test failing

## Major Accomplishments

### 1. ✓ First Successful Hardware Test in CI
- **Commit**: `5203e6e` "fix: Make motor init test accept telemetry as proof"
- **CI Run**: [22509465558](https://github.com/arnew/FOC_joystick/actions/runs/22509465558)
- **Result**: **ALL 5 BASIC TESTS PASSED**

Tests that now pass:
```
✓ Device Exists
✓ Device Opens  
✓ Device Responds (A=0.00 T=0.00)
✓ Motor Initialization (telemetry detected)
✓ Commander Interface (M0? responded)
```

This was the **first time** after 40+ CI failures that tests passed consistently.

### 2. ✓ SimpleFOC Commander Integration Complete
- **Commits**: `be86de7`, `de21837`, `2ad76fb`
- **Status**: Fully functional for status queries (`M0?`)
- **Problem**: Target commands (`M0 T3.14`) not executing

Features implemented:
- Motor registration: `commander.motor(&motor0, "M0")`
- Access to all SimpleFOC motor commands (T, P, I, D, L, C, ?)
- Useful for SimpleFOC Studio integration
- Custom direct command `T<angle>` added for testing

### 3. ✓ DUMMY_MODE Removed
- **Commit**: `2ad76fb`
- **Status**: Replaced with real SimpleFOC Commander
- **Benefit**: Real motor control for testing

### 4. ✓ Telemetry Rate Increased 10x
- **Commit**: `fcf3534` 
- **Change**: `DEBUG_UPDATE_INTERVAL` from 1000ms → 100ms (1Hz → 10Hz)
- **Benefit**: Eliminates race conditions in test timing
- **Test improvement**: Now collects 10 samples, reports mean ± stddev

## Current Blocker: Motor Not Moving

### Symptoms
```
Command sent:  T3.14 (set target to 180°)
Response:      [CMD] Set target_angle[0] = 3.14 ✓
Motor angle:   A=0.00 (stays at 0° forever)
Motor target:  T=3.14 (correctly shows in telemetry)
Movement:      0.000 rad (motor frozen)
```

### What Works
- ✓ Firmware uploads and boots reliably
- ✓ Telemetry streams continuously (10 Hz)
- ✓ Commands received and echoed back
- ✓ `target_angle[0]` updates correctly
- ✓ Motor control loop running (FOC executing)
- ✓ Motor initialization completes (initFOC runs)

### What's Broken
- ✗ Motor doesn't respond to target changes
- ✗ `motor.move(target)` not moving motor
- ✗ No phase current output detected
- ✗ Motor angle always stays 0.00 rad

### Investigation Timeline

**Run 22509661774** (M0 T3.14 command):
```
[01:54:07] Sending: M0 T3.14
[01:54:09] Response: M0 T3.14 (echo - command received)
[01:54:09] Response: A=0.00 T=0.00 (telemetry unchanged!)
```
**Finding**: SimpleFOC Commander receiving command but target not updating

**Commit 80f5b15** (Bidirectional sync attempt):
Added sync logic in `update_motor()`:
```cpp
if (motor->target != target_angle[motor_id]) {
    target_angle[motor_id] = motor->target;
} else {
    motor->target = target_angle[motor_id];
}
motor->move();
```
**Result**: No improvement. Target stayed 0.00 in telemetry.

**Commit a8a0eb5** (Simplify target source):
Changed to single source of truth:
```cpp
motor->move(target_angle[motor_id]);  // Pass target directly
```
**Result**: No improvement. Motor still frozen.

**Commit 499e567 + fcf3534** (Direct command + 10Hz telemetry):
- Added custom `T<angle>` command that calls `set_motor_target()` directly
- Bypasses SimpleFOC Commander entirely
- Increased telemetry to 10Hz
- Added statistical sampling (10 samples per measurement)

**Latest logs** (Run 22516226985):
```
[08:34:55] Command: T3.14
[08:34:55] Response: [CMD] Set target_angle[0] = 3.14 ✓
[08:34:55] Response: [CMD] Verify: target_angle[0] = 3.14 ✓
[08:34:55] Telemetry: T=3.14 ✓
[08:35:00] [5] A=0.000 (error=3.140)  ← Still at 0°
[08:35:20] Final: A=0.000 rad ← Never moved
```

**Conclusion**: Target is correctly set in state, but motor doesn't move.

## Root Cause Analysis

### Theory 1: Motor Control Loop Blocked ❌
**Status**: Unlikely - telemetry every 100ms proves loop running
- If loop blocked, no telemetry output
- We see consistent A=0.00 every 100ms
- **Verdict**: Loop is running

### Theory 2: SimpleFOC FOC Not Executing ⚠️
**Status**: Possible but unlikely
- `motor->loopFOC()` is called
- `motor->move(target)` is called
- No errors reported
- **Next check needed**: Verify `loopFOC()` and `move()` actually execute

### Theory 3: Motor Hardware Issue ❌
**Status**: Unlikely - MIDI control works per user notes
- User reported manual MIDI control moves motor
- So hardware, wiring, driver all working
- **Only in CI tests**: Motor stuck
- **Verdict**: Firmware/software issue, not hardware

### Theory 4: Motor Control State Not Initialized ⚠️
**Status**: Possible
- `init_motor()` completes and reports success
- `initFOC()` completes without errors
- But perhaps `motor0` global not properly initialized
- Or sensor not reading correctly
- **Next check needed**: Verify sensor values, motor state

### Theory 5: Phase Current Not Applied ⚠️
**Status**: Most likely
- Motor receives target but no current flows
- Could be: driver not enabled, voltage limit = 0, PWM not initialized
- Current observed: Motor doesn't move despite target set
- **Next check needed**: Instrument driver current output, PWM pins

## Commits This Session

| Commit | Message | Status |
|--------|---------|--------|
| `5203e6e` | fix: Make motor init test accept telemetry as proof | ✓ Working |
| `aefd650` | test: Add motor movement verification test | Test framework added |
| `f94918e` | fix: Correct SimpleFOC Commander command format | Parser fixed |
| `80f5b15` | fix: Sync motor.target bidirectionally | Reverted as ineffective |
| `a8a0eb5` | fix: keep target_angle as single control source | Single source approach |
| `66d0280` | debug: Add direct target command | Bypassed Commander |
| `499e567` | fix: Parse Commander T command payload | Parser fixed |
| `fcf3534` | fix: Increase telemetry to 10Hz and add statistical sampling | ✓ Deployed |
| `b70ebb9` | fix: Add missing statistics import | Test dependency |
| `699d546` | docs: Add device testing guide and detection scripts | ✓ Infrastructure |

## Files Modified

### Firmware Changes
- [src/motor_control.cpp](../src/motor_control.cpp) - Target sync experiments
- [src/commander_integration.cpp](../src/commander_integration.cpp) - Direct command added
- [src/main.cpp](../src/main.cpp) - Telemetry rate increased 100ms
- [src/config.h](../src/config.h) - No changes needed

### Test Updates
- [test/test_motor_movement.py](../test/test_motor_movement.py) - Now collects 10 samples with statistics
- [test/simple_hardware_test.py](../test/simple_hardware_test.py) - Unchanged

### Infrastructure
- [.agentic/DEVICE_TESTING.md](.agentic/DEVICE_TESTING.md) - Testing guide
- [.agentic/local_device_detect.sh](.agentic/local_device_detect.sh) - Device detection
- [.agentic/ci_device_detect.sh](.agentic/ci_device_detect.sh) - CI validation

## What Next Agent Should Do

### Immediate Actions (Priority 1)

1. **Enable motor debugging:**
   ```cpp
   // In update_motor(), add after motor->move():
   static unsigned long last_debug = 0;
   if (millis() - last_debug >= 1000) {
       Serial.print("[MOTOR] Current angle: ");
       Serial.print(motor0.shaft_angle);
       Serial.print(" | Target: ");
       Serial.print(target_angle[0]);
       Serial.print(" | Electrical angle: ");
       Serial.print(motor0.electrical_angle);
       Serial.print(" | Voltage: ");
       Serial.println(motor0.voltage_q);
       last_debug = millis();
   }
   ```

2. **Check driver initialization:**
   - Verify `driver0.init()` actually initializes PWM
   - Check: GPIO pins 13, 12, 11 configured correctly
   - Verify voltage_power_supply = 12.0V
   - Check PWM frequency = 30000 Hz

3. **Instrument sensor:**
   ```cpp
   // In init_motor():
   Serial.print("[MOTOR] Sensor initial angle: ");
   Serial.println(sensor0.getAngle());
   
   // In update_motor():
   static unsigned long last_sensor_check = 0;
   if (millis() - last_sensor_check >= 2000) {
       Serial.print("[SENSOR] AS5600 angle: ");
       Serial.println(sensor0.getAngle());
       last_sensor_check = millis();
   }
   ```

4. **Test motor.move() directly:**
   ```cpp
   // Add test command T0 to query motor state
   void cmd_test_motor(char* cmd) {
       Serial.print("[TEST] motor0.target = ");
       Serial.println(motor0.target);
       Serial.print("[TEST] motor0.shaft_angle = ");
       Serial.println(motor0.shaft_angle);
       Serial.print("[TEST] motor0.electrical_angle = ");
       Serial.println(motor0.electrical_angle);
   }
   ```

### Investigation Path

1. **Build with debug logging enabled (above)**
2. **Run CI test** and collect logs
3. **Analyze telemetry** for voltage_q, electrical_angle patterns
4. **If voltage_q = 0**: Driver not applying current
5. **If voltage_q > 0**: Current applied but motor not responding
6. **If electrical_angle stuck**: Sensor issue or commutation problem

### Testing Approach

- Use **CI tests** (runs on hardware)
- Increase logging in steps, analyze output
- Don't try local testing yet (no device attached here)
- Check CI logs via: `gh api /repos/arnew/FOC_joystick/actions/jobs/<id>/logs`

### Tools Ready

- ✓ Direct command bypass for testing
- ✓ 10Hz telemetry (high resolution)
- ✓ Statistical sampling in tests
- ✓ CI infrastructure solid
- ✓ Device detection scripts in place

## References

- **SimpleFOC Docs**: https://docs.simplefoc.com/
- **Motor initialization**: See `init_motor()` in [src/motor_control.cpp](../src/motor_control.cpp)
- **Test framework**: [test/test_motor_movement.py](../test/test_motor_movement.py) - can be extended
- **GitHub Actions logs**: Accessible via `gh run view --job <id> --log`

## Session Statistics

- **Duration**: ~4 hours
- **Commits**: 10
- **CI test runs**: ~15
- **Basic tests**: 5/5 passing ✓
- **Motor movement tests**: 0/15 passing ❌
- **Knowledge base added**: 3 files (detection scripts + guide)

---

**Next Agent**: Read [DEVICE_TESTING.md](.agentic/DEVICE_TESTING.md) for how to run local tests if DUT is available, or use CI testing. Start with the debug logging approach above and analyze the voltage/angle telemetry.
