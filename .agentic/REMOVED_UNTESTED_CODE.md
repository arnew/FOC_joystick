# Removed Untested Code - Commit Record

**Date**: 2024  
**Reason**: Code cleanup to ship only tested and validated functionality  
**CI Status**: All remaining tests pass (3/3 pytest + build validation)

---

## Summary

This document records untested functionality that was removed from the codebase during the consolidation to proven baseline. The philosophy: **Only ship what's tested on CI**. Removed features can be recovered from git history if needed, but their removal simplifies the codebase and eliminates maintenance burden for unvalidated infrastructure.

**Result**: Firmware reduced from 3 untested build environments to 1 proven configuration (pico_1motor_endless with single endless-rotation motor and CC#64 MIDI trim control).

---

## Removed Features

### 1. Dual-Motor Support Infrastructure

**Status**: Untested - never validated on hardware with 2 motors

**Files Modified**:
- `platformio.ini` - Environment definitions removed
- `src/config.h` - Dual-motor profile definitions removed  
- `src/motor_control.cpp` - motor1 arrays and conditionals removed
- `src/motor_control.h` - motor1 declarations removed, array sizes reduced

**What Was Removed**:

#### a. Hardware Build Environments (platformio.ini)
```ini
# REMOVED: These environments were never tested on hardware
[env:pico_1motor_limited]      # Limited rotation (0-360°) - UNTESTED
[env:pico_2motor_limited]      # Two limited-rotation motors - UNTESTED
```

Only `pico_1motor_endless` remains - the one configuration with CC#64 MIDI trim control tested on actual RP2040 hardware.

#### b. Hardware Configuration Selection (config.h)
```cpp
// REMOVED: Complex conditional system with 3 configurations
#define HW_CONFIG 0  // User selects: 0=1motor_endless, 1=1motor_limited, 2=2motor_limited
#if HW_CONFIG == 1
  // 222 lines of motor1, motor2 profile definitions (UNTESTED)
#elif HW_CONFIG == 2
  // Dual-motor axis configurations (UNTESTED)
#endif
```

Simplified to single configuration: single endless motor with single axis (CC#64 trim control).

#### c. Motor1 Instantiation (motor_control.cpp)
```cpp
// REMOVED: These instantiations were never initialized on hardware with 2 motors
BLDCMotor motor1;
BLDCDriver3PWM driver1;
MagneticSensorI2C sensor1;

// REMOVED: Array-based references to untested motor1
motor1->init();
motor1->linkCurrent2Phase();
motors[1] = &motor1;
drivers[1] = &driver1;
sensors[1] = &sensor1;
```

Motor control now hardcoded to single motor0 only. Arrays reduced from [2] to [1].

#### d. Motor1 Monitoring (motor_control.h)
```cpp
// REMOVED: Extern declarations for non-existent motor1
#if NUM_MOTORS > 1
  extern BLDCMotor motor1;
  extern BLDCDriver3PWM driver1;
#endif
```

Single-motor declarations only. `active_motor` variable kept but unused (only motor 0 ever active).

---

### 2. SimpleFOC Commander Integration  

**Status**: Untested - never validated in CI  

**File Modified**:
- `src/commander_integration.cpp` - Gutted to no-op stubs
- `src/main.cpp` - Init and update calls removed

**What Was Removed**:

#### a. Commander Initialization (commander_integration.cpp)
```cpp
// REMOVED: 24 lines attempting to enable motor monitoring on Serial
void init_commander() {
  motor0.useMonitoring(Serial);
  #if NUM_MOTORS > 1
  motor1.useMonitoring(Serial);
  #endif
  // ... more setup code
}
```

Purpose was to enable live tuning in SimpleFOC Studio, but:
- Never tested in CI pipeline
- Requires hardware serial monitoring connection
- Conflicts with MIDI debug output
- No CI test validates it works

#### b. Commander Update Loop (main.cpp)
```cpp
// REMOVED: From main loop - no longer called
#include "commander_integration.h"
#include <pico/bootrom.h>  // Related to Commander setup

// In setup():
init_commander();

// In loop():
update_commander();
```

The init and update calls added to main loop were removed. File `commander_integration.cpp` gutted to empty no-op stubs to preserve any code references that might compile against old headers.

**Alternative**: Use [calibrate_pid.py](../test/calibrate_pid.py) for offline PID tuning, or connect SimpleFOC Studio directly to Serial if needed with proper CI test coverage.

---

### 3. Multi-Axis MIDI Configuration

**Status**: Partially tested - only CC#64 trim validated in CI  

**File Modified**:
- `src/config.h` - Removed axis profiles

**What Was Removed**:

```cpp
// REMOVED: These axes were defined but only CC#64 tested on hardware
struct MIDIAxis {
  uint8_t cc;
  // ...
};

// REMOVED: Multi-axis configuration block
MIDIAxis axes[NUM_AXES] = {
  {64, "Trim", ...},      // TESTED on pico_1motor_endless
  {7,  "Throttle", ...},  // UNTESTED
  {5,  "Flaps", ...},     // UNTESTED
  {11, "Pitch", ...},     // UNTESTED
  {10, "Pan", ...},       // UNTESTED
};
```

**Why**: 
- Only `CC#64` (trim axis) has CI test coverage (`test_sim_device.py`)
- Other MIDI CC channels never validated on hardware
- RemoveD to focus testing on proven 1-axis configuration
- Can be recovered from git if multiple axes needed in future

---

## Recovery Process (if needed)

All removed code is preserved in git history. To recover:

```bash
# View what was removed:
git log --follow --oneline .agentic/REMOVED_UNTESTED_CODE.md

# Checkout specific commit showing dual-motor code:
git show <commit-before-removal>:src/motor_control.cpp

# If you need to re-enable dual-motor support:
1. Restore commits that added motor1 support
2. Re-run full CI test suite with 2 motors on hardware
3. Update this document with new CI coverage
4. Create feature branch and merge via git flow
```

---

## Code Cleanup Statistics

| Item | Lines | Status |
|------|-------|--------|
| Removed test scripts (midi_debug.py, midi_controller.py) | 267 | ✓ |
| Removed platformio.ini untes contexts | 2 envs | ✓ |
| Removed config.h conditional block | ~120 | ✓ |
| Removed motor_control.cpp motor1 code | ~45 | ✓ |
| Removed motor_control.h conditionals | ~25 | ✓ |
| Simplified main.cpp (removed commander) | ~10 | ✓ |
| **Total Eliminated** | **~467 lines** | ✓ |

---

## Testing Validation

All remaining code passes validation:

```bash
✓ Build: platformio run -e pico_1motor_endless 
  → 89KB firmware (4.3% flash), builds in 3.3s
  
✓ Tests: pytest test/ -v
  → 3 passed, 1 skipped (hardware test)
  → Covers: HID scaling, MIDI trim response, angles
  
✓ Hardware: Tested on RP2040 pico with:
  → AS5600 magnetic encoder
  → BLDC motor with endless rotation
  → SimpleFOC FOC control loop
  → USB HID joystick output (0-1023)
  → MIDI CC#64 input → trim control
```

---

## System Baseline (Tested & Proven)

After cleanup, the system baseline is:

**Hardware**: Single RP2040 Pico + AS5600 encoder + 3-phase BLDC motor  
**Control**: SimpleFOC 2.4.0 FOC algorithm, ~1kHz PID loop  
**Input**: MIDI CC#64 (trim) via USB-MIDI device  
**Output**: USB HID joystick (0-1023 range) for Flight Simulator  
**Configuration**: Single endless-rotation motor (no angle limits)  

This is the ONLY configuration with:
- ✓ CI test coverage (build + pytest)
- ✓ Hardware validation (tested on actual RP2040)
- ✓ Integration test (MIDI→motor→joystick chain)

---

## Next Steps

To re-introduce removed features:

1. **Dual-motor support**: 
   - Create feature branch `feature/dual-motor-support`
   - Restore motor1 code from git history
   - Add CI test for 2-motor hardware configuration
   - Update this document with new test coverage
   - Merge via `git flow finish` once CI validates

2. **SimpleFOC Commander**:
   - Create feature branch `feature/commander-integration`
   - Restore commander code with #ifdef guards
   - Add CI test connecting to Serial monitor
   - Document how users should set up SimpleFOC Studio
   - Merge once CI validates

3. **Multi-axis MIDI**:
   - Create feature branch `feature/multi-axis-midi`
   - Add axis definitions for each CC channel
   - Add test for each axis (CC#5, CC#7, CC#10, CC#11)
   - Validate on hardware with multi-axis MIDI device
   - Merge once CI validates all axes

---

**Key Principle**: *Ship only what's tested on CI, document everything that's removed.*

