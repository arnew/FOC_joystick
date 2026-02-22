# Test Suite & Debug Tools

Automated testing and minimalistic debugging for the USB HID joystick controller.

## Quick Start

### Automated Test Suite

Run all tests automatically:

```bash
python3 test/test_suite_automated.py
```

This tests:
- ✓ System identification (firmware version, configuration)
- ✓ Motor initial position
- ✓ Motor response to MIDI commands (close-loop)
- ✓ Joystick output scaling (0-1023 range)
- ✓ Motor sweep with MIDI

### Debug Tools (Interactive)

**Monitor joystick output:**
```bash
python3 test/debug_joystick.py
```
Shows real-time motor angle and joystick value with visual progress bar.

**Send MIDI commands:**
```bash
python3 test/debug_midi.py
```
Interactive menu to send individual MIDI CC messages or sweeps.

Example:
```
> cc 64 64
  → Sent CC#64 = 64
> sweep 64 0 127 10
  → Sweeping CC#64: 0 to 127 (step 10)
     CC#64 = 0
     CC#64 = 10
     ...
```

## Files

| File | Purpose |
|------|---------|
| `test_suite_automated.py` | Full automated test suite (no user interaction required) |
| `debug_joystick.py` | Minimalistic joystick monitor |
| `debug_midi.py` | Minimalistic MIDI command sender |
| `midi_controller.py` | Advanced MIDI controller with menu (legacy) |
| `hid_monitor.py` | Pygame-based HID joystick monitor (legacy) |
| `test_config.cpp` | Unit tests for configuration (TODO) |

## Setup

### Prerequisites

```bash
# For all tools
pip3 install pyserial

# For hid_monitor.py only (optional, not needed for basic testing)
pip3 install pygame
```

### Serial Port Permissions (Linux)

```bash
sudo usermod -a -G dialout $USER
# Then log out and back in
```

## Understanding the Output

### System Identification
Shows firmware initialization messages and available axes:
```
=== USB HID Joystick Controller ===
Number of axes: 1
  0: Trim (Motor0, CC#64, endless)
=== Ready ===
```

### Motor Response Test
Example output when MIDI command is sent:
```
Sending MIDI CC#64 value 64...
  MIDI: CC#64 = 64 → Trim Motor0 angle: 3.1416
  Angle: 3.1416 rad (180.0°) | Target: 3.1416 | USB: 1023 (0-1023)
✓ PASS: Motor responded to MIDI
```

### Joystick Monitor
Example output showing real-time values:
```
✓ Connected to /dev/ttyACM0 @ 115200 baud (Ctrl+C to exit)

  Motor Angle      USB Value   Status
--------------------------------------------------
  0.0000 rad       512        ████████████████████░░░░░░░░░░░░░░░░
  1.5708 rad       768        ██████████████████████████████░░░░░░░░
  3.1416 rad       1023       ████████████████████████████████████████
```

## Close-Loop Test Specification

The automated suite verifies the complete control loop:

1. **Send MIDI CC command** via Serial1 @ 31250 baud
2. **Motor receives** and moves to target angle
3. **Rotation detected** by AS5600 encoder
4. **Angle logged** in debug output
5. **Joystick value** (0-1023) computed from angle
6. **Test verifies** angle and joystick output match expectations

Example test sequence:
```
Step 1: Send CC#64 value 64 (sets trim to 50%)
Step 2: Read debug output, extract angle
Step 3: Calculate expected joystick: angle / (2π) * 1023
Step 4: Compare actual vs expected joystick value
Step 5: Log pass/fail
```

## Troubleshooting

### No Serial Ports Found
```bash
# Check connected devices
ls /dev/tty* | grep -E "ACM|USB"

# Verify RP2040 is connected
lsusb | grep Raspberry
```

### Permission Denied
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in
```

### MIDI Not Responding
1. Check dual CDC is enabled (should have 2 ACM ports):
   ```bash
   ls /dev/ttyACM*  # Should show ACM0 and ACM1
   ```
2. Verify firmware was uploaded with correct environment:
   ```bash
   platformio run -e pico_1motor_endless --target upload
   ```
3. Check baud rates:
   - Debug (ACM0): 115200
   - MIDI (ACM1): 31250

## Advanced Usage

### Custom Port Selection
If auto-detection fails, modify port settings in scripts.

### Logging Test Results
```bash
python3 test/test_suite_automated.py > test_results_$(date +%Y%m%d_%H%M%S).log
```

## See Also

- [PLANNING.md](../.agentic/PLANNING.md) — Architecture specification
- [QUICKSTART.md](../.agentic/QUICKSTART.md) — Build & upload instructions
- [TEST_RESULTS.md](../.agentic/TEST_RESULTS.md) — Latest test status
