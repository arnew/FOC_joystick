# Usage Guide

How to build, verify, tune, and monitor the FOC joystick.

**Prerequisites**: Python 3, `pyserial` (`pip3 install pyserial`),
PlatformIO, device at `/dev/ttyACM0`.
Most tools accept `--port /dev/ttyACMx` to override.

---

## 1. Build & Upload

```bash
pio run                              # build firmware
pio run -t upload                    # upload (needs 1200bps reset or BOOTSEL)
python3 tools/upload_via_rb.py       # automated: sends RB → waits for BOOTSEL → uploads
```

## 2. Linux Dead Zone Fix

Linux auto-applies a dead zone (`flat=range/16`) to joystick axes.
For a precision FOC encoder this is wrong — zero it out:

```bash
# Persistent (needs root, survives replug):
sudo cp tools/99-foc-joystick.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
# Then replug USB.

# Quick fix (lost on replug, no root):
evdev-joystick --evdev /dev/input/event18 --deadzone 0 --fuzz 0

# Or via jscal:
jscal -s 2,0,0,0,0 /dev/input/js0
```

---

## 3. Verify — Automated Tests

### Quality Goals Suite (the main test)

8 tests (A–H): accuracy, speed, stability, overshoot, tame holds,
fast transitions, random walk, regression patterns.

```bash
python3 test/quality_goals_test_suite.py
python3 test/quality_goals_test_suite.py --json results.json
python3 test/quality_goals_test_suite.py --tests A B D G   # run subset
```

Pass criteria at v0.1: 7/8 (Test G Random Walk at 90% is accepted).
Runtime: ~90 seconds.

### Profile-Specific: Cessna Trim Linearity

Sweeps the full 6480° range (18 turns) forward and reverse,
measures linearity error + hysteresis, then tests both endstops.

```bash
python3 test/test_cessna_trim.py
python3 test/test_cessna_trim.py --json cessna_trim.json
```

### Haptic Layer Test

Exercises detent snapping, endstop hold, spacing uniformity,
HID mapping, and enable/disable — all automated, no physical turning.

```bash
python3 test/tools/trim_wheel_test.py
python3 test/tools/trim_wheel_test.py --json haptic_results.json
```

### Linearity Scan (manual turning)

Turn the wheel slowly from endstop to endstop while the tool records
motor angle vs. HID axis value.  Live bargraph, endstop bounceback
measurement, final linearity grade.

```bash
python3 test/tools/linearity_scan.py
python3 test/tools/linearity_scan.py --bins 60
```

### Unit Tests (no hardware)

```bash
python -m pytest test/unit/ -q
```

---

## 4. Select & Monitor Profiles

### Profile Monitor

Switch profiles, watch @T telemetry and joystick axis values live.
The single tool for "is my profile doing what I expect?"

```bash
python3 test/tools/profile_monitor.py          # monitor current profile
python3 test/tools/profile_monitor.py 5         # switch to profile 5
python3 test/tools/profile_monitor.py --list    # list all profiles
python3 test/tools/profile_monitor.py --fix-deadzone   # also zero Linux dead zone
python3 test/tools/profile_monitor.py --serial-only    # no joystick, just telemetry
python3 test/tools/profile_monitor.py --joy-only       # no serial, just joystick
```

The 11 profiles (switch via MIDI CC#0 bank select or profile_monitor):

| # | Profile | Range | Feel |
|---|---------|-------|------|
| 0 | Cessna Trim | 6480° (18 turns) | 648 uniform detents |
| 1 | A320 Throttle | 90° | IDLE→CLB→FLX→TOGA gates |
| 2 | GA Throttle | 180° | smooth |
| 3 | Prop RPM | 270° | 27 detents |
| 4 | Mixture | 180° | smooth |
| 5 | Cessna Flaps | 100° | 4-notch gates |
| 6 | A320 Spoiler | 90° | RET→½→FULL gates |
| 7 | Glider Airbrake | 90° | smooth |
| 8 | Rudder Trim | 60° | 12 detents |
| 9 | Elevator Trim | 360° | 36 detents |
| 10 | Bench / Free Spin | 36000° | no detents |

---

## 5. Tune

### PID Optimizer (automated)

Coordinate-descent optimizer.  Iterates: edit pid_config.h → build →
upload → measure quality cost → adjust.  Typically converges in 5–8 rounds.

```bash
python3 test/tools/pid_optimizer.py --dry-run           # show plan without running
python3 test/tools/pid_optimizer.py --rounds 15 --patience 3
python3 test/tools/pid_optimizer.py --json pid_result.json
```

**Current best** (pid_config.h): P=16, I=0.2, D=1.0, vel_P=0.1, vel_I=0.5,
LPF Tf=0.001, V_limit=2.0 V.

### Interactive Haptic Setup

Terminal UI for adjusting haptic parameters in real time.
Keyboard controls for range, center, detent count, strength, endstop margin.

```bash
python3 test/tools/trim_setup.py
```

Keys: `r/R` range, `c/C` center, `n/N` detents, `s/S` strength,
`m/M` margin, `e` enable toggle, `0-9` jump to detent, `q` quit.

### SimpleFOC Studio (live PID)

Web app for real-time PID gain adjustment over serial.

1. Visit https://studio.simplefoc.com
2. Connect to `/dev/ttyACM0` at 115200 baud
3. Adjust P/I/D gains live — motor responds immediately
4. When happy, copy values into `include/pid_config.h`

See [tools/simplefoc_studio.md](tools/simplefoc_studio.md) for Commander
protocol details.

---

## 6. Debug

### Serial Monitor

```bash
python3 test/tools/debug_joystick.py     # angle + joystick values from serial
pio device monitor --baud 115200         # raw serial
```

### MIDI

```bash
python3 test/tools/debug_midi.py         # send MIDI CC interactively
```

### HID Joystick

```bash
python3 test/tools/hid_monitor.py        # pygame-based HID axis display
jstest /dev/input/js0                    # raw joystick test (Linux)
```

### Diagnostic Report

Full motor performance analysis — step responses, settling times,
position accuracy across the full range.  Outputs JSON for archiving.

```bash
python3 test/tools/diagnostic_tuning_report.py
python3 test/tools/diagnostic_tuning_report.py --output report.json
```

---

## Quick Reference

| I want to… | Run |
|-------------|-----|
| Check if everything works | `python3 test/quality_goals_test_suite.py` |
| Test a specific profile | `python3 test/tools/trim_wheel_test.py` |
| Watch what the motor is doing | `python3 test/tools/profile_monitor.py` |
| Switch to profile 3 | `python3 test/tools/profile_monitor.py 3` |
| Auto-tune PID | `python3 test/tools/pid_optimizer.py` |
| Adjust haptic feel live | `python3 test/tools/trim_setup.py` |
| Fix Linux dead zone | `sudo cp tools/99-foc-joystick.rules /etc/udev/rules.d/` |
| Upload without BOOTSEL button | `python3 tools/upload_via_rb.py` |
