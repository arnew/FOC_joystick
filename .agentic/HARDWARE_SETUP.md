# Hardware Setup Documentation

## Critical Distinction: Two Test Environments

### Environment 1: Windows VSCode Machine (Current Session)
**Hardware**: Bare Raspberry Pi Pico
- **Purpose**: Firmware compilation, USB HID/MIDI enumeration testing
- **No motor connected** - motor control code will initialize but not move anything
- **Available tests**:
  - ✅ Firmware upload verification
  - ✅ USB HID joystick enumeration
  - ✅ USB MIDI device enumeration
  - ✅ CDC serial communication
  - ❌ Motor angle tracking (no motor hardware)
  - ❌ FOC control loop (no motor hardware)

### Environment 2: CI/CD Runner (Motor Test Environment)
**Hardware**: Raspberry Pi Pico + Motor + AS5600 Encoder
- **Purpose**: Full hardware-in-the-loop testing
- **Motor setup**: Complete SimpleFOC control system
- **Configuration**: `pico_1motor_endless` environment
- **Available tests**:
  - ✅ All Windows machine tests PLUS
  - ✅ Motor angle tracking
  - ✅ SimpleFOC PID control
  - ✅ AS5600 I2C encoder communication
  - ✅ MIDI CC → motor position mapping

## Upload Workflow
Both environments use the same firmware binary:
1. **Compile** on Windows machine (PlatformIO build)
2. **Upload** to target device (manual BOOTSEL or automatic via CI/CD)
3. **Test** appropriate subset (HID/MIDI on Windows, full stack on CI/CD)

## Current Session Status (2026-02-27)
- ✅ Firmware compiled successfully (121KB / 2MB flash)
- ✅ Uploaded to **Windows bare Pico** via manual BOOTSEL
- ⏳ Next: CI/CD motor hardware testing (requires GitHub Actions trigger or SSH access)

## Important Notes
- **Windows machine**: Use for compilation and USB descriptor verification only
- **CI/CD runner**: Required for any motor control validation
- **Testing strategy**: Iterative - verify USB on Windows, then motor on CI/CD
- **Upload method**: Manual BOOTSEL button required on Windows, may be automatic on CI/CD

## Configuration Files
All hardware configs support both environments:
- `HW_BARE_PICO`: USB-only testing (no motor init)
- `HW_1MOTOR_ENDLESS`: Single motor, continuous rotation (CI/CD)
- `HW_1MOTOR_LIMITED`: Single motor, 0-180° range (CI/CD)
- `HW_2MOTOR_LIMITED`: Dual motor, flight sim axes (future CI/CD)

Currently building: `pico_1motor_endless` (works on both, motor features idle on bare Pico)
