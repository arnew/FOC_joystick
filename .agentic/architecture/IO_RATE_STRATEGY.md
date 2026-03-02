# I/O Update Rate Strategy (MIDI + HID + Debug)

**Date**: 2026-02-27  
**Scope**: `src/main.cpp` runtime scheduling for RP2040 composite USB device

---

## Problem

The RP2040 uses one USB controller for all three interfaces:
- USB MIDI input
- USB HID joystick output
- USB CDC debug output

Previous instability came from excessive/poorly-scheduled USB activity. A specific risk remained: MIDI was drained with an unbounded `while (usb_midi.available())` loop, which can starve motor control (`update_motor`) under burst input.

---

## Design Goals

1. Keep motor control loop responsiveness highest priority.
2. Keep joystick output responsive for simulator use.
3. Keep debug human-readable without risking USB congestion.
4. Use simple, explicit, interval-based scheduling (KISS).

---

## Rate Budget Concept

### Priority order
1. **FOC update** (every loop, best-effort high frequency)
2. **MIDI ingest** (bounded time slice per loop)
3. **HID report** (fixed interval)
4. **Debug output** (fixed low rate + non-blocking)

### Chosen runtime budgets

| Channel | Policy | Target/Limit | Rationale |
|---|---|---:|---|
| FOC | Always first in loop | best effort (~kHz) | Motor stability is primary control objective |
| MIDI IN | Bounded burst processing | max 24 bytes OR 500 us per loop | Prevents long MIDI bursts from monopolizing CPU/USB service |
| HID OUT | Interval scheduler | 20 ms (50 Hz) | Sufficient for joystick feel, halves bus load vs 100 Hz |
| Debug OUT | Interval + non-blocking gate | 1000 ms (1 Hz) | Human-readable telemetry, avoids CDC backpressure |

---

## Implementation Summary

Implemented in `src/main.cpp` with small helper functions:
- `service_midi_input()`
  - Processes MIDI bytes until one budget is hit:
    - `MIDI_MAX_BYTES_PER_LOOP = 24`
    - `MIDI_BUDGET_US = 500`
- `service_hid_output(now_ms)`
  - Sends joystick report every `HID_UPDATE_INTERVAL_MS = 20` ms
- `service_debug_output(now_ms)`
  - Emits one compact line at `DEBUG_UPDATE_INTERVAL_MS = 1000` ms
  - Sends only when `Serial.availableForWrite() >= 32`
  - Uses single `Serial.println()` line to reduce transaction count

Main loop order:
1. `update_motor(0)`
2. `service_midi_input()`
3. `service_hid_output(now_ms)`
4. `service_debug_output(now_ms)`

---

## Why This Is Safer

- Removes unbounded MIDI drain behavior.
- Keeps USB CDC from blocking control loop when host does not read debug fast enough.
- Gives predictable USB load envelope with explicit constants.
- Keeps code simple, observable, and easy to tune.

---

## Tuning Knobs

If behavior requires adjustment, only tune these constants in `src/main.cpp`:
- `HID_UPDATE_INTERVAL_MS`
- `DEBUG_UPDATE_INTERVAL_MS`
- `MIDI_MAX_BYTES_PER_LOOP`
- `MIDI_BUDGET_US`

Recommended process:
1. Change **one** knob.
2. Build and run test suite.
3. Validate on hardware sweep (with 1.5s step spacing in `test/debug_midi.py`).

---

## Validation Performed

- Firmware build for `pico_1motor_endless`: success
- Python test suite (`pytest test/ -v`): pass on simulator tests, hardware tests skipped unless enabled

Hardware validation checklist (manual):
1. Run `python3 test/debug_midi.py`
2. Execute `sweep 64 0 64 16 1.5`
3. Confirm per-step motion and stable debug line cadence
4. Run `python3 test/test_suite_automated.py --test sweep`

---

## Non-Goals

- No reintroduction of removed PID auto-tuning or dual-motor experiments.
- No complex RTOS/task framework; interval scheduler only.
