# Hardware Test Plan - Task 2

**Date**: 2026-02-27  
**Session**: Hardware integration testing on CI runner  
**Status**: 📋 Ready to execute on CI runner

---

## Summary

Dev branch now contains full HID+MIDI+SimpleFOC integration. Hardware testing needed to verify:
1. Firmware builds and uploads cleanly
2. Motor angle tracking functional
3. HID joystick enumerates
4. Serial debug output working

---

## Test Checklist

### Pre-Test (Setup)
- [ ] Motor connected to CI runner
- [ ] USB cable connected (Micro-B to host)
- [ ] Power supply verified (5V 2A minimum)
- [ ] Serial monitor ready (115200 baud)

### Build Test
```bash
cd /home/runner/work/FOC_joystick/FOC_joystick
source .venv/bin/activate
platformio run -e pico_1motor_endless
```
**Expected**: Compilation succeeds (~14-20s)
- ✅ No errors
- ✅ ~64KB flash, ~10KB RAM
- ✅ Bootloader reentry enabled automatically

### Upload Test
```bash
platformio run --target upload -e pico_1motor_endless
```
**Expected**: Upload via automatic 1200bps reset (NO manual BOOTSEL)
- ✅ Device detected by picotool
- ✅ Upload completes (~15-25s)
- ✅ No BOOTSEL button needed
- ✅ Device automatically reboots and starts firmware

### Motor Test
**Expected Serial Output** (115200 baud):
```
=== USB HID Joystick Controller ===
USB: CDC /dev/ttyACM0 (115200)
     Native MIDI (if enabled)
     HID Joystick (8btn + 2axis)
Initializing Motor 0...
Motor 0 ready
=== Ready ===
A=0.00 T=0.00
~0.0000 0.0000  0.0000  0.0000
```

**Test Procedure**:
1. Open serial monitor
2. Verify output stream (angle A, target T, FOC debug values ~)
3. Check angle updates: motor rotation should update A value
4. If no motion: verify encoder I2C bus, check address 0x36

### HID Joystick Test
```bash
# Linux/Mac
ls /dev/input/js*
cat /dev/input/js0  # Should show axis values changing

# Or use pygame test:
python3 test/test_hid_exercise.py
```
**Expected**:
- ✅ Device enumerates as `/dev/input/js0`
- ✅ Joystick recognized by test script
- ✅ No permission errors (should not need sudo)

### MIDI Input Test (Skeleton Present)
```bash
# MIDI dispatcher not yet implemented (Task 4)
# Placeholder code present in src/main.cpp
# Motor target angle can be set via Serial1 (31250 baud) - TODO
```

---

## Expected Results

| Test | Expected | Status |
|------|----------|--------|
| Code compiles | ✅ Yes | **Ready** |
| Upload succeeds (automated reset) | ✅ Yes | **Ready** (bootloader verified working) |
| Motor spins | ✅ Yes | **Pending hardware test** |
| Serial output (A/T/~) | ✅ Yes | **Pending hardware test** |
| HID joystick enumeration | ✅ Yes | **Pending hardware test** |
| MIDI parsing | ⏳ WIP | **Task 4** |

---

## Troubleshooting

### Build Fails
- **Symptom**: Compilation errors, missing headers
- **Check**: `include/my_tusb_config.h` present
- **Check**: `include/pid_config.h` present
- **Check**: SimpleFOC library installed in `lib/`
- **Action**: Run `platformio lib install` to fetch dependencies

### Upload Fails (Device Not Found)
- **Symptom**: "Device not found" or timeout
- **Check**: USB cable working (try another cable)
- **Check**: Pico detected via `lsusb` or `Get-PnPDevice`
- **Workaround**: Manual BOOTSEL (hold button during upload)
  ```bash
  # Hold BOOTSEL, then run:
  platformio run --target upload -e pico_1motor_endless
  # Release BOOTSEL when upload starts
  ```
- **Fallback**: `picotool` manual upload
  ```bash
  picotool load -x .pio/build/pico_1motor_endless/firmware.uf2
  ```

### Motor Doesn't Move
- **Symptom**: Serial shows angle but motor not spinning
- **Check**: Motor phase wires connected (A, B, C to pins 13, 12, 11)
- **Check**: Enable wire connected (pin 10)
- **Check**: Encoder I2C bus (SDA=7, SCL=6)
- **Check**: SimpleFOC init completes (look for "Motor 0 ready")
- **Action**: Verify encoder address with I2C scanner
  ```bash
  python3 -c "import board, busio; i2c = busio.I2C(board.SCL, board.SDA); print(hex(i2c.scan()))"
  ```

### Serial Output Garbled
- **Symptom**: Characters showing as gibberish
- **Check**: Baud rate (must be 115200)
- **Check**: Port selection (correct /dev/ttyACM0 or COM port)
- **Action**: Restart serial monitor

### HID Device Not Detected
- **Symptom**: No `/dev/input/js0`, pygame can't find joystick
- **Check**: Device shows up in `lsusb` as "Adafruit" USBD HID
- **Check**: Test script has permissions (`sudo` if needed, but shouldn't)
- **Note**: If HID enumeration fails, bootloader/USB issue (not TinyUSB config issue)

---

## Success Criteria (Task 2 Complete)

✅ All of the following must pass:
1. Firmware builds without errors
2. Firmware uploads via automatic 1200bps reset (no manual BOOTSEL)
3. Serial output shows angle tracking (`A=angle` values)
4. Motor physically spins (observable rotation)
5. HID joystick enumerates as `/dev/input/js0` or pygame detects it

---

## Next Steps (After Task 2)

### If Task 2 ✅ Succeeds:
→ Proceed to **Task 4: MIDI Integration**
- Implement CC dispatcher
- Enable native USB MIDI
- Test CC → motor angle mapping

### If Task 2 ❌ Fails:
→ Diagnose issue
- Check motormotor wiring and encoder connectivity
- Verify SimpleFOC configuration
- Debug bootloader reentry (if upload fails)
- Check USB enumeration (if HID fails)

---

## Notes for CI Runner

**Runner reliability**: Expected to be unreliable initially, improves with commits
- Expect 1-2 flaky runs before stabilizing
- Don't abandon after first failure - iterate and debug
- Each commit will improve reliability as motor wiring/calibration settles

**Parallel testing**: Can run tests while working on Task 4 (MIDI integration)
- Task 2 hardware testing can happen in background
- Task 4 MIDI implementation is code-only (local work)
- Merge Task 4 and run combined test after hardware confirms basic functionality

---

**Document Version**: v1.0  
**Status**: Ready for CI runner execution  
**Owner**: GitHub Copilot (automation) + Human (hardware observation)
