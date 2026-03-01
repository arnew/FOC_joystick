# Architecture

USB HID joystick with BLDC motor haptic feedback, controlled by SimpleFOC,
running on RP2040.  MIDI input from a flight-sim companion app positions the
motor; the user pushes back through detent clicks; HID output reports the
result to the simulator.

## System Context

```
  Flight Simulator  ◄──── HID joystick (axis position) ────┐
        │                                                    │
        ▼                                                    │
  Companion App ──── MIDI CC (target position) ────►  RP2040 Firmware
                                                       │    ▲
                                                       │    │
  Test/Tuning Host ── Commander serial ───────────────►│    │
                   ◄── Telemetry @T lines ─────────────┘    │
                                                            │
                                              User Hand ────┘
                                           (pushes motor shaft)
```

Four external actors:

| Actor | Interface | Direction | Semantics |
|-------|-----------|-----------|-----------|
| **Simulator** | MIDI CC | In | "Move this axis to position X" |
| **User hand** | Motor shaft | In | Physical push detected as position deviation |
| **Flight sim** | USB HID | Out | "Axis is now at position Y" |
| **Test host** | CDC serial | In/Out | Commander commands in, telemetry out |

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Outputs                                            │
│   usb_hid          HID joystick report (50 Hz)             │
│   telemetry        @T observation lines (10 Hz)            │
│   statistics       Diagnostic counters                      │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Inputs                                             │
│   midi_handler     MIDI CC → position request               │
│   commander        Serial commands (T, M, A, S, W)          │
│   (user hand)      Detected by Layer 2 as position delta    │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Position Arbiter                                   │
│   haptic_layer     Detent snapping, endstop clamping,       │
│                    deadband filtering, delta tracking        │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Motor Control                                      │
│   motor_control    SimpleFOC FOC loop, PID, idle mgmt       │
├─────────────────────────────────────────────────────────────┤
│ Layer 0: Hardware                                           │
│   AS5600 I²C encoder, 7pp BLDC, 3PWM driver, RP2040        │
└─────────────────────────────────────────────────────────────┘
```

**Rule: data flows down.** Inputs (Layer 3) never write to the motor
directly.  Every position command flows through the haptic layer (Layer 2)
when it is enabled.  The haptic layer is the sole owner of `target_angle[]`
during haptic operation.

## Data Flow: Who Sets the Motor Target

The motor holds exactly one target angle at any time.  The question is
always: who set it, and did it go through the right path?

### When haptic is enabled (normal operation)

```
  MIDI CC ──────────┐
  Commander T ──────┤
  (user pushes) ────┤
                    ▼
              haptic_layer
              ├─ Snap to nearest detent
              ├─ Clamp to endstops
              └─ set_motor_target()
                    │
                    ▼
              motor_control
              └─ motor.move(target_angle)
```

All position commands call `haptic_set_position()`.  User physical
interaction is detected inside `haptic_update()` as a delta between the
expected motor position and the actual shaft angle (read from AS5600).

### When haptic is disabled (free positioning)

```
  MIDI CC ──────────┐
  Commander T ──────┤
                    ▼
              set_motor_target()
                    │
                    ▼
              motor_control
              └─ motor.move(target_angle)
```

No detent snapping.  Motor moves to the exact commanded angle.

### When user pushes with haptic enabled

This is the most interesting path — it closes the human-in-the-loop:

1. Motor holds detent N (PID maintains target angle)
2. User pushes shaft → shaft angle deviates from target
3. `haptic_update()` detects delta > deadband (3°)
4. Haptic layer moves target to detent N±1
5. Motor PID drives shaft to new detent
6. User feels a "click" as the motor snaps into place
7. HID reports the new detent position to the simulator

The deadband prevents PID settling noise from being misread as user input.

## Module Responsibilities

### motor_control — Layer 1

**Owns**: `target_angle[]`, `current_angle[]`, SimpleFOC motor objects.

Single point of motor actuation: only `update_motor()` calls
`motor->move()`.  All other code sets targets via `set_motor_target()`.

Idle management: reduces `voltage_limit` when motor is at rest to prevent
heat buildup.  Must keep torque active when haptic is enabled (detents need
holding force).

### haptic_layer — Layer 2

**Owns**: detent state, snapped position, endstop enforcement.

Delta-tracking pattern: reads `get_motor_angle()`, computes delta from
expected position, applies deadband, accumulates intentional push, snaps
to nearest detent, calls `set_motor_target()`.

Resync mechanism: when an external command (MIDI, Commander) calls
`haptic_set_position()`, the layer resets its delta tracker to avoid
interpreting the resulting motor movement as user input.

Produces `haptic_get_hid_value()` — the HID axis value derived from the
detent position within the configured range, independent of raw motor angle.

### midi_handler — Layer 3

Parses 3-byte MIDI CC messages.  Maps CC number to axis via profile config,
converts CC value (0–127) to angle.  Routes through haptic layer when
enabled.  CC#121 triggers profile switching.

### commander_integration — Layer 3

SimpleFOC Commander serial interface.  Commands:
- **M**: Direct motor PID tuning (SimpleFOC native)
- **T**: Set target — routes through haptic when enabled
- **A**: Switch aircraft profile (triggers reboot for USB re-enum)
- **S**: Print statistics snapshot
- **W**: Haptic layer configuration

### usb_hid — Layer 4

TinyUSB HID joystick: 8 buttons, 2 axes (X/Y), 10-bit (0–1023).
Reports only on value change (avoids USB bus saturation).

HID value source:
- Haptic enabled → `haptic_get_hid_value()` (maps detent position to 0–1023)
- Haptic disabled → `angle_to_joystick_value()` (maps raw motor angle to 0–1023)

### telemetry — Layer 4

Device-side rolling statistics (500-sample ring buffer).  Emits structured
`@T` lines at 10 Hz over CDC serial.  Format:

```
@T ms,target_rad,actual_rad,error_rad,variance,settled
```

Purely observational — never influences motor control.  Host-side test
scripts parse these lines for automated quality assertions.

### config / profile_manager — Cross-cutting

Static profile data (MotorProfile, AxisProfile, ProfileMetadata) defined in
`config.h`.  Runtime profile switching (EEPROM persistence, USB identity
reconfiguration) in `profile_manager`.

Aircraft profiles: Cessna, Airbus A320, Glider — each defines axes with
MIDI CC mappings, motor limits, and HID output scaling.

### statistics — Layer 4

Counters for loop timing, motor hold quality, message rates, uptime.
Read-only diagnostic aid, no control influence.

## Physical Model

The motor operates in SimpleFOC **angle mode** — the PID acts as a virtual
torsion spring pulling the shaft toward `target_angle`.

```
  Motor physics:  τ_motor = PID(target − actual)
  User force:     τ_user  = hand push on shaft
  Net torque:     τ_net   = τ_motor + τ_user
  Result:         shaft moves toward equilibrium
```

When the user pushes hard enough to overcome PID holding torque, the shaft
deviates from target.  The haptic layer detects this deviation and decides
whether to move the target (switch detents) or resist (endstop clamping).

**Thermal constraint**: The motor's voltage limit (2.0V) is the thermal
ceiling.  The idle timeout exists to prevent heat buildup when no interaction
is happening.  When haptic is active, the motor must maintain holding torque
indefinitely — this is acceptable because detent holding current is low
(shaft at rest, small correction torques only).

## Build Configurations

| PlatformIO env | Motor mode | Haptic | Notes |
|----------------|-----------|--------|-------|
| `pico_1motor_endless` | Endless (0–2π) | Runtime | Default, tested |
| `pico_1motor_limited` | Limited (0–π) | Runtime | Clamped range |
| `pico_trim_preview` | Endless | Runtime | Retired alias of endless |

`pico_trim_preview` has been retired — the haptic layer with runtime config
(`W R360`, `W D48`, `W C180`) provides equivalent functionality.  The env
now builds identically to `pico_1motor_endless`.

## Test Instrumentation

```
  RP2040 ──── /dev/ttyACM0 (CDC) ──── Test Host
                │                        │
                │  Commander in ◄────────┤
                │  @T telemetry out ────►│
                │                        │
                ├── /dev/hidrawN ───────►│ (HID reports)
                └── MIDI ◄──────────────┤ (not yet used in tests)
```

Tests use a request-observe loop:
1. Send Commander `T<angle>` to request motor position
2. Read `@T` telemetry lines to observe actual position, error, variance
3. Assert quality goals (resolution, speed, precision, overshoot)

The haptic test suite uses Commander `W` commands to configure detent
parameters, then physical observation via `@T` lines to verify behavior.

## Resolved Architecture Debts

1. **`trim_wheel_preview` retired** — haptic layer with `range_deg=360,
   detent_count=48` replaces it.  Dead code in `trim_wheel_preview.cpp/h`
   can be deleted once confirmed unnecessary.

2. **Idle timeout is haptic-aware** — `update_motor()` checks
   `haptic_get_config().enabled` and keeps voltage active when haptic needs
   holding torque, instead of relying on `#ifdef TRIM_WHEEL_PREVIEW`.

3. **MIDI routes through haptic** — `process_midi_message()` calls
   `haptic_set_position()` when haptic is enabled, consistent with
   Commander `T` command behavior.

4. **Unified HID output path** — `service_hid_output()` uses the same
   haptic-enabled/disabled branch regardless of build env.  No more
   `#ifdef TRIM_WHEEL_PREVIEW` in the HID path.

## Remaining Architecture Debts

1. **Compile-time motor type vs runtime profiles** — `get_motor_profile()`
   uses `#ifdef MOTOR_LIMITED`, ignoring per-axis motor config in profiles.
   HID output normalization may disagree with MIDI input scaling.

2. **Global state coupling** — `target_angle[]`, `current_angle[]`, and
   motor objects are exported as bare globals in `motor_control.h`.
   Acceptable for single-motor embedded code, but limits testability.

3. **`config.h` split-brain** — Declares `g_active_profile` extern and
   getter/setter prototypes, but definitions live in `profile_manager.cpp`.
   Not self-contained.
