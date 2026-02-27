
**Purpose**
This is a usb HID joystick that accepts MIDI commands to control SimpleFOC driven motors (USB Composite Device).

**Preconfigured aircraft profiles:**
- **Airbus A320** — Throttle, Flaps, Spoilers, Landing Gear, Trim (all MIDI-configurable)
- **Cessna 172** — Throttle, Flaps, Landing Gear, Trim (all MIDI-configurable)
- **Glider** — Spoilers/Airbrakes, Trim (all MIDI-configurable)

See [AIRCRAFT_PROFILES.md](AIRCRAFT_PROFILES.md) for detailed MIDI CC mappings and profile switching instructions.

The joystick sends position data as USB HID output to Microsoft Flight Simulator. With the single-motor hardware, one axis is controlled at a time (typically trim or one aircraft control). Select profiles by editing [src/config.h](src/config.h) before building.

**Hardware Configurations**:
Three buildable configurations support different hardware setups:
- **pico_1motor_endless** — Single endless motor (current hardware, trim-like)
- **pico_1motor_limited** — Single 0-180° motor (throttle/flaps-like)

Build with: `platformio run -e pico_1motor_endless`

