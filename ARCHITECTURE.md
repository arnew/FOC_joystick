# Architecture — FOC Joystick Controller

## System Overview

A USB composite device: HID joystick + MIDI input + CDC serial.
One BLDC motor with a magnetic angle sensor provides force-feedback
haptic detents for flight simulator controls.

```
  ┌─────────────┐     USB HID      ┌────────────────┐
  │  RP2040      │ ◄──────────────► │ Flight Sim     │
  │  + AS5600    │     USB MIDI     │ (MSFS, X-Plane)│
  │  + BLDC 7pp  │ ◄──────────────► │                │
  │              │     CDC serial   │ Host tools     │
  │              │ ◄──────────────► │ (tuning, test) │
  └─────────────┘                   └────────────────┘
```

**Hardware**: RP2040 (Raspberry Pi Pico), AS5600 I2C magnetic encoder,
BLDC motor (7 pole pairs), 3-PWM driver (pins 13/12/11/10).

**Stack**: PlatformIO, earlephilhower Arduino core, SimpleFOC v2.4.0,
TinyUSB (composite HID+MIDI+CDC), MIDI library.


## Source Tree

```
include/
  pid_config.h              PID gains & limits (compile-time #defines)
  my_tusb_config.h          TinyUSB endpoint/descriptor configuration

src/
  config.h                  ControlProfile struct, 11 profiles, detent maps
  main.cpp                  setup(), loop(), rate scheduling
  motor_control.cpp/h       SimpleFOC init, FOC loop, target/angle accessors
  haptic_layer.cpp/h        Observe/snap/set detent engine (v2)
  profile_manager.cpp/h     EEPROM persistence, USB identity from profile

  input/
    commander_integration   Serial Commander: M T A W commands
    midi_handler            MIDI CC → position, CC#121 → profile switch

  output/
    usb_hid                 TinyUSB HID joystick (16-bit axes, 8 buttons)
    telemetry               @T structured output, ring buffer, EMA RMS
```


## Layered Architecture

```
Layer 0  Hardware      AS5600 sensor, BLDC driver, RP2040 peripherals
Layer 1  Motor         SimpleFOC angle-mode PID → motor.move(target)
Layer 2  Haptic        Observe actual → snap to detent → set target
Layer 3  Input         MIDI CC handler, Serial Commander (M/T/A/W)
Layer 4  Output        USB HID reports, @T telemetry lines
Cross    Config        ControlProfile table, profile persistence
```

**Rule**: only Layer 1 (`update_motor`) calls `motor.move()`.
Everything else sets targets via `set_motor_target()`.
Layer 2 reads actual angle via `get_motor_angle()`.


## Main Loop — Execution Order

```cpp
void loop() {
  update_motor();          // 1. FOC control (~1kHz)
  telemetry_update();      // 2. Feed ring buffer
  haptic_update();         // 3. Observe → snap → set target
  service_midi_input();    // 4. Bounded MIDI burst (≤8 CC, ≤500µs)
  update_commander();      // 5. Serial commands
  service_hid_output();    // 6. HID report at 50Hz
  telemetry_output();      // 7. @T line at 10Hz
}
```

All timing is cooperative — no interrupts, no RTOS.


## Motor Control (Layer 1)

SimpleFOC angle mode, unbounded (−∞ to +∞ radians).

| Parameter         | Value | Source          |
|-------------------|-------|-----------------|
| Angle P           | 16.0  | pid_config.h    |
| Angle I           | 0.2   | pid_config.h    |
| Angle D           | 1.0   | pid_config.h    |
| Velocity P        | 0.1   | pid_config.h    |
| Velocity I        | 0.5   | pid_config.h    |
| Voltage limit     | 2.0V  | Thermal ceiling |
| Velocity limit    | 4.0   | Overshoot cap   |
| LPF Tf            | 0.001 | Phase-lag min   |

PID gains are **global** — all 11 profiles share the same motor tuning.
This is a known limitation; see *Architecture Debts* below.

Integral reset: `reset_motor_pid_integral()` zeroes I-term accumulators
on detent transitions to prevent wind-up.

Boot centering: `center_motor_to()` offsets the sensor reference frame
so the profile's `center_deg` maps to the motor's current physical
position.  The shaft does not move.


## Haptic Layer (Layer 2)

**v2 architecture**: observe / snap / set.

1. Read actual shaft angle from motor
2. Find nearest detent (or gate capture zone)
3. Set motor target to that detent's angle

The haptic layer does NOT touch PID parameters.
It only decides WHAT target the motor holds.

### Detent Modes

| Mode     | Description                | Example              |
|----------|----------------------------|----------------------|
| Uniform  | N evenly-spaced clicks     | Cessna Trim (18)     |
| Map      | Arbitrary positions 0–100% | Cessna Flaps (5 pos) |
| Gate     | Snap only near detents     | A320 Throttle (6)    |
| Smooth   | detent_count=0, no snapping| Cessna Throttle      |

### HapticConfig Fields

```
range_deg, center_deg, detent_count, detent_strength,
endstop_margin, enabled, detent_map, detent_map_size,
gate_mode, gate_capture_deg
```

All adjustable at runtime via Commander `W` commands:
`WE` enable, `WR` range, `WC` center, `WN` count,
`WS` strength, `WM` margin.


## Profile System

11 control profiles defined in `config.h` as `ALL_PROFILES[]`:

| # | Profile         | MIDI CC | Range° | Detents    | Gate |
|---|-----------------|---------|--------|------------|------|
| 0 | Cessna Trim     | 1       | 360    | 18 uniform | no   |
| 1 | Cessna Throttle | 2       | 180    | smooth     | no   |
| 2 | Cessna Flaps    | 3       | 120    | 5 map      | no   |
| 3 | Cessna Gear     | 4       | 90     | 2 map      | no   |
| 4 | A320 Trim       | 5       | 180    | 24 uniform | no   |
| 5 | A320 Throttle   | 6       | 120    | 6 map      | yes  |
| 6 | A320 Flaps      | 7       | 90     | 5 map      | no   |
| 7 | A320 Spoilers   | 8       | 90     | 3 map      | no   |
| 8 | Glider Trim     | 9       | 360    | 24 uniform | no   |
| 9 | Glider Spoiler  | 10      | 90     | 2 map      | no   |
|10 | Bench Test      | 11      | 360    | 36 uniform | no   |

Queryable from the device: `A` lists all profiles, `A3` switches.

Each profile also defines `usb_pid` and `usb_product` so the device
re-enumerates with a profile-specific USB identity after switching.
Profile index is persisted to EEPROM.  Switching triggers a reboot.

### ControlProfile Struct

```cpp
struct ControlProfile {
    const char* name;
    uint8_t     midi_cc;
    bool        reversed;           // invert HID axis
    float       range_deg;
    float       center_deg;
    float       endstop_margin;
    uint16_t    detent_count;       // uniform clicks (0 = smooth)
    float       detent_strength;
    const DetentPoint* detent_map;  // custom map (nullptr = uniform)
    uint8_t     detent_map_size;
    bool        gate_mode;
    float       gate_capture_deg;
    uint16_t    usb_pid;
    const char* usb_product;
};
```


## Communication Interfaces

### USB HID (Layer 4)

16-bit axes (0–65535), 8 buttons.  Reports sent at 50 Hz, only on change.

HID value source:
- Haptic enabled → `haptic_get_hid_value()` (detent position mapped)
- Haptic disabled → `angle_to_joystick_value()` (raw motor angle mapped)

Axis reversal applied from `ControlProfile::reversed`.

### USB MIDI (Layer 3)

Receives standard MIDI CC messages (3 bytes).
- Profile's `midi_cc` → position command (0–127 → 0–100% of range)
- CC#121 → profile switch

Routes through haptic layer when enabled.

### Serial Commander (Layer 3)

SimpleFOC Commander over CDC serial:

| Cmd | Function                                        |
|-----|-------------------------------------------------|
| M   | Motor PID tuning (MAP/MAI/MAD/MVP/MVI/MAL/MAF) |
| T   | Set target in degrees (routes through haptic)   |
| A   | List profiles / switch (`A`, `A3`)              |
| W   | Haptic config (WE/WR/WC/WN/WS/WM)              |

### Telemetry (Layer 4)

Structured `@T` lines at 10 Hz over CDC serial:
```
@T <ms>,<target>,<actual>,<error>,<rms>,<variance>,<settled>
```

Ring buffer (0.5s, ~500 samples) for variance + settle detection.
EMA filter (τ ≈ 200ms) for O(1) RMS.  Read-only — never influences
motor control.


## Build

Single PlatformIO environment:

| Env                    | Mode     | Status  |
|------------------------|----------|---------|
| `pico_1motor_endless`  | Endless  | Tested  |

Platform: `maxgerhardt/platform-raspberrypi`, board `pico`,
core `earlephilhower`, framework `arduino`.

Build flags: `-DUSE_TINYUSB`, TinyUSB config via `my_tusb_config.h`.


## Architecture Debts

### 1. Global PID — no per-hardware motor parameters

PID gains (pid_config.h) are compile-time `#define`s shared by all
profiles.  The user has observed that I=0.2 "kills the fun" on
throttle-type controls where smooth free movement is desired, while
the same I-term is needed for position-holding on trim wheels.

Future hardware with different motors will need different gains
entirely.  The design direction (v0.2+):

```
  MotorConfig (per hardware)       ControlProfile (per aircraft control)
  ├─ pole_pairs                    ├─ name, midi_cc, range, detents...
  ├─ pid_P, pid_I, pid_D           └─ (what the axis does)
  ├─ vel_P, vel_I
  ├─ voltage_limit
  └─ lpf_Tf

  Selected independently:
    Hardware = which motor is connected
    Profile  = which aircraft control to emulate
```

This separates "what motor am I driving?" from "what does this axis
feel like?" — allowing any profile on any hardware.

### 2. Global state coupling

`target_angle`, `current_angle`, and motor objects are bare globals
in `motor_control.h`.  Acceptable for single-motor embedded code, but
limits testability and multi-motor scaling.

### 3. config.h split-brain

Declares `g_active_profile` extern and getter/setter prototypes, but
definitions live in `profile_manager.cpp`.  Not self-contained.
