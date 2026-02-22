# Copilot Coding Guidelines

Context: USB HID joystick controller for Flight Simulator. See [AGENTS.md](../AGENTS.md) for overview and [.agentic/PLANNING.md](../.agentic/PLANNING.md) for architecture.

## Code Style

1. **Motor Control**: SimpleFOC API, FOC loop ~1 kHz
2. **Indexing**: Motors 0-1 for dual setup; axes correspond to motors
3. **Config**: Static arrays in `src/config.h` (no runtime changes)
4. **MIDI**: 3-byte stateful parser, CC# 0-127
5. **Timing**: FOC ~1kHz, USB HID ~100Hz, debug ~1Hz (interval-based, no blocking)
6. **Comments**: Motor limits (endless vs limited), pin mappings, MIDI CC meanings

## Common Edits

**Change MIDI CC mapping**:
```cpp
// src/config.h
{.motor_id = 0, .midi_cc = 7, .label = "Throttle", ...}
```

**Adjust motor range**:
```cpp
{.min_angle = 0.0f, .max_angle = 3.14f, .is_endless = false, ...}
```

**Motor wiring** (GPIO pins):
- Motor 0: PWM 13,12,11 + Enable 10 + I2C encoder
- Motor 1: TBD (placeholder)

## Testing

Before pushing: `python3 test/test_suite_automated.py` must pass all 5 tests.

## References

- SimpleFOC: https://docs.simplefoc.com/
- TinyUSB: https://github.com/hathach/tinyusb
- RP2040: https://github.com/earlephilhower/arduino-pico
