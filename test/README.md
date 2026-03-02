# Test Directory

Automated testing and debug tools for the USB HID joystick controller.

## Structure

```
test/
├─ quality_goals_test_suite.py   ← THE active test suite (8 tests, 6 sequences)
├─ test_cessna_trim.py           ← Cessna Trim linearity & endstop test
├─ tools/                        Debug & diagnostic scripts (interactive)
├─ unit/                         Headless unit tests (pytest)
└─ archive/                      Superseded tests (reference only)
```

## Quick Start

### Quality Goals Test Suite (requires device)

```bash
python3 test/quality_goals_test_suite.py
```

Runs 8 tests (A–H) across configurable position sequences.
Sends Commander `T` commands (degrees) over serial, reads back angle telemetry.

### Cessna Trim Linearity Test (requires device)

```bash
python3 test/test_cessna_trim.py
python3 test/test_cessna_trim.py --json cessna_trim.json
```

Sweeps the full 6480° range forward and reverse, checks linearity
(max error, hysteresis, slope), then verifies both endstops clamp correctly.

### Headless Unit Tests

```bash
python -m pytest test/unit/ -q
```

### Debug Tools

```bash
python3 test/tools/debug_joystick.py   # monitor angle + joystick
python3 test/tools/debug_midi.py       # send MIDI CC interactively
python3 test/tools/hid_monitor.py      # pygame HID monitor
```

## Prerequisites

```bash
pip3 install pyserial
pip3 install pygame   # only for hid_monitor.py
```

## See Also

- [.agentic/DEVICE_TESTING.md](../.agentic/DEVICE_TESTING.md) — Device detection & CI workflow
- [.agentic/testing/](../.agentic/testing/) — Test plans & results
