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

Before pushing: `python3 test/test_suite_automated.py` must pass all tests.

---

## Quick Workflow

1. **Build**: `platformio run -e pico_1motor_endless`
2. **Upload**: `platformio run -e pico_1motor_endless --target upload`
3. **Test**: `python3 test/test_suite_automated.py`
4. **Debug**: `python3 test/debug_joystick.py` (monitor) + `python3 test/debug_midi.py` (control)

---

## References

- SimpleFOC: https://docs.simplefoc.com/
- TinyUSB: https://github.com/hathach/tinyusb
- RP2040: https://github.com/earlephilhower/arduino-pico

---

## Repository Structure

```
src/
  ├─ main.cpp         # Motor control, MIDI handler, USB HID
  ├─ config.h         # Axis profiles, motor configurations

test/
  ├─ test_suite_automated.py  # Automated tests
  ├─ debug_joystick.py        # Real-time monitor
  ├─ debug_midi.py            # Interactive MIDI sender
  └─ README.md                # Test documentation

platformio.ini         # Build configs (endless, limited, 2motor)
```

---

## Key Facts

- **Hardware**: RP2040 + SimpleFOC + AS5600 encoder
- **Protocol**: MIDI CC @ 31250 baud (USB dual CDC)
- **Testing**: Automated suite verifies system ID, motor response, joystick output
