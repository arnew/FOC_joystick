# Aircraft Profiles

This firmware includes pre-configured MIDI control mappings for three aircraft types: Airbus A320, Cessna 172, and Glider.

## Overview

The firmware supports three aircraft profiles that define which MIDI Control Change (CC) numbers control the motor. Since the current hardware has only one motor, only one axis is active at a time. The profile determines which MIDI CCs the firmware recognizes.

## Switching Profiles

### Compile-Time Selection

Edit [src/config.h](src/config.h) and change the `ACTIVE_CONFIG` and `NUM_ACTIVE_AXES` macros:

```cpp
// At the bottom of config.h, around line 245-246
#define ACTIVE_CONFIG A320_CONFIG          // Change this line
#define NUM_ACTIVE_AXES NUM_A320_AXES      // Change this line to match
```

**Options:**
```cpp
// Airbus A320
#define ACTIVE_CONFIG A320_CONFIG
#define NUM_ACTIVE_AXES NUM_A320_AXES

// Cessna 172
#define ACTIVE_CONFIG CESSNA_CONFIG
#define NUM_ACTIVE_AXES NUM_CESSNA_AXES

// Glider
#define ACTIVE_CONFIG GLIDER_CONFIG
#define NUM_ACTIVE_AXES NUM_GLIDER_AXES
```

Then rebuild and upload:
```bash
platformio run -e pico_1motor_endless
# (Hold BOOTSEL, then it uploads)
```

### Runtime Selection (NEW!)

Switch aircraft profiles **without recompiling** via serial commands:

```bash
# Show available profiles
> P

# Switch to A320
> P0

# Switch to Cessna
> P1

# Switch to Glider
> P2

# Check current profile
> P
```

Use any serial terminal (Arduino IDE, minicom, `picocom`, etc.) connected to `/dev/ttyACM0`.

## Aircraft Configurations

### Airbus A320

**Available Controls:**
| Axis | MIDI CC | Range | Type | Hardware |
|------|---------|-------|------|----------|
| Throttle | #7 | 0-100% | Limited (0-180°) | pico_1motor_limited |
| Flaps | #11 | 0,1,2,3,Full | Limited (0-180°) | pico_1motor_limited |
| Trim | #64 | -100% to +100% | Endless (360°) | pico_1motor_endless |
| Spoilers | #2 | 0-100% | Limited (0-180°) | pico_1motor_limited |
| Landing Gear | #32 | 0-100% | Limited (0-180°) | pico_1motor_limited |

**Usage:**
To control Airbus A320 throttle, send MIDI CC#7:
```
CC#7 value 0   → Motor at 0° (minimum throttle)
CC#7 value 64  → Motor at 90° (mid throttle)
CC#7 value 127 → Motor at 180° (maximum throttle)
```

### Cessna 172

**Available Controls:**
| Axis | MIDI CC | Range | Type | Hardware |
|------|---------|-------|------|----------|
| Throttle | #7 | 0-100% | Limited (0-180°) | pico_1motor_limited |
| Flaps | #5 | 0-5 positions | Limited (0-180°) | pico_1motor_limited |
| Trim | #64 | -100% to +100% | Endless (360°) | pico_1motor_endless |
| Landing Gear | #35 | 0-100% | Limited (0-180°) | pico_1motor_limited |

**Note:** Flaps on Cessna 172 have 5 discrete positions. Map CC#5 values:
- 0-25: Position 0 (retracted)
- 26-51: Position 1 (10°)
- 52-76: Position 2 (20°)
- 77-102: Position 3 (30°)
- 103-127: Position 4 (full, 40°)

### Glider

**Available Controls:**
| Axis | MIDI CC | Range | Type | Hardware |
|------|---------|-------|------|----------|
| Spoilers/Airbrakes | #2 | 0-100% | Limited (0-180°) | pico_1motor_limited |
| Trim | #64 | -100% to +100% | Endless (360°) | pico_1motor_endless |

## Hardware Configurations

The firmware can also be built for different motor types:

### pico_1motor_endless
Single motor with endless rotation (360°), suitable for trim axes.

Build:
```bash
platformio run -e pico_1motor_endless
```

### pico_1motor_limited  
Single motor with limited range (0-180°), suitable for throttle/flaps/spoiler axes.

Build:
```bash
platformio run -e pico_1motor_limited
```

## MIDI Protocol

The firmware uses standard MIDI Control Change (CC) protocol. Any MIDI tool that can send CC messages will work:

**Protocol:**
- Type: Control Change (0xB0)
- CC Number: 0-127 (depends on configured aircraft profile)
- Value: 0-127 (0 = minimum, 127 = maximum)

**Examples using `mido` Python library:**
```python
import mido

# Open MIDI output to the device
output = mido.open_output("pico_1motor_endless")  # or device name

# Send CC#64 (Trim) at 50% position
msg = mido.Message('control_change', channel=0, control=64, value=64)
output.send(msg)

# Send CC#7 (Throttle) at full
msg = mido.Message('control_change', channel=0, control=7, value=127)
output.send(msg)
```

See [test/debug_midi.py](test/debug_midi.py) for an interactive test tool.

## Future Enhancements

### MSFS Integration (Future)

A companion script will be provided that:
1. Reads flight simulator data (throttle, flaps, trim, etc.)
2. Converts to appropriate MIDI CC commands
3. Sends to the Pico via USB MIDI

### Multi-Motor Configuration (Future)

Support for dual-motor setups (one motor per axis) with simultaneous control of two aircraft controls.

This enables true "follow-along" motion where the motor follows the simulator's control state.

## Troubleshooting

**Motor not responding to MIDI?**
1. Check that the correct profile is compiled in
2. Verify the MIDI CC number matches the profile
3. Use [test/debug_midi.py](test/debug_midi.py) to test
4. Check the debug serial output: `platformio device monitor`

**MIDI CC values don't map to expected angles?**
- CC#0 → 0° minimum
- CC#127 → 180° maximum (for limited motors) or 360° (for endless)
- Linear  interpolation is used between min and max angles

See [src/config.h](src/config.h) for the implementation of `cc_to_angle()`.

