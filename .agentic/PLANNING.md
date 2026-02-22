# Implementation Plan: Dual-Motor USB HID Joystick Controller with MIDI Profiles

## Overview

This document outlines the complete implementation strategy for a USB HID joystick controller with dual motorized axes, MIDI-driven profile switching, and preconfigured support for Airbus A320 flight controls.

**Architecture Pattern**: Configuration → Motor Abstraction → USB HID Output

---

## Current Status (2026-02-22)

- Build: Successful for `pico_1motor_endless` and `pico_twocdc_test` environments.
- Dual USB CDC: Enabled and working (`-DCFG_TUD_CDC=2`, `usb_cdc_midi` instance) — host shows ACM0 (debug) and ACM1 (MIDI).
- MIDI input: 3-byte MIDI CC parsing implemented; `usb_cdc_midi` read integrated into `loop()`.
- Motor control: `motor0` FOC loop stable; angle sensing via AS5600 validated.
- Test suite: `test/test_suite_automated.py` implemented and passes on connected hardware (5/5 tests when device running firmware).

## Progress Summary

- Completed:
  - Phase 1: Configuration system
  - Phase 2: Motor controller abstraction (Motor0 fully working)
  - Phase 3: MIDI input handler (dual-CDC + 3-byte parser)
  - Phase 4: Axis output scaling (0-1023 mapping)
  - Test harness and debug tools

- In progress / TODO:
  - Phase 5: USB HID joystick: descriptor exists as a stub; implementation of actual HID report send is remaining and must be validated on host (MSFS).
  - Motor 1: wiring and configuration need finalization and verification on hardware (pico_2motor_limited env).
  - Remove legacy text-demultiplexing code paths and cleanup unused helpers.
  - Prepare release branch and update CHANGELOG after HID verification.

## Requirements Specification

### Hardware Configuration
- **Microcontroller**: Raspberry Pi Pico (RP2040)
- **Motors**: Dual BLDC motors with SimpleFOC FOC control
- **Encoder**: AS5600 magnetic position sensor (I2C)
- **Motor Driver**: 3-phase PWM (pins 13, 12, 11, 10)
- **Communication**: MIDI input (serial), USB output (HID)

### Supported Aircraft & Controls
- **Airbus A320**: Throttle, Flaps, Landing Gear, Trim (pitch/roll/yaw), Spoilers/Speed Brakes
- Architecture supports expansion for Cessna 172, Glider profiles

### Control Specifications
| Control | Motor | Range | Mode | MIDI CC |
|---------|-------|-------|------|---------|
| Throttle | 0 | 0-180° | Limited | #7 |
| Flaps | 0 | 0-180° | Limited | #11 |
| Landing Gear | 1 | 0-180° | Limited | #32 |
| Trim | 1 | 360° | Endless | #64 |
| Spoilers | 0 | 0-180° | Limited | #2 |

### Output Format
- **USB Device Class**: HID Joystick
- **Axes**: 2 analog axes (Motor 0, Motor 1)
- **Resolution**: 10-bit (0-1023 range)
- **Report Rate**: ~100 Hz

---

## Implementation Phases

### **Phase 1: Configuration System**

**Goal**: Define all control profiles and motor parameters in structured, extensible code.

**Files Modified**: `src/main.cpp`
**Files Created**: `src/config.h`

**Structures**:
```cpp
struct MotorProfile {
  uint8_t id;
  float min_angle;
  float max_angle;
  bool is_endless;
  float voltage_limit;
  const char* label;
};

struct AxisProfile {
  uint8_t motor_id;
  uint8_t midi_cc;
  const char* label;
  bool reversed;
  float scaling_factor;
  MotorProfile motor;
};
```

**A320 Configuration**:
- Throttle (Motor 0, CC#7, 0-180°)
- Flaps (Motor 0, CC#11, 0-180°)
- Landing Gear (Motor 1, CC#32, 0-180°)
- Trim (Motor 1, CC#64, 360° endless)
- Spoilers (Motor 0, CC#2, 0-180°)

**Verification**:
- Config compiles without errors
- Serial output shows all axis parameters loaded

---

### **Phase 2: Motor Controller Abstraction**

**Goal**: Refactor SimpleFOC code to support dual motors with independent control.

**Files Modified**: `src/main.cpp`

**Changes**:
1. Create motor array: `BLDCMotor motors[2]`
2. Create driver array: `BLDCDriver3PWM drivers[2]`
3. Refactor FOC loop to iterate over both motors
4. Helper functions:
   - `void set_motor_target(uint8_t motor_id, float angle)`
   - `float get_motor_angle(uint8_t motor_id)`
   - `void handle_motor_limits(uint8_t motor_id, float& angle)`

**Motor Limits Logic**:
- Limited axes: clamp angle between min/max
- Endless axes: wrap using `fmod(angle, 360)`

**Verification**:
- Both motors initialize successfully
- Manual test: both motors respond to angle commands
- Serial output: both motor angles updating at ~1 kHz

---

### **Phase 3: MIDI Input Handler**

**Goal**: Parse MIDI CC messages and map to motorized axes.

**Files Modified**: `src/main.cpp`

**Implementation**:
1. Initialize `Serial1` at 31250 baud (MIDI standard)
2. State machine MIDI parser (3-byte messages)
3. Message format: `[0xBn, CC#, value (0-127)]`
4. Mapping logic: CC# → AxisProfile → Motor target

**For Limited Axes**:
```
angle = min_angle + (cc_value / 127.0) * (max_angle - min_angle)
```

**For Endless Axes** (Trim):
```
trim_angle += (new_cc_value - last_cc_value) * rotation_scale
```

**Verification**:
- Serial debug: each MIDI CC received and parsed
- Send CC#7 from MIDI controller: Motor 0 moves
- Send CC#64: Motor 1 (trim) rotates endlessly

---

### **Phase 4: Axis Output Scaling**

**Goal**: Convert motor angle to USB joystick 10-bit range (0-1023).

**Files Modified**: `src/main.cpp`

**Function**:
```cpp
uint16_t angle_to_joystick_value(uint8_t motor_id) {
  float angle = get_motor_angle(motor_id);
  float normalized = (angle - min_angle) / (max_angle - min_angle);
  if (reversed) normalized = 1.0 - normalized;
  normalized = constrain(normalized, 0.0, 1.0);
  return (uint16_t)(normalized * 1023);
}
```

**Features**:
- Respects motor limits and reversed flags
- Low-pass filtering (already present in SimpleFOC)
- Output array: `uint16_t axis_values[2]` at ~100 Hz

**Verification**:
- Serial debug: motor angle → joystick value
- Value range stays 0-1023
- Reversed axis inverts correctly

---

### **Phase 5: USB HID Joystick Implementation**

**Goal**: Enumerate as USB joystick, send HID reports.

**Files Modified**: `src/main.cpp`
**Dependencies**: TinyUSB (included in RP2040 Arduino core)

**Implementation**:
1. Include TinyUSB: `#include <Adafruit_TinyUSB.h>`
2. Create HID joystick instance
3. Define HID descriptor (2-axis joystick)
4. HID report structure: `uint16_t x; uint16_t y;`
5. Send reports at ~100 Hz via `usb_hid.sendReport()`

**platformio.ini Update**:
- Add `Adafruit TinyUSB Library` dependency

**Verification**:
- Windows Device Manager: "USB Joystick" appears
- Windows calibrator (`joy.cpl`): axes move 0-100%
- USB reports send at ~100 Hz

---

### **Phase 6: Main Loop Integration**

**Goal**: Orchestrate all systems cleanly.

**Files Modified**: `src/main.cpp`

**Control Loop**:
1. **~1 kHz**: FOC loop for both motors
2. **Async**: MIDI byte input handling
3. **~100 Hz**: Scale motor angles to USB values
4. **~100 Hz**: Send USB HID reports
5. **~1 Hz**: Debug serial output

**Loop Structure**:
```cpp
void loop() {
  // FOC control (1 kHz)
  for (int i = 0; i < 2; i++) {
    motors[i].loopFOC();
    motors[i].move(target_angle[i]);
  }
  
  // MIDI input (async)
  if (Serial1.available()) {
    handle_midi_byte(Serial1.read());
  }
  
  // USB HID output (100 Hz)
  static unsigned long last_usb = 0;
  if (millis() - last_usb > 10) {
    axis_values[0] = angle_to_joystick_value(0);
    axis_values[1] = angle_to_joystick_value(1);
    
    if (usb_hid.ready()) {
      usb_hid.sendReport(...);
    }
    last_usb = millis();
  }
  
  // Debug output (1 Hz)
  static unsigned long last_debug = 0;
  if (millis() - last_debug > 1000) {
    Serial.print("Motor0: "); Serial.println(axis_values[0]);
    last_debug = millis();
  }
}
```

**Verification**:
- All systems initialize without errors
- Motor angles update smoothly
- MIDI input triggers motor movement
- USB reports send at ~100 Hz
- No timing conflicts or jitter

---

## Testing Strategy

### Unit Tests (Hardware)
- Motor initialization and angle commands
- Encoder reading and angle smoothness
- MIDI CC parsing and axis mapping
- Motor angle → joystick value conversion

### Integration Tests
- Dual motors + MIDI + USB simultaneously
- MIDI profile switches activate correct motors
- Endless trim wraps correctly
- USB enumeration and HID reports

### Flight Sim Integration
- Bind axes in MSFS (throttle, flaps, gear, trim, spoilers)
- Send MIDI CC commands from controller
- Verify motors move to control positions
- Test responsiveness and feedback smoothness

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Dual-motor architecture** | Supports flexible multi-axis PCBs; expandable to 3+ motors |
| **MIDI CC for profile switching** | Industry standard, works with any MIDI controller |
| **TinyUSB library** | Already in RP2040 core; no external dependencies |
| **Endless rotation for trim only** | Detected via config flag; simplifies other axis logic |
| **10-bit resolution (0-1023)** | Standard joystick range, maps cleanly to motor steps |
| **Simultaneous motor operation** | Both motors move independently; supports complex scenarios |
| **SimpleFOC FOC loop unchanged** | Maintains stability and performance |

---

## File Structure After Implementation

```
src/
  main.cpp          (refactored with all 6 phases)
  config.h          (MotorProfile, AxisProfile, A320_Config)
platformio.ini      (updated with TinyUSB dependency)
.agentic/
  PLANNING.md       (this file)
AGENTS.md           (updated with reference)
README.md           (updated with status)
.github/
  copilot-instructions.md  (context for future work)
```

---

## See Also
- [README.md](../README.md) — Project overview
- [AGENTS.md](../AGENTS.md) — AI agent instructions
- SimpleFOC [docs](https://docs.simplefoc.com/)
- TinyUSB [HID examples](https://github.com/hathach/tinyusb/tree/master/examples)
