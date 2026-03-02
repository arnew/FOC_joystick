# Architecture

System design, build procedures, and code style guidelines.

---

## Documents

- [PLANNING.md](PLANNING.md) - 6-phase implementation architecture
- [QUICKSTART.md](QUICKSTART.md) - Build, upload, test instructions
- [REFACTORING_PLAN.md](REFACTORING_PLAN.md) - Code cleanup & modularization plan
- [IO_RATE_STRATEGY.md](IO_RATE_STRATEGY.md) - MIDI/HID/Debug scheduling and bandwidth budget

---

## Code Style Guidelines

### Motor Control
- **SimpleFOC API**: FOC loop ~1 kHz
- **Indexing**: Motors 0-1 for dual setup; axes correspond to motors
- **Config**: Static arrays in `src/config.h` (no runtime changes)
- **MIDI**: 3-byte stateful parser, CC# 0-127
- **Timing**: FOC best-effort high-rate, USB HID 50Hz, debug 1Hz, bounded MIDI budget

### Common Edits

**Change MIDI CC mapping**:
```cpp
// src/config.h
{.motor_id = 0, .midi_cc = 7, .label = "Throttle", ...}
```

**Adjust motor range**:
```cpp
{.min_angle = 0.0f, .max_angle = 3.14f, .is_endless = false, ...}
```

### Hardware Configuration

**Motor 0 Wiring** (GPIO pins):
- PWM: 13, 12, 11
- Enable: 10
- Encoder: I2C (AS5600)

**Motor 1**: TBD (placeholder)

---

## Testing Requirements

Before pushing: `python3 test/quality_goals_test_suite.py` must pass.

---

## Quick Workflow

1. **Build**: `pio run`
2. **Upload**: `pio run -t upload`
3. **Test**: `python3 test/quality_goals_test_suite.py`
4. **Debug**: `python3 test/tools/debug_joystick.py` (monitor) + `python3 test/tools/debug_midi.py` (control)

---

## References

- SimpleFOC: https://docs.simplefoc.com/
- TinyUSB: https://github.com/hathach/tinyusb
- RP2040: https://github.com/earlephilhower/arduino-pico

---

## Repository Structure

```
src/
  ├─ config.h                  # 11 profiles, detent maps
  ├─ main.cpp                  # setup(), loop(), rate scheduling
  ├─ motor_control.cpp/h       # SimpleFOC init, FOC loop, accessors
  ├─ haptic_layer.cpp/h        # Detent engine (v2)
  ├─ profile_manager.cpp/h     # EEPROM persistence, profile state
  ├─ input/
  │   ├─ commander_integration # Serial Commander (M/T/A/W)
  │   └─ midi_handler          # MIDI CC → position, CC#0 → profile
  └─ output/
      ├─ usb_hid               # TinyUSB HID joystick (16-bit axes)
      └─ telemetry             # @T structured output, ring buffer

test/
  ├─ quality_goals_test_suite.py  # 8-test quality suite
  ├─ test_cessna_trim.py          # Linearity & endstop test
  ├─ tools/                       # Debug & diagnostic scripts
  └─ unit/                        # Headless pytest tests

platformio.ini         # Single env: pico_1motor_endless
```

---

## Key Facts

- **Hardware**: RP2040 + SimpleFOC + AS5600 encoder + BLDC 7pp
- **Protocol**: Native USB MIDI (TinyUSB composite)
- **Testing**: Quality goals suite (8 tests), Cessna trim linearity test
