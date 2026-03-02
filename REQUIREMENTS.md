# Requirements — FOC Joystick

SOPHIST-style requirements. Each requirement is testable, versioned, and
traceable to a milestone in [ROADMAP.md](ROADMAP.md).

---

## Notation

- **ID**: REQ-‹area›-‹number›
- **Priority**: MUST | SHOULD | NICE
- **Verified**: version tag where the test passed on CI/HIL, or PENDING
- **Test**: reference to test case or manual procedure

---

## R1 — Motor Control

| ID | Requirement | Priority | Test | Verified |
|----|-------------|----------|------|----------|
| REQ-MOT-01 | The system MUST hold a commanded position within ±10° under no external load. | MUST | HIL Test A (accuracy) | v0.1-rc |
| REQ-MOT-02 | The system MUST reach a commanded position within 5 s under no external load. | MUST | HIL Test B (speed) | v0.1-rc |
| REQ-MOT-03 | The system MUST maintain a held position with less than 5° standard deviation. | MUST | HIL Test C (stability) | v0.1-rc |
| REQ-MOT-04 | The system MUST NOT overshoot a step command by more than 20° on profiles with detents. | MUST | HIL Test D (overshoot) | v0.1-rc |
| REQ-MOT-05 | The system SHOULD NOT overshoot a step command by more than 10° on smooth profiles. | SHOULD | HIL Test F (fast transitions) | PENDING (v0.2, F-2.8) |
| REQ-MOT-06 | The system MUST support continuous rotation (unbounded angle mode). | MUST | T command ≥720° | v0.1-rc |

## R2 — Haptic Feedback

| ID | Requirement | Priority | Test | Verified |
|----|-------------|----------|------|----------|
| REQ-HAP-01 | The system MUST provide configurable detent positions with per-detent strength. | MUST | Profile switch + manual feel | v0.1-rc |
| REQ-HAP-02 | The system MUST enforce endstops without detent cascade (walk-through). | MUST | HIL Test E (tame holds) + manual push test | v0.1-rc |
| REQ-HAP-03 | The system MUST support gate mode (snap only near detents, free between). | MUST | A320 Throttle profile manual test | v0.1-rc |
| REQ-HAP-04 | The system MUST support smooth mode (no detents, resistance only). | MUST | Bench Test profile | v0.1-rc |
| REQ-HAP-05 | The system MUST support uniform-click mode (evenly spaced, same strength). | MUST | Cessna Trim profile | v0.1-rc |
| REQ-HAP-06 | The system MUST limit detent-to-detent transitions to at most 1 per 300 ms. | MUST | HIL endstop hold, no cascade | v0.1-rc |

## R3 — USB HID

| ID | Requirement | Priority | Test | Verified |
|----|-------------|----------|------|----------|
| REQ-HID-01 | The system MUST present a USB HID Joystick with at least one 16-bit axis. | MUST | Linux evdev absinfo | v0.1-rc |
| REQ-HID-02 | The HID axis MUST track the motor position proportionally across the full range. | MUST | linearity_scan.py | v0.1-rc |
| REQ-HID-03 | The system MUST send a valid initial HID report at boot (no stale axis). | MUST | Boot → evdev read (sentinel fix) | v0.1-rc |
| REQ-HID-04 | The system MUST be recognized as a joystick in Windows Game Controllers (joy.cpl). | MUST | Manual: joy.cpl | PENDING (v0.2, F-2.7) |
| REQ-HID-05 | Each profile SHOULD present a distinct USB product string and PID. | SHOULD | Profile switch → lsusb | v0.1-rc |

## R4 — Profile System

| ID | Requirement | Priority | Test | Verified |
|----|-------------|----------|------|----------|
| REQ-PRO-01 | The system MUST support at least 10 selectable control profiles. | MUST | config.h: 11 profiles | v0.1-rc |
| REQ-PRO-02 | The active profile MUST persist across power cycles (EEPROM). | MUST | Power cycle → same profile | v0.1-rc |
| REQ-PRO-03 | Profile switch MUST trigger USB re-enumeration (new PID/name). | MUST | Commander A‹n› → lsusb change | v0.1-rc |
| REQ-PRO-04 | The system MUST provide a bench-test profile (360°, smooth, no detents). | MUST | HIL quality suite auto-switch | v0.1-rc |

## R5 — Communication

| ID | Requirement | Priority | Test | Verified |
|----|-------------|----------|------|----------|
| REQ-COM-01 | The system MUST accept Commander serial commands (M, T, A, W). | MUST | Serial terminal interaction | v0.1-rc |
| REQ-COM-02 | The system MUST emit telemetry (@T) at ≥10 Hz with target/actual/velocity. | MUST | quality_goals_test_suite.py parser | v0.1-rc |
| REQ-COM-03 | The system MUST accept MIDI CC messages for position control. | MUST | debug_midi.py | v0.1-rc |
| REQ-COM-04 | The system MUST accept MIDI CC#121 for profile switching. | MUST | MIDI profile switch test | v0.1-rc |

## R6 — Build & Deploy

| ID | Requirement | Priority | Test | Verified |
|----|-------------|----------|------|----------|
| REQ-BLD-01 | The firmware MUST build with `pio run -e pico_1motor_endless` without errors. | MUST | CI build gate | v0.1-rc |
| REQ-BLD-02 | The firmware MUST fit in RP2040 flash (< 2 MB) and RAM (< 264 KB). | MUST | Build output: 5% flash, 9% RAM | v0.1-rc |
| REQ-BLD-03 | Upload MUST work via picotool (1200 bps reset → BOOTSEL). | MUST | `pio run -t upload` | v0.1-rc |

## R7 — Sim Integration (v0.2+)

| ID | Requirement | Priority | Test | Verified |
|----|-------------|----------|------|----------|
| REQ-SIM-01 | The HID axis MUST be assignable in MSFS to a control axis. | MUST | Manual: MSFS controls | PENDING (v0.2) |
| REQ-SIM-02 | A companion app SHOULD read SimConnect variables and send MIDI CC to the device. | SHOULD | — | PENDING (v0.4) |
| REQ-SIM-03 | Bidirectional sync MUST NOT oscillate (user push overrides sim). | MUST | — | PENDING (v0.4) |

---

## Traceability

| Milestone | Requirements Verified |
|-----------|---------------------|
| v0.1-rc | REQ-MOT-01…06, REQ-HAP-01…06, REQ-HID-01…03,05, REQ-PRO-01…04, REQ-COM-01…04, REQ-BLD-01…03 |
| v0.2 | + REQ-HID-04, REQ-MOT-05, REQ-SIM-01 |
| v0.4 | + REQ-SIM-02, REQ-SIM-03 |
