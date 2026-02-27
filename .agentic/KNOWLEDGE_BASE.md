# Technical Knowledge Base

**Last Updated**: 2026-02-27
**Status**: Working baseline established

---

## Hardware Architecture

### RP2040 Pico
- **MCU**: Dual ARM Cortex-M0+ @ 133MHz
- **RAM**: 264KB SRAM
- **Flash**: 2MB (via picotool)
- **USB**: Native USB 1.1 (TinyUSB stack)
- **Bootloader**: earlephilhower (BOOTSEL button for uploads)

### Motor Control
- **Sensor**: AS5600 12-bit magnetic encoder (I2C @ 0x36)
- **Motor**: 3-phase BLDC with PWM driver
- **Control**: SimpleFOC library (FOC algorithm)
- **Loop Rate**: ~1kHz FOC updates

### USB Interfaces
- **HID**: Joystick (2 axes, 8 buttons) @ ~100Hz reports
- **MIDI**: Native USB MIDI (TinyUSB)
- **CDC**: Virtual serial port @ 115200 baud (debug output)

---

## Software Stack

### PlatformIO Configuration
```ini
platform = https://github.com/maxgerhardt/platform-raspberrypi.git
board = pico
board_build.core = earlephilhower
framework = arduino
lib_deps =
    Simple FOC
    MIDI
build_flags =
    -DHW_CONFIG=0
    -DUSE_TINYUSB
    -DCFG_TUSB_CONFIG_FILE=\"my_tusb_config.h\"
```

### Libraries
- **SimpleFOC**: 2.4.0 (motor control, PID, encoder interface)
- **Adafruit TinyUSB**: 3.7.2 (USB HID + MIDI + CDC)
- **MIDI**: Latest (USB MIDI parsing)

### Build Environments
1. **pico_1motor_endless**: Single motor, 360° endless rotation (trim)
2. **pico_1motor_limited**: Single motor, 0-180° limited (throttle/flaps)
3. **pico_2motor_limited**: Dual motors, both limited range

---

## Working Baseline

### Feature: Main Branch (feature/modularize-main)

**Status**: ✅ **WORKS** - Manual BOOTSEL upload required

**Capabilities**:
- ✅ Motor initialization (SimpleFOC)
- ✅ USB HID joystick enumeration
- ✅ Serial debug output @ 115200
- ✅ Angle tracking and PID control
- ⏳ MIDI input (library linked, handler WIP)
- ⏳ SimpleFOC Commander integration

**Build**:
```powershell
platformio run -e pico_1motor_endless  # ~14-20s
```

**Upload**:
```powershell
# Hold BOOTSEL button, then:
platformio run --target upload -e pico_1motor_endless  # ~15-25s
```

**Serial Output** (expected):
```
=== USB HID Joystick Controller ===
USB: CDC /dev/ttyACM0 (115200)
     Native MIDI port
     HID Joystick (8btn + 2axis)
Initializing Motor 0...
Motor 0 ready
=== Ready ===
A=0.00 T=0.00
~0.0000 0.0000  0.0000  0.0000
A=0.00 T=0.00
```

### Feature: Minimal Branch (feature/tinyusb-minimal)

**Status**: ✅ **WORKS** - Bootloader debugging baseline

**Capabilities**:
- ✅ USB HID joystick (test pattern only)
- ✅ Serial debug output
- ❌ No motor control (stripped for debugging)
- ❌ No MIDI (not added yet)

**Purpose**: Isolate TinyUSB integration from SimpleFOC complexity

**Serial Output** (expected):
```
Status: X=-121 Y=-36 Buttons=89
Status: X=-12 Y=-126 Buttons=F6
```

---

## Known Issues

### 1. TinyUSB Bootloader Reentry ⚠️ LOW PRIORITY

**Problem**: Automated 1200bps DTR reset doesn't trigger bootloader mode

**Impact**: Requires manual BOOTSEL button press for uploads

**Workaround**: Hold BOOTSEL during upload (works 100% reliably)

**Attempts Made**:
1. ❌ TinyUSB CDC callback (`tud_cdc_line_state_cb()`) - timing issue
2. ❌ USB-first initialization - still no automatic reboot
3. ❌ DTR polling in loop - not implemented fully

**Recommended Fix** (for future):
- Research earlephilhower bootloader docs
- Try polling DTR in setup() with 1s timeout
- Or accept manual BOOTSEL as permanent solution

**Documentation**: [.agentic/ci/TINYUSB_BOOTLOADER_ISSUE.md](.agentic/ci/TINYUSB_BOOTLOADER_ISSUE.md)

### 2. MIDI Library Dependency

**Problem**: `#include <MIDI.h>` failed initially

**Solution**: ✅ Added `MIDI` to `lib_deps` in platformio.ini

**Status**: FIXED - compiles successfully

---

## CI/CD Pipeline

### GitHub Actions Workflows

#### 1. code-quality.yml
**Trigger**: Push to any branch
**Runners**: `ubuntu-latest`
**Steps**:
1. Check function size compliance (≤43 lines)
2. Build all 3 PlatformIO environments
**Status**: ✅ Passing

#### 2. headless-test.yml
**Trigger**: Push to any branch
**Runners**: `ubuntu-latest`
**Steps**:
1. Setup Python venv
2. Install pytest + dependencies
3. Run `pytest -m "not hardware"` (simulator tests)
**Status**: ✅ Passing (3 passed, 1 skipped)

#### 3. hardware-test.yml
**Trigger**: Manual dispatch or push to dev/main
**Runners**: `[self-hosted, hardware]`
**Steps**:
1. Setup Python venv
2. Build firmware
3. **Upload firmware** (requires manual BOOTSEL trigger)
4. Run `pytest -m hardware` (live device tests)
**Status**: ⏳ Pending - requires BOOTSEL automation or manual trigger

### GitHub CLI Integration

**Tool**: `gh` CLI (authenticated as arnew)
**Capabilities**:
- Trigger workflows: `gh workflow run hardware-test.yml`
- Monitor runs: `gh run list --workflow=hardware-test.yml`
- View logs: `gh run view <run-id> --log`
- Rerun failed: `gh run rerun <run-id>`

**Documentation**: [.agentic/ci/GITHUB_INTEGRATION.md](.agentic/ci/GITHUB_INTEGRATION.md)

---

## Testing Strategy

### Headless Tests (Simulator)
**Location**: `test/sim_device.py`
**Purpose**: Test axis logic without hardware
**Tests**:
- Limited axis (0-180° mapping)
- Reversed axis
- Endless axis (wrap-around)

**Run**:
```bash
pytest -m "not hardware"
```

### Hardware Tests
**Location**: `test/test_hid_exercise.py`
**Purpose**: Test live device with motor control
**Markers**: `@pytest.mark.hardware`
**Requirements**: 
- Device connected
- Firmware uploaded
- Motor attached (for CI runner)

**Run**:
```bash
RUN_HARDWARE_TESTS=1 pytest -m hardware
```

---

## Development Workflow

### Feature Development

```bash
# Start new feature
git flow feature start my-feature

# Code + test
edit src/...
platformio run -e pico_1motor_endless
# Hold BOOTSEL
platformio run --target upload -e pico_1motor_endless

# Commit
git add -A
git commit -m "feat: description"
git push

# Merge (HUMAN ONLY)
git flow feature finish my-feature
```

### Bug Fixes

```bash
# Start hotfix
git flow hotfix start fix-description

# Fix + test + commit + push
# ...

# Merge (HUMAN ONLY)
git flow hotfix finish fix-description
```

### Testing Before Merge

```bash
# Run all tests
pytest  # Headless tests
RUN_HARDWARE_TESTS=1 pytest -m hardware  # Hardware tests (if device available)

# Check function sizes
grep -A 50 "^void\|^int\|^float" src/*.cpp | wc -l  # Manual check
```

---

## Motor Control Details

### SimpleFOC Configuration

**Controller**: `BLDCMotor motor = BLDCMotor(7);`  // 7 pole pairs
**Sensor**: `MagneticSensorI2C sensor = MagneticSensorI2C(AS5600_I2C);`
**Driver**: 3-phase PWM (pins in config.h)

**PID Tuning** (default):
```cpp
motor.PID_velocity.P = 0.2f;
motor.PID_velocity.I = 20.0f;
motor.PID_velocity.D = 0.001f;
motor.LPF_velocity.Tf = 0.01f;  // 10ms lowpass filter
```

**Control Mode**: `ANGLE` (position control with velocity profile)

### Tuning Process

1. **Calibration**: Run `test/calibrate_pid.py` (ramp test)
2. **SimpleFOC Studio**: Connect via serial, adjust P/I/D live
3. **Save**: Update `pid_config.h` with optimal values
4. **Test**: Run `test/motor_monitor.py` for stability check

**Docs**:
- [PID_TUNING_QUICKSTART.md](../PID_TUNING_QUICKSTART.md)
- [test/RAMP_TEST_GUIDE.md](../test/RAMP_TEST_GUIDE.md)

---

## USB Protocol Details

### HID Report Descriptor

```cpp
TUD_HID_REPORT_DESC_GAMEPAD(
    HID_REPORT_ID(1),
    2,  // 2 axes (X, Y)
    0,  // 0 sliders
    0,  // 0 hats
    8   // 8 buttons
)
```

**Report Format** (8 bytes):
```
Byte 0: X axis (-127 to 127)
Byte 1: Y axis (-127 to 127)
Byte 2: Buttons 0-7 (bitfield)
Bytes 3-7: Reserved
```

**Report Rate**: ~100Hz (10ms interval in main loop)

### MIDI CC Mapping

**Channel**: 1 (flight sim standard)

| CC# | Control        | Motor | Range      |
|-----|----------------|-------|------------|
| 7   | Throttle       | 0     | 0-127 → 0-180° |
| 5   | Flaps          | 0     | 0-127 → 0-180° |
| 9   | Spoilers       | 0     | 0-127 → 0-180° |
| 10  | Trim           | 1     | 0-127 → 0-360° |
| 11  | Landing Gear   | 1     | 0-127 → 0-180° |

**Handling**: `src/midi_handler.cpp` (parses CC, updates motor targets)

---

## Debugging

### Serial Monitor

```powershell
# Windows
& "C:\Users\Arne Wichmann\.platformio\penv\Scripts\platformio.exe" device monitor

# Or via Python
python -m serial.tools.miniterm COM14 115200
```

### Motor Monitoring

```bash
cd test
python motor_monitor.py  # Real-time angle/velocity/PID graphs
```

### HID Debugging

```bash
cd test
python debug_joystick.py  # Read HID reports
```

### MIDI Debugging

```bash
cd test
python debug_midi.py  # Monitor MIDI CC messages
```

---

## Useful Commands

### PlatformIO

```bash
# Clean build
pio run --target clean

# Verbose build
pio run -v

# List devices
pio device list

# Monitor serial
pio device monitor --baud 115200
```

### Git Flow

```bash
# List features
git flow feature

# Publish feature
git flow feature publish my-feature

# Switch between branches
git checkout feature/tinyusb-minimal
git checkout feature/modularize-main
```

### GitHub CLI

```bash
# Check auth
gh auth status

# List workflows
gh workflow list

# Manual trigger
gh workflow run hardware-test.yml

# Check runs
gh run list --limit 5
```

---

## References

- [SimpleFOC Docs](https://docs.simplefoc.com/)
- [TinyUSB Examples](https://github.com/adafruit/Adafruit_TinyUSB_Arduino/tree/master/examples)
- [RP2040 Datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [AS5600 Datasheet](https://ams.com/documents/20143/36005/AS5600_DS000365_5-00.pdf)
- [PlatformIO RP2040](https://docs.platformio.org/en/latest/boards/raspberrypi/pico.html)
