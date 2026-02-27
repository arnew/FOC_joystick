# Testing & Hardware

Hardware issues, test results, and validation.

---

## Documents

- [TESTING_FINDINGS.md](TESTING_FINDINGS.md) - Hardware issues & fixes (dual CDC, encoder)
- [TEST_RESULTS.md](TEST_RESULTS.md) - Latest automated test status
- [HEADLESS_TESTING.md](HEADLESS_TESTING.md) - CI-safe tests without hardware

---

## Current Test Status

**4 of 6 tests passing** (Feb 22, 2026)

See [TEST_RESULTS.md](TEST_RESULTS.md) for details.

---

## Known Hardware Issues

**Resolved**:
- Dual CDC MIDI conflict → Fixed with separate serial ports
- AS5600 angle resolution → Calibrated I2C timing

**Active**:
- Motor reliability concerns (see [../sessions/SITUATION_ANALYSIS_AND_REWORK_PLAN.md](../sessions/SITUATION_ANALYSIS_AND_REWORK_PLAN.md))

See [TESTING_FINDINGS.md](TESTING_FINDINGS.md) for complete history.

---

## Running Tests

```bash
# Full automated suite
python3 test/test_suite_automated.py

# Interactive debugging
python3 test/debug_joystick.py   # Monitor motor state
python3 test/debug_midi.py       # Send MIDI commands
```
