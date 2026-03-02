# Debug & Diagnostic Tools

Interactive scripts for manual investigation. Not automated tests.

| File | Purpose |
|------|---------|
| `profile_monitor.py` | **Set profile + watch telemetry & joystick live** |
| `linearity_scan.py` | **Verify motor→detent→HID linearity across full range** |
| `debug_joystick.py` | Monitor motor angle + joystick value via serial |
| `debug_midi.py` | Send MIDI CC commands interactively |
| `hid_monitor.py` | Monitor HID joystick via pygame |
| `diagnostic_tuning_report.py` | Collect PID tuning data, produce JSON report |
| `quick_tuning_check.py` | Quick motor response check (step + settle) |
