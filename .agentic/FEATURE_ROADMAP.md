# Feature Development Roadmap

**Date**: February 27, 2026  
**Status**: Post-merge, ready for enhancement  
**Team Level**: Autonomous agent development facilitation  

## Current Architecture Status

✅ **Merged**:
- Modular architecture (motor_control, midi_handler, usb_hid, commander_integration)
- DTR bootloader reentry support
- CI/CD automation (6 workflows + headless testing)
- Knowledge base documentation
- Build: 4.0% flash, 4.4% RAM on pico_1motor_endless

✅ **Working**:
- USB HID joystick output
- MIDI CC input parsing
- SimpleFOC FOC loop integration
- PID tuning via SimpleFOC Commander CLI
- Dual motor conditional support (code structure ready)

⚠️ **Known Limitations**:
- Dual motor (pico_2motor_limited) build fails on Windows due to MAX_PATH
- Sensor1 TODO for dual motor configuration
- Single axis currently active per motor
- No comprehensive error recovery

## Development Priorities

### Phase 1: Safety & Robustness (Week 1, 16 hours)
**Goal**: Production-ready error handling and diagnostics

#### 1.1 Motor Initialization Safety (**4 hours**)
**What**:
- Add voltage validation checks
- Verify sensor readiness before FOC
- Add initialization timeout detection
- Better error messages to serial

**Files**:
- `src/motor_control.cpp`: Enhance `init_motor()`
- `src/motor_control.h`: Add error status return type

**Tests**:
- `test/test_motor_init.py`: Verify init sequences
- `test/test_hid_exercise.py`: Exercise after initialization

**Success Criteria**:
- Init fails gracefully with diagnostic message
- Misaligned sensors detected
- Voltage limits enforced

#### 1.2 Telemetry & Logging (**4 hours**)
**What**:
- Add debug output levels (none, error, debug, verbose)
- Motor status messages (angle, voltage, errors)
- Performance metrics (loop timing, buffer usage)
- CDC serial logging with compile-time control

**Files**:
- `src/log.h`: Logging macros
- `src/motor_control.cpp`: Log at key points
- `src/midi_handler.cpp`: Log CC messages
- `config.h`: LOG_LEVEL define

**Implementation**:
```cpp
#define LOG_LEVEL LOG_DEBUG  // Change to LOG_ERROR for production

#define LOG_ERROR(fmt, ...) if (LOG_LEVEL >= LOG_ERROR) { Serial.printf("[ERROR] " fmt "\n", __VA_ARGS__); }
#define LOG_INFO(fmt, ...)  if (LOG_LEVEL >= LOG_INFO)  { Serial.printf("[INFO] " fmt "\n", __VA_ARGS__); }
#define LOG_DEBUG(fmt, ...) if (LOG_LEVEL >= LOG_DEBUG) { Serial.printf("[DEBUG] " fmt "\n", __VA_ARGS__); }
```

**Tests**:
- `test/test_logging.py`: Capture and verify log output
- Monitor serial during operation

#### 1.3 Error Recovery (**4 hours**)
**What**:
- Watchdog for FOC loop hangs
- Motor stall detection
- Graceful degradation (limp mode)
- State machine for motor health

**Files**:
- `src/motor_control.cpp`: Add state tracking
- New `src/diagnostics.h`: Health monitoring
- `src/main.cpp`: Add watchdog kick

**Enum**:
```cpp
enum MotorState {
  UNINITIALIZED,
  IDLE,
  RUNNING,
  ERROR,
  STALLED
};
```

**Success Criteria**:
- Stalled motor detected within 100ms
- System recovers with retry
- Error logged with timestamp
- Prevents motor damage via overcurrent

#### 1.4 Configuration Validation (**4 hours**)
**What**:
- Compile-time configuration checks
- MIDI CC map uniqueness validation
- Motor speed limit consistency
- Angle range validation

**Files**:
- New `src/config_check.cpp`: Static assertions
- Template-based validation
- Example: `static_assert(NUM_MOTORS <= 2, "Max 2 motors");`

**Validations**:
```cpp
// All MIDI CCs must be unique (no conflicts)
// Motor profiles must have min < max
// Voltage limits must be within motor specs (0.5V - 12V)
// All motor IDs referenced in axes must exist
```

---

### Phase 2: Feature Expansion (Week 2, 20 hours)
**Goal**: Support diverse hardware and use cases

#### 2.1 Dual Motor Full Support (**6 hours**)
**Current**: Code structure ready, sensor test framework exists  
**Target**: Working pico_2motor_limited with independent tuning

**What**:
- Add sensor1 I2C address selection
- Separate PID profiles for motor1
- Dual motor initialization coordination
- Test on hardware when available

**Files**:
- `src/config.h`: I2C address defines
- `src/motor_control.cpp`: Motor1 init flow
- `include/pid_config.h`: MOTOR1_PID_* defines
- `test/test_dual_motor.py`: Coordination tests

**I2C Addressing**:
```cpp
#define AS5600_I2C_ADDR_0  0x36
#define AS5600_I2C_ADDR_1  0x37  // Motor 1 on alternate address pin

// Then:
sensor0 = MagneticSensorI2C(AS5600_I2C_ADDR_0);
#if NUM_MOTORS > 1
sensor1 = MagneticSensorI2C(AS5600_I2C_ADDR_1);
#endif
```

#### 2.2 Advanced Axis Mapping (**5 hours**)
**Current**: One axis per motor hardcoded in config  
**Target**: Dynamic axis assignment at runtime

**What**:
- Multiple axes per motor (e.g., throttle + flaps on same motor)
- Priority-based axis resolution (last CC wins)
- Axis enable/disable via MIDI
- Per-axis scaling factors

**Implementation**:
```cpp
// Let one motor handle multiple axes
// When M0 receives CC7 (throttle), move to angle_min-angle_max
// When M0 receives CC11 (flaps), move to different range on same axis
// Current angle = weighted blend or last-command-wins
```

#### 2.3 Velocity Control (**5 hours**)
**Current**: Direct angle commands  
**Target**: Velocity ramping with acceleration limits

**What**:
- Smooth acceleration profiles
- User-configurable ramp time
- Prevent jerky movements
- Torque smoothing for realistic feel

**Files**:
- New `src/velocity_control.h`: Ramping profiles
- `src/motor_control.cpp`: Integrate ramping
- `config.h`: Ramp time defines

**Profile Types**:
```cpp
enum RampProfile {
  INSTANT,        // No ramping (current behavior)
  LINEAR,         // Constant acceleration
  EXPONENTIAL,    // Smooth S-curve (preferred)
  CUSTOM          // User-defined function
};

#define RAMP_TIME_MS 500  // Move from 0 to max in 500ms
```

#### 2.4 Failsafe & Automation (**4 hours**)
**What**:
- Return-to-neutral on loss of connection
- Auto-disconnect detection
- Timeout-based recovery
- Safe shutdown sequence

**Files**:
- New `src/failsafe.h`
- `src/main.cpp`: Failsafe check in loop

---

### Phase 3: Flight Simulator Integration (Week 3, 12 hours)
**Goal**: Full MSFS support (Airbus A320 primary target)

#### 3.1 A320 Profile Tuning (**6 hours**)
**Current**: Template axes defined  
**Target**: Tuned for MSFS A320 FBW Mod

**Axes Map**:
- CC7 (Volume) → Throttle (0-180°)
- CC11 (Expression) → Flaps (5-25 discrete)
- CC64 (Sustain) → Trim (±360°)
- CC32 (Bank Select) → Spoilers (0-180°)
- CC65 (Portamento) → Landing Gear (0-180°)

**Each axis**:
- Deadzone configuration
- Curve shaping (linear, exponential, S-curve)
- Reverse option (e.g., flaps reverse)
- Scaling to 8-bit MIDI (0-127)

**Files**:
- `src/config.h`: A320_AXES array
- `test/test_a320_mapping.py`: Verify CC-to-angle
- SimpleFOC Studio profiles exported

#### 3.2 Profile Switching (**3 hours**)
**What**:
- Switch between A320, Boeing, Helicopter configurations
- MIDI Program Change for profile selection
- Flash storage of profiles (EEPROM)
- Active profile display on HID

#### 3.3 Joystick Calibration UI (**3 hours**)
**What**:
- Self-test on startup
- Min/max discovery per axis
- Non-linearity compensation
- Export calibration to config

---

### Phase 4: Tools & Testing (Ongoing)
**Goal**: Developer experience and reliability

#### 4.1 Python Test Suite Enhancements
**Current**: Basic HID/MIDI tests  
**Target**: Comprehensive test coverage

**New Tests**:
- `test/test_motor_tracking.py`: Verify motor follows CC commands
- `test/test_consistency.py`: Same CC always produces same angle
- `test/test_limits.py`: Boundaries enforced
- `test/test_performance.py`: Loop timing < 1ms
- `test/test_endurance.py`: 1000 CC messages without error

#### 4.2 SimpleFOC Studio Integration Guide
**Current**: Basic tuning support  
**Target**: Documented tuning workflow

**Create**:
- `tools/simplefoc_studio.md`: Studio connection guide
- Pre-configured motor profiles
- Tuning checklist for A320 hardware
- P/I/D gain recommendations

#### 4.3 Hardware Simulation Tools
**Current**: Minimal simulator  
**Target**: Full controller emulation

**Expand**:
- USB HID report validation
- MIDI sequence playback
- Load testing (burst CC messages)
- Timing analysis tools

---

## Development Workflow

### Branch Strategy
```
dev (main development)
├─ feature/motor-safety-checks (1.1)
├─ feature/telemetry-logging (1.2)
├─ feature/error-recovery (1.3)
├─ feature/config-validation (1.4)
├─ feature/dual-motor-support (2.1)
├─ feature/axis-mapping (2.2)
├─ feature/velocity-ramping (2.3)
├─ feature/failsafe-automation (2.4)
├─ feature/a320-tuning (3.1)
├─ feature/profile-switching (3.2)
└─ feature/joystick-calibration-ui (3.3)
```

### Testing Gates
- ✅ Builds with `pio run -e pico_1motor_endless`
- ✅ Existing tests pass (`test/test_suite.py`)
- ✅ No regression in firmware size (< 5%)
- ✅ Functionality verified on hardware (if available)

### Merge Criteria
1. Code review: ✅ Clean code, good comments
2. Tests: ✅ 80%+ coverage of new code
3. Performance: ✅ Loop timing maintained
4. Documentation: ✅ Docstrings and examples

---

## Success Metrics

### Reliability (Target: 99.9%)
- **MTBF**: Mean Time Between Failures > 100 hours
- **MTTR**: Recovery time < 100ms
- **Error rate**: < 0.1% of commands fail

### Performance (Target: Real-time)
- **Loop time**: < 1ms (FOC at 1kHz+)
- **Latency**: CC → Motor movement < 5ms
- **Memory**: < 20% of available RAM

### User Experience
- **Setup time**: < 5 minutes (plug, calibrate, fly)
- **Accuracy**: ±2° angle tracking
- **Smoothness**: No jerkiness or oscillation

---

## Quick Links
- [Architecture Overview](.agentic/architecture/)
- [Hardware Configuration](HARDWARE_SETUP.md)
- [CI/CD Guidance](.github/workflows/README.md)
- [Known Issues](.agentic/sessions/2026-02-27_merge_completion_report.md)

---

**Next Update**: Post-Phase 1 completion (estimated March 5, 2026)
