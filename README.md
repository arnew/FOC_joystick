
**Purpose**
This is a usb HID joystick that accepts MIDI commands to control SimpleFOC driven motors (USB Composite Device).

**Preconfigured aircraft profiles:**
- **Cessna 172** — Throttle, Flaps, Landing Gear, Trim (all MIDI-configurable)
- **Airbus A320** — Throttle, Flaps, Spoilers, Landing Gear, Trim (all MIDI-configurable)
- **Glider** — Spoilers/Airbrakes, Trim (all MIDI-configurable)

See [AIRCRAFT_PROFILES.md](AIRCRAFT_PROFILES.md) for detailed MIDI CC mappings.

**Profile Selection**

Profiles can be selected:
1. **At compile time** - Edit [src/config.h](src/config.h) before building
2. **At runtime** - Send profile command via serial: `P0` (A320), `P1` (Cessna), `P2` (Glider), or `P` to show current

Example using serial terminal:
```bash
# Show available profiles and current selection
> P

# Switch to Cessna
> P1
```

The joystick sends position data as USB HID output to Microsoft Flight Simulator. With the single-motor hardware, one axis is controlled at a time (typically trim or one aircraft control). Select profiles to match your aircraft type.

**Operation Modes**
Profiles are selected during compile time or at runtime via serial command. Joystick operates with profile-specific MIDI CC mappings without requiring companion apps.

**Hardware Configurations**:
Two buildable configurations support different hardware setups:
- **pico_1motor_endless** — Single endless motor (current hardware, trim-like)
- **pico_1motor_limited** — Single 0-180° motor (throttle/flaps-like, future)

Build with: `platformio run -e pico_1motor_endless`

**Quality Goals**
Position Hold Noise: At position the motor should not vibrate visibly.
Movement: Travelling to a position the motor should not overshoot violently.
