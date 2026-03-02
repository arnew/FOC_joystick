# Testing & Hardware

Hardware issues, test results, and validation.

---

## Documents

- [TESTING_FINDINGS.md](TESTING_FINDINGS.md) - Hardware issues & fixes (dual CDC, encoder)
- [TEST_RESULTS.md](TEST_RESULTS.md) - Latest automated test status
- [HEADLESS_TESTING.md](HEADLESS_TESTING.md) - CI-safe tests without hardware

---

## Current Test Status

**7 of 8 quality goals passing** (v0.1, Feb 28, 2026)

Test G (Random Walk) scores 18/20 — accepted threshold.
See [TEST_RESULTS.md](TEST_RESULTS.md) for details.

---

## Known Hardware Issues

**All resolved** as of v0.1:
- Dual CDC MIDI conflict → separate serial ports
- AS5600 angle resolution → calibrated I2C timing
- Motor reliability → power-cycle resolves intermittent issues
- USB CDC overflow → reduced telemetry rate, ring buffer

See [TESTING_FINDINGS.md](TESTING_FINDINGS.md) for complete history.

---

## Running Tests

```bash
# Quality goals suite (requires device)
python3 test/quality_goals_test_suite.py

# Cessna Trim linearity (requires device)
python3 test/test_cessna_trim.py

# Headless unit tests
python -m pytest test/unit/ -q

# Interactive debugging
python3 test/tools/debug_joystick.py   # Monitor motor state
python3 test/tools/debug_midi.py       # Send MIDI commands
```
