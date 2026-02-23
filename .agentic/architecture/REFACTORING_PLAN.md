# Repository Cleanup & Code Refactoring Plan

**Status**: Planned  
**Date**: February 23, 2026  
**Estimated Effort**: 12-16 hours  

---

## Overview

Major refactoring to modularize monolithic `main.cpp` (727 lines) into clean, maintainable modules following UNIX/KISS philosophy and AGENTS.md guidelines.

### Goals

- ✅ Refactor main.cpp into logical modules (<100 lines each)
- ✅ Functions fit on one screen (25-43 lines per AGENTS.md)
- ✅ Repository cleanup (remove build artifacts, organize structure)
- ✅ Add SimpleFOC Studio reference/integration
- ✅ Maintain test-driven workflow
- ✅ Follow git-flow (feature branches)

### Non-Goals

- ❌ Change motor control logic (preserve functionality)
- ❌ Rewrite SimpleFOC integration (keep as-is)
- ❌ Break existing tests (must remain passing)

---

## Current State Analysis

### File Structure (Before)

```
src/
  ├── main.cpp           727 lines (MONOLITHIC)
  └── config.h           219 lines

include/
  ├── pid_config.h        76 lines
  └── my_tusb_config.h    93 lines

test/                    Python tools
.pio/                    Build artifacts
.venv/                   Python venv
```

**Total C++ code**: 1,115 lines across 4 files

### main.cpp Analysis (727 lines)

**Sections** (by concern):

1. **USB Setup** (lines 1-31)
   - USB HID device (`usb_hid`)
   - USB MIDI device (`usb_midi`)

2. **Motor Definitions** (lines 33-90)
   - Sensor/motor/driver initialization
   - Motor arrays for dual-motor support
   - State variables (target_angle, current_angle, axis_values)

3. **PID Parameter Storage** (lines 92-130)
   - `PIDGains` struct
   - Runtime gain storage for online parameter transfer

4. **Serial Command Handling** (lines 132-301)
   - `handle_serial_command()` - 118 lines (TOO LARGE)
   - `apply_pid_gains()` - 18 lines
   - `print_current_gains()` - 33 lines
   - Custom text protocol parsing

5. **MIDI Input** (lines 303-409)
   - `handle_midi_byte()` - 28 lines (state machine)
   - `process_midi_message()` - 34 lines
   - USB MIDI packet reading

6. **Motor Control** (lines 411-493)
   - `set_motor_target()` - 23 lines
   - `handle_motor_limits()` - 56 lines (boundary checking)

7. **USB HID Output** (lines 495-563)
   - `setup_usb_hid()` - 38 lines
   - `send_hid_report()` - 15 lines
   - HID report descriptor

8. **Setup & Loop** (lines 565-727)
   - `setup()` - 91 lines (TOO LARGE)
   - `loop()` - 65 lines

**Problems**:
- ❌ **Monolithic**: All concerns in one file
- ❌ **Large functions**: `handle_serial_command()` 118 lines, `setup()` 91 lines
- ❌ **Mixed abstractions**: USB, MIDI, FOC, serial all intertwined
- ❌ **Hard to test**: No module boundaries
- ❌ **Hard to navigate**: 727 lines requires scrolling

**Violates AGENTS.md**:
- "Functions stay small, ideally fit on one monitor page (80x25 to 132x43)"
- `handle_serial_command()` is 118 lines (3-4 screens)
- `setup()` is 91 lines (2-3 screens)

---

## Proposed Architecture

### File Structure (After)

```
src/
  ├── main.cpp                 ~80 lines   (setup + loop only)
  ├── motor_control.cpp        ~120 lines  (FOC integration)
  ├── motor_control.h
  ├── midi_handler.cpp         ~100 lines  (MIDI parser + routing)
  ├── midi_handler.h
  ├── usb_hid.cpp              ~80 lines   (HID setup + reports)
  ├── usb_hid.h
  ├── commander_integration.cpp ~60 lines  (SimpleFOC Commander)
  ├── commander_integration.h
  └── config.h                 219 lines   (unchanged)

include/
  ├── pid_config.h             76 lines    (unchanged)
  └── my_tusb_config.h         93 lines    (unchanged)

lib/                           (NEW - optional libraries)
  └── README.md                SimpleFOC Studio reference

test/
  ├── test_motor_control.py    (NEW - unit tests for motor module)
  ├── test_midi_handler.py     (NEW - MIDI parser tests)
  └── calibrate_pid.py         (existing)

tools/                         (NEW - development tools)
  ├── simplefoc_studio.md      SimpleFOC Studio integration guide
  └── build_helper.sh          Build/upload shortcuts

.gitignore                     (UPDATED - exclude build artifacts)
```

**Total C++ code**: ~1,200 lines across 11 files (modularized)

---

## Module Design

### 1. motor_control.cpp/h (~120 lines)

**Purpose**: SimpleFOC integration, motor initialization, control loop

**Public API**:
```cpp
// motor_control.h
#pragma once
#include <SimpleFOC.h>

extern BLDCMotor* motors[2];
extern float target_angle[2];
extern float current_angle[2];

void motor_init(uint8_t motor_id);
void motor_loop_foc(uint8_t motor_id);
void motor_move(uint8_t motor_id);
void motor_set_target(uint8_t motor_id, float angle);
float motor_get_angle(uint8_t motor_id);
void motor_set_pid_gains(uint8_t motor_id, float p, float i, float d, bool is_velocity);
```

**Responsibilities**:
- ✅ Initialize sensors, drivers, motors
- ✅ Run FOC control loop
- ✅ Apply PID gains
- ✅ Handle motor limits
- ✅ Read current position

**Max function size**: 40 lines

---

### 2. midi_handler.cpp/h (~100 lines)

**Purpose**: USB MIDI input parsing and routing to motor control

**Public API**:
```cpp
// midi_handler.h
#pragma once
#include <stdint.h>

void midi_init();
void midi_process();  // Call in loop() to read USB MIDI packets
void midi_set_profile(uint8_t profile_id);  // Switch CC mappings
```

**Responsibilities**:
- ✅ Read USB MIDI packets (TinyUSB MIDI)
- ✅ Parse MIDI CC messages (state machine)
- ✅ Map CC# to motor targets via config
- ✅ Call motor_set_target() for each CC

**Max function size**: 35 lines

**State Machine**:
```
IDLE → (0x80-0xEF) → WAIT_DATA1 → WAIT_DATA2 → PROCESS → IDLE
```

---

### 3. usb_hid.cpp/h (~80 lines)

**Purpose**: USB HID joystick setup and reporting

**Public API**:
```cpp
// usb_hid.h
#pragma once
#include <stdint.h>

void hid_init();
void hid_update_axis(uint8_t axis_id, uint16_t value);  // 0-1023
void hid_send_report();  // Call at ~100 Hz
```

**Responsibilities**:
- ✅ Initialize USB HID device (TinyUSB)
- ✅ Define HID report descriptor
- ✅ Convert motor angles to joystick values (0-1023)
- ✅ Send HID reports

**Max function size**: 40 lines

---

### 4. commander_integration.cpp/h (~60 lines)

**Purpose**: SimpleFOC Commander protocol for GUI tuning

**Public API**:
```cpp
// commander_integration.h
#pragma once
#include <communication/Commander.h>

void commander_init();
void commander_process();  // Call in loop() to handle serial commands
```

**Responsibilities**:
- ✅ Setup SimpleFOC Commander instance
- ✅ Register motor callbacks (command.motor())
- ✅ Configure monitoring output
- ✅ Process serial commands in loop

**Implementation** (replaces custom protocol):
```cpp
#include "commander_integration.h"
#include "motor_control.h"

Commander command = Commander(Serial);

void onMotor0(char* cmd) { command.motor(motors[0], cmd); }
// void onMotor1(char* cmd) { command.motor(motors[1], cmd); }

void commander_init() {
  motors[0]->useMonitoring(Serial);
  motors[0]->monitor_variables = _MON_TARGET | _MON_ANGLE | _MON_VEL;
  motors[0]->monitor_downsample = 100;
  command.add('M', onMotor0, "motor0");
  command.verbose = VerboseMode::machine_readable;
}

void commander_process() {
  command.run();
  motors[0]->monitor();
}
```

**Max function size**: 20 lines

---

### 5. main.cpp (~80 lines)

**Purpose**: Entry point, orchestration only

**Structure**:
```cpp
#include "motor_control.h"
#include "midi_handler.h"
#include "usb_hid.h"
#include "commander_integration.h"

void setup() {
  Serial.begin(115200);
  
  // Initialize modules in order
  motor_init(0);
  // motor_init(1);  // When motor1 configured
  
  midi_init();
  hid_init();
  commander_init();
  
  Serial.println("System ready");
}

void loop() {
  // FOC control loop (~1 kHz)
  motor_loop_foc(0);
  motor_move(0);
  
  // Input processing
  midi_process();           // Read USB MIDI
  commander_process();      // Read serial commands
  
  // Output updates
  hid_send_report();        // Send joystick state (~100 Hz)
}
```

**Max function size**: 40 lines (setup + loop combined)

---

## SimpleFOC Studio Integration

### Option 1: Reference Link (Recommended)

**Approach**: Document SimpleFOC Studio as external tool, no submodule

**Implementation**:
1. Create `tools/simplefoc_studio.md` with integration guide
2. Update README.md with link to https://studio.simplefoc.com
3. No git submodule (it's a web app)

**Pros**:
- ✅ No repository bloat
- ✅ Always use latest Studio version
- ✅ Web app works immediately

**File**: `tools/simplefoc_studio.md`
```markdown
# SimpleFOC Studio Integration

**Web App**: https://studio.simplefoc.com (recommended)
**Desktop**: https://github.com/JorgeMaker/SimpleFOCStudio/releases

## Quick Start
1. Build and upload firmware with Commander support
2. Open SimpleFOC Studio (web or desktop)
3. Connect to serial port (115200 baud)
4. Motor appears in device tree
5. Adjust PID gains with sliders

## Commands
- Motor 0: Command prefix 'M' (e.g., MAP20.0)
- Motor 1: Command prefix 'N' (when configured)

See: .agentic/tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md
```

---

### Option 2: Git Submodule (Not Recommended)

**Approach**: Add SimpleFOCStudio repo as submodule

**Command**:
```bash
git submodule add https://github.com/JorgeMaker/SimpleFOCStudio.git lib/SimpleFOCStudio
```

**Cons**:
- ❌ Adds 10+ MB to repo
- ❌ Need to update submodule manually
- ❌ Web version is easier to use
- ❌ Not needed for firmware build

**Verdict**: Use Option 1 (reference only)

---

## Repository Cleanup

### .gitignore Updates

**Add to .gitignore**:
```gitignore
# Build artifacts (PlatformIO)
.pio/build/
.pio/libdeps/
*.pio

# Python
.venv/
__pycache__/
*.pyc

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Test outputs
test/logs/
test/*.log
```

### Remove Tracked Build Artifacts

```bash
git rm -r --cached .pio/build/
git rm -r --cached .pio/libdeps/
git rm -r --cached .venv/
```

### Directory Structure Cleanup

**Create missing directories**:
```bash
mkdir -p tools
mkdir -p lib
mkdir -p docs
```

**Move documentation**:
```bash
git mv PID_TUNING_QUICKSTART.md docs/
git mv .agentic/architecture/QUICKSTART.md docs/BUILD_QUICKSTART.md
```

---

## Function Refactoring Guidelines

**Per AGENTS.md**: "Functions stay small, ideally fit on one monitor page (80x25 to 132x43)"

### Size Limits

- **Target**: 25 lines per function
- **Maximum**: 43 lines per function
- **If longer**: Split into helper functions

### Current Violations

| Function | Current Lines | Target | Strategy |
|----------|---------------|--------|----------|
| `handle_serial_command()` | 118 | 25 | **DELETE** (replace with Commander) |
| `setup()` | 91 | 40 | Split into module init calls |
| `handle_motor_limits()` | 56 | 30 | Extract boundary calculation helper |
| `setup_usb_hid()` | 38 | 38 | ✅ OK (just under limit) |
| `process_midi_message()` | 34 | 34 | ✅ OK |

### Refactoring Strategy

**Example**: `handle_motor_limits()` (56 lines → 2 functions)

**Before** (56 lines):
```cpp
void handle_motor_limits(uint8_t motor_id, float& angle) {
  // 56 lines of boundary checking, wrapping, clamping...
}
```

**After** (2 functions, max 30 lines each):
```cpp
// motor_control.cpp
static float clamp_angle(float angle, float min, float max) {
  if (angle < min) return min;
  if (angle > max) return max;
  return angle;
}

static float wrap_endless_angle(float angle) {
  while (angle > TWO_PI) angle -= TWO_PI;
  while (angle < 0) angle += TWO_PI;
  return angle;
}

void motor_set_target(uint8_t motor_id, float angle) {
  if (motor_config[motor_id].is_endless) {
    angle = wrap_endless_angle(angle);
  } else {
    angle = clamp_angle(angle, 
                        motor_config[motor_id].min_angle,
                        motor_config[motor_id].max_angle);
  }
  target_angle[motor_id] = angle;
  motors[motor_id]->target = angle;
}
```

---

## Implementation Steps

### Phase 1: Preparation (1 hour)

**Feature branch**:
```bash
git checkout dev
git pull
git checkout -b feature/modularize-main
```

**Repository cleanup**:
```bash
# Update .gitignore
# Remove build artifacts from git
# Create tools/ and lib/ directories
# Move documentation
git add .
git commit -m "chore: Repository cleanup - ignore build artifacts, organize docs"
```

---

### Phase 2: Extract motor_control Module (2 hours)

**Create files**:
1. `src/motor_control.h` - API declarations
2. `src/motor_control.cpp` - Implementation

**Move from main.cpp**:
- Motor initialization code
- FOC loop functions
- PID gain application
- Motor limit handling

**Test**:
```bash
platformio run -e pico_1motor_endless
# Should compile without errors
```

**Commit**:
```bash
git add src/motor_control.*
git commit -m "refactor: Extract motor_control module from main.cpp"
```

---

### Phase 3: Extract midi_handler Module (2 hours)

**Create files**:
1. `src/midi_handler.h` - API declarations
2. `src/midi_handler.cpp` - Implementation

**Move from main.cpp**:
- MIDI state machine (`handle_midi_byte()`)
- MIDI message processing
- USB MIDI reading

**Test**:
```bash
platformio run -e pico_1motor_endless
# Should compile
python3 test/debug_midi.py
# Should receive MIDI commands
```

**Commit**:
```bash
git add src/midi_handler.*
git commit -m "refactor: Extract midi_handler module from main.cpp"
```

---

### Phase 4: Extract usb_hid Module (1.5 hours)

**Create files**:
1. `src/usb_hid.h` - API declarations
2. `src/usb_hid.cpp` - Implementation

**Move from main.cpp**:
- HID initialization
- HID report descriptor
- Report sending

**Test**:
```bash
platformio run -e pico_1motor_endless --target upload
python3 test/debug_joystick.py
# Should see joystick values updating
```

**Commit**:
```bash
git add src/usb_hid.*
git commit -m "refactor: Extract usb_hid module from main.cpp"
```

---

### Phase 5: Add commander_integration Module (2 hours)

**Create files**:
1. `src/commander_integration.h` - API declarations
2. `src/commander_integration.cpp` - SimpleFOC Commander integration

**Remove from main.cpp**:
- `handle_serial_command()` (118 lines)
- `apply_pid_gains()`
- `print_current_gains()`
- `PIDGains` struct
- All custom serial protocol code

**Add SimpleFOC Commander**:
- Implement as per SIMPLEFOC_STUDIO_PLAN.md
- Use built-in `command.motor()` callbacks

**Update Python tools**:
- Modify `test/calibrate_pid.py` to send Commander format
- Update monitoring parser for tab-separated values

**Test**:
```bash
# Firmware
platformio run -e pico_1motor_endless --target upload

# SimpleFOC Studio
# Open https://studio.simplefoc.com
# Connect to serial port
# Verify motor appears and responds to commands

# Python tools
python3 test/calibrate_pid.py --motor 0 --step-only
# Should work with Commander protocol
```

**Commit**:
```bash
git add src/commander_integration.*
git commit -m "feat: Add SimpleFOC Commander integration, remove custom protocol (243 lines)"
```

---

### Phase 6: Simplify main.cpp (1 hour)

**Reduce main.cpp to orchestration**:
- Include module headers
- Call init functions in setup()
- Call process functions in loop()

**Target**: ~80 lines total

**Test full system**:
```bash
platformio run -e pico_1motor_endless --target upload
python3 test/test_suite_automated.py
# All tests should pass
```

**Commit**:
```bash
git add src/main.cpp
git commit -m "refactor: Simplify main.cpp to orchestration only (727 → ~80 lines)"
```

---

### Phase 7: Add SimpleFOC Studio Documentation (1 hour)

**Create**:
1. `tools/simplefoc_studio.md` - Integration guide
2. Update README.md with Studio reference
3. Update `.agentic/` documentation

**Commit**:
```bash
git add tools/ README.md .agentic/
git commit -m "docs: Add SimpleFOC Studio integration guide"
```

---

### Phase 8: Function Size Compliance (1.5 hours)

**Refactor remaining large functions**:
- Extract helpers from `setup()` if needed
- Split any functions >43 lines

**Verify compliance**:
```bash
# Check function sizes
grep -n "^void\|^static" src/*.cpp | while read line; do
  # Count lines until next function
  # Flag any >43 lines
done
```

**Commit**:
```bash
git add src/
git commit -m "refactor: Ensure all functions ≤43 lines per AGENTS.md"
```

---

### Phase 9: Testing & Integration (2 hours)

**Run full test suite**:
```bash
# Automated tests
python3 test/test_suite_automated.py

# Manual tests
python3 test/debug_joystick.py    # USB HID
python3 test/debug_midi.py        # MIDI input
python3 test/calibrate_pid.py --motor 0 --step-only  # Quality eval

# SimpleFOC Studio
# Test GUI tuning workflow
```

**Create module unit tests** (optional but recommended):
```python
# test/test_motor_control.py
def test_motor_initialization():
    """Verify motor initializes correctly"""
    
def test_angle_clamping():
    """Verify motor limits enforced"""

# test/test_midi_handler.py  
def test_midi_cc_parsing():
    """Verify MIDI CC messages parsed correctly"""
```

**Commit**:
```bash
git add test/
git commit -m "test: Add module-level unit tests"
```

---

### Phase 10: Merge to dev (0.5 hours)

**Review changes**:
```bash
git log --oneline feature/modularize-main
# Should show ~10 clean commits
```

**Merge**:
```bash
git checkout dev
git merge feature/modularize-main --no-ff
git push origin dev
```

**Tag**:
```bash
git tag -a v0.3.0 -m "Modularized architecture + SimpleFOC Commander"
git push origin v0.3.0
```

---

## Validation Checklist

### Code Quality
- [ ] All functions ≤43 lines
- [ ] No function >100 lines
- [ ] Clear module boundaries (motor, MIDI, HID, Commander)
- [ ] No code duplication

### Functionality
- [ ] Motors move in response to MIDI
- [ ] USB HID joystick reports correctly
- [ ] SimpleFOC Studio connects and controls motor
- [ ] Python tools work with Commander protocol
- [ ] Quality evaluation still functional

### Testing
- [ ] All existing tests pass
- [ ] SimpleFOC Studio tested manually
- [ ] Module unit tests added (optional)

### Documentation
- [ ] README.md updated
- [ ] SimpleFOC Studio guide created
- [ ] .agentic/ documentation updated
- [ ] Code comments accurate

### Repository
- [ ] Build artifacts not tracked
- [ ] .gitignore comprehensive
- [ ] Directory structure clean
- [ ] All commits follow conventional format

---

## Estimated Effort Summary

| Phase | Task | Hours |
|-------|------|-------|
| 1 | Preparation & cleanup | 1.0 |
| 2 | Extract motor_control | 2.0 |
| 3 | Extract midi_handler | 2.0 |
| 4 | Extract usb_hid | 1.5 |
| 5 | Add commander_integration | 2.0 |
| 6 | Simplify main.cpp | 1.0 |
| 7 | SimpleFOC Studio docs | 1.0 |
| 8 | Function size compliance | 1.5 |
| 9 | Testing & integration | 2.0 |
| 10 | Merge to dev | 0.5 |
| **Total** | | **14.5 hours** |

**Buffer**: +1.5 hours for unexpected issues

**Total with buffer**: 16 hours

---

## Success Criteria

**Code Metrics**:
- ✅ main.cpp: 727 lines → ~80 lines (90% reduction)
- ✅ Modules: 4 new files (~360 lines total)
- ✅ Largest function: ≤43 lines
- ✅ Average function: ~25 lines

**Functionality**:
- ✅ All existing features work
- ✅ SimpleFOC Studio integration functional
- ✅ Test suite passes
- ✅ No regressions

**Maintainability**:
- ✅ Clear module boundaries
- ✅ Functions fit on one screen
- ✅ Easy to navigate codebase
- ✅ New features isolated to specific modules

---

## Risks & Mitigation

### Risk 1: Breaking Existing Functionality

**Mitigation**:
- Incremental refactoring (one module at a time)
- Run tests after each phase
- Keep feature branch until fully validated

### Risk 2: Module Interdependencies

**Issue**: Modules might create circular dependencies

**Mitigation**:
- Design clean APIs first
- Use forward declarations
- Keep motor_control as base (no dependencies on other modules)

### Risk 3: SimpleFOC Commander Integration

**Issue**: Commander might not work as expected

**Mitigation**:
- Test Commander early (Phase 5)
- Keep custom protocol code until Commander validated
- Fallback: Revert Commander, keep modular structure

### Risk 4: Test Breakage

**Issue**: Python tools might break with new protocol

**Mitigation**:
- Update Python tools in same commit as firmware changes
- Test with both old and new protocol during transition
- Keep quality evaluation system working throughout

---

## Future Enhancements

**After modularization**:

1. **Motor 1 Support**
   - Add motor1 configuration to motor_control module
   - Extend MIDI handler for motor1 mappings
   - Test dual-motor HID output

2. **EEPROM Configuration**
   - Save tuned PID gains to EEPROM
   - Load on startup
   - Commander command to persist

3. **Error Handling**
   - Add error codes for each module
   - LED status indicators
   - Error recovery strategies

4. **Performance Monitoring**
   - FOC loop timing (should be <1ms)
   - HID report rate (target 100 Hz)
   - MIDI input latency

---

## References

- **AGENTS.md**: Function size requirements (25-43 lines)
- **SimpleFOC Commander**: https://docs.simplefoc.com/commander_interface
- **SimpleFOC Studio Plan**: `.agentic/tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md`
- **Current Architecture**: `.agentic/architecture/PLANNING.md`

---

## Decision Log

**Feb 23, 2026**: Modularization approach chosen
- **Rationale**: 727-line main.cpp violates AGENTS.md (functions too large)
- **Strategy**: Extract 4 modules (motor, MIDI, HID, Commander)
- **Benefit**: Functions ≤43 lines, clear boundaries, easier testing

**Feb 23, 2026**: SimpleFOC Studio reference (not submodule)
- **Rationale**: Web app, no need for git submodule
- **Implementation**: Documentation link only
- **Benefit**: No repo bloat, always latest version

**Feb 23, 2026**: Commander integration in modularization
- **Rationale**: Combine two refactorings (avoid double work)
- **Benefit**: Remove 243 lines of custom protocol during modularization
- **Risk**: More changes at once, mitigated by incremental phases
