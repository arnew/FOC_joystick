# Project Purpose

## What This Is

**USB HID Joystick Controller for Flight Simulator**
- Dual motorized axes with force feedback (SimpleFOC)
- MIDI input for flight sim controls (throttle, flaps, spoilers, trim, gear)
- USB HID output as joystick (TinyUSB)
- Real-time PID tuning via SimpleFOC Commander

## Hardware

### Development Setup (User's PC)
- RP2040 Pico (earlephilhower bootloader)
- USB connection only
- **No motors attached** - code compiles and USB tests work
- Manual BOOTSEL press required for uploads

### Production Setup (CI/CD Runner)
- RP2040 Pico with endless motor (AS5600 I2C encoder)
- 3-phase BLDC motor driver
- USB connection for serial + HID + MIDI
- Manual BOOTSEL trigger available for uploads

## Technology Stack

- **Platform**: RP2040 (PlatformIO, earlephilhower Arduino core)
- **Motor Control**: SimpleFOC 2.4.0
- **USB**: Adafruit TinyUSB 3.7.2 (HID + MIDI + CDC)
- **Sensor**: AS5600 magnetic encoder (I2C)
- **Build**: PlatformIO with 3 environments (1motor_endless, 1motor_limited, 2motor_limited)
- **CI/CD**: GitHub Actions (code-quality, headless-test, hardware-test)
- **Testing**: pytest (headless + hardware markers), simulator

## Goals

### Primary
1. ✅ Reliable motor control with tunable PID
2. ✅ USB HID joystick output
3. ⏳ MIDI input for flight controls
4. ⏳ Dual-axis support (throttle + trim)

### Secondary
1. ✅ Automated headless testing
2. ⏳ Automated hardware testing (requires manual BOOTSEL trigger)
3. ⏳ SimpleFOC Studio integration for live tuning
4. ⚠️ Automated bootloader reentry (nice-to-have, not critical)

## Non-Goals

- Complex USB bootloader automation (manual BOOTSEL is acceptable)
- Real-time OS (bare metal Arduino loop is sufficient)
- Multi-device support (single Pico target)
- Wireless connectivity (USB only)

## Success Criteria

**Minimum Viable Product:**
- [x] Compiles and uploads to RP2040
- [x] Motor spins and tracks target angle
- [x] USB HID reports joystick position
- [ ] MIDI CC messages control motor positions
- [ ] PID tuning persists across reboots

**Production Ready:**
- [ ] Dual motors with independent control
- [ ] Flight sim integration tested
- [ ] Hardware CI tests passing
- [ ] Documentation complete
