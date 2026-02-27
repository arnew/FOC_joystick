# Technical Knowledge Base

**Last Updated**: 2026-02-27
**Status**: Foundation established - working baseline captured

---

## Hardware Architecture

### RP2040 Pico
- **MCU**: Dual ARM Cortex-M0+ @ 133MHz
- **RAM**: 264KB SRAM
- **Flash**: 2MB (via picotool)
- **USB**: Native USB 1.1 (TinyUSB stack)
- **Bootloader**: earlephilhower (BOOTSEL button for uploads)

### Motor Control (CI Runner Only)
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

### Current State: feature/modularize-main

**Build Status**: ✅ Compiles successfully (~14-20s)
**Upload Method**: Manual BOOTSEL press required
**Test Hardware**: CI runner with endless motor

**Capabilities**:
- ✅ Motor initialization (SimpleFOC)
- ✅ USB HID joystick enumeration
- ✅ Serial debug output @ 115200
- ✅ Angle tracking and PID control
- ⏳ MIDI input (library linked, handler WIP)
- ⏳ SimpleFOC Commander integration

**Build Command**:
```powershell
platformio run -e pico_1motor_endless
```

**Upload Procedure**:
```powershell
# 1. Hold BOOTSEL button on Pico
# 2. Run upload command:
platformio run --target upload -e pico_1motor_endless
# 3. Release BOOTSEL when upload completes (~15-25s)
```

**Expected Serial Output**:
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

Where:
- `A=` current angle
- `T=` target angle
- `~` PID debug values (error, P, I, D terms)

---

## Known Issues

### 1. TinyUSB Bootloader Reentry ⚠️ LOW PRIORITY

**Problem**: Automated 1200bps DTR reset doesn't trigger bootloader mode

**Impact**: Requires manual BOOTSEL button press for uploads

**Status**: Acceptable workaround in place

**Workaround**: Hold BOOTSEL during upload (works 100% reliably)

**Root Cause**: Adafruit TinyUSB doesn't implement Arduino-standard DTR-on-reset bootloader reentry. The earlephilhower bootloader supports it, but the TinyUSB CDC stack isn't wired to trigger it.

**Attempts Made**:
1. ❌ TinyUSB CDC callback (`tud_cdc_line_state_cb()`) - timing issue
2. ❌ USB-first initialization (moved Serial.begin before motor init) - no effect
3. ❌ DTR polling concept - not fully implemented

**Recommendation**: Accept manual BOOTSEL as permanent solution unless user requires automation. Feature development is higher priority.

**Future Research** (if needed):
- Check earlephilhower bootloader documentation
- Try polling DTR in setup() with 1s timeout loop
- Consider forking TinyUSB to add reentry hook

---

## CI/CD Pipeline

### GitHub Actions Workflows

#### 1. code-quality.yml
**Trigger**: Push to any branch
**Runners**: `ubuntu-latest`
**Steps**:
1. Check function size compliance (≤43 lines per AGENTS.md)
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
**Runners**: `[self-hosted, hardware]` (CI runner with motor)
**Steps**:
1. Setup Python venv
2. Build firmware
3. **Upload firmware** (requires manual BOOTSEL trigger on runner)
4. Run `pytest -m hardware` (live device tests)
**Status**: ⏳ Pending - requires manual BOOTSEL on runner or automation

### GitHub CLI Integration

**Tool**: `gh` CLI (authenticated as arnew, repo scope)

**Common Commands**:
```bash
# Trigger hardware test manually
gh workflow run hardware-test.yml

# Check status
gh run list --workflow=hardware-test.yml --limit 5

# View logs
gh run view <run-id> --log

# Rerun failed tests
gh run rerun <run-id>
```

**Documentation**: See `.agentic/ci/` for full workflow docs

---

## Testing Strategy

### Headless Tests (No Hardware Required)
**Location**: `test/sim_device.py`
**Purpose**: Test axis math without physical device
**Tests**:
- Limited axis (0-180° MIDI CC → angle mapping)
- Reversed axis
- Endless axis (wrap-around behavior)

**Run**:
```bash
pytest -m "not hardware"
```

### Hardware Tests (CI Runner Required)
**Location**: `test/test_hid_exercise.py`
**Purpose**: Test live device with motor control
**Markers**: `@pytest.mark.hardware`
**Requirements**: 
- Device connected via USB
- Firmware uploaded (manual BOOTSEL)
- Motor attached and calibrated

**Run**:
```bash
RUN_HARDWARE_TESTS=1 pytest -m hardware
```

---

## Development Workflow

### Feature Development

```bash
# Start new feature branch
git flow feature start my-feature

# Edit code
# (edit src/...)

# Build
platformio run -e pico_1motor_endless

# Upload (hold BOOTSEL first!)
platformio run --target upload -e pico_1motor_endless

# Test
pytest  # headless tests

# Commit
git add -A
git commit -m "feat: description"
git push

# Merge (HUMAN ONLY)
git flow feature finish my-feature
```

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
Bytes 3-7: Reserved/padding
```

**Report Rate**: ~100Hz (10ms interval in main loop)

### MIDI CC Mapping (Planned)

**Channel**: 1

| CC# | Control        | Motor | Range      |
|-----|----------------|-------|------------|
| 7   | Throttle       | 0     | 0-127 → 0-180° |
| 5   | Flaps          | 0     | 0-127 → 0-180° |
| 9   | Spoilers       | 0     | 0-127 → 0-180° |
| 10  | Trim           | 1     | 0-127 → 0-360° |
| 11  | Landing Gear   | 1     | 0-127 → 0-180° |

**Implementation Status**: ⏳ Handler skeleton present, parsing logic needed

---

## References

- [SimpleFOC Docs](https://docs.simplefoc.com/)
- [TinyUSB Examples](https://github.com/adafruit/Adafruit_TinyUSB_Arduino/tree/master/examples)
- [RP2040 Datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [AS5600 Datasheet](https://ams.com/documents/20143/36005/AS5600_DS000365_5-00.pdf)
- [PlatformIO RP2040](https://docs.platformio.org/en/latest/boards/raspberrypi/pico.html)
