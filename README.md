
This is a usb HID joystick that accepts midi commands to configure a SimpleFOC driven motor controlled AXIS (USB Composite Device).

Preconfigured use cases are:
- Cessna Throttle, Flaps, Gear, Trim
- Airbus Throttle, Flaps, Spoilers, Gear, Trim
- Glider Spoiler, Trim

The joystick needs to be used with Microsoft Flight Simulator, sending the Axis data as USB joystick, and sending the configured case as identification of the USB device.
A companion script is provided that interfaces with the MSFS Scripting  and provides the current position interface from the User Interface of the respective control.

## Implementation Status & Planning

This project is currently in **active development** with a structured 6-phase implementation plan.

**See [PLANNING.md](./PLANNING.md)** for:
- Complete architecture specification
- Phase-by-phase implementation steps with code examples
- Hardware configuration and control mappings
- Testing strategy and design decisions

**See [test/README.md](./test/README.md)** for:
- MIDI testing with Python scripts
- USB HID joystick monitoring
- Configuration-specific test workflows

**Current Status**:
- ✅ Motor control & SimpleFOC integration working
- ✅ AS5600 encoder reading functional
- ✅ Configuration system with 3 hardware variants (Phase 1)
- ✅ Motor abstraction for 1-2 motors (Phase 2)
- ✅ MIDI input handler (Phase 3)
- ✅ Axis output scaling (Phase 4)
- 🚧 USB HID implementation (Phase 5)
- ✅ Main loop integration (Phase 6)

**Hardware Configurations**:
Three buildable configurations support different hardware setups:
- **pico_1motor_endless** — Single endless motor (current hardware, trim-like)
- **pico_1motor_limited** — Single 0-180° motor (throttle/flaps-like)
- **pico_2motor_limited** — Dual motors (throttle + trim, future-proof)

Build with: `platformio run -e pico_1motor_endless`

