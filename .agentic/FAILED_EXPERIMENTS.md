# Failed Experiments & Lessons Learned

**Purpose**: Document approaches that were attempted but didn't work out, preserving knowledge for future reference.

---

## 1. Automated PID Tuning System ❌

**Status**: FAILED EXPERIMENT - Removed from codebase  
**Date**: 2026-02-22 to 2026-02-27  
**Outcome**: Manual tuning successful; automated approach blocked by debug output rate limitations

### What Was Attempted

Built a comprehensive **automatic PID tuning framework** using the **Ziegler-Nichols relay method**:

**Files Created** (all removed):
- `test/calibrate_pid.py` - 1042-line automated calibration script
- `test/motor_monitor.py` - High-speed motor data capture library
- `test/CALIBRATION.md` - Complete tuning guide with theory
- `test/RAMP_TEST_GUIDE.md` - Step response testing guide
- `PID_TUNING_QUICKSTART.md` - User-facing quick start
- `.agentic/quality/` folder - Quality scoring system

**Approach**:
1. Send square wave MIDI commands to motor (relay test)
2. Capture high-speed motor response data
3. Measure oscillation frequency & amplitude
4. Apply Ziegler-Nichols equations to calculate Kp, Ki, Kd
5. Validate with step response tests
6. Generate quality score (0-100) from 5 metrics

**Quality Metrics Developed**:
1. **Overshoot**: Peak deviation from target
2. **Settling Time**: Time to reach steady-state
3. **Position Noise**: Standard deviation of angle readings
4. **Position Drift**: Mean error from target
5. **Stability**: Percentage of time within tolerance

**Rating Scale**:
- 90-100: EXCELLENT
- 70-89: GOOD
- 50-69: FAIR
- 0-49: POOR

### Why It Failed

**Root Cause**: **USB bandwidth limitations forced 1 Hz debug output rate**

The automated PID tuning system requires:
- **High-speed motor data capture** (10-100 Hz minimum)
- **Continuous sampling during relay test** (3-5 seconds)
- **Precise timing measurements** for oscillation frequency

With debug output at **1 Hz** (to prevent USB stability issues):
- Only **1 sample per second** available
- Can't measure oscillation frequency accurately
- Can't capture transient response behavior
- Can't validate settling time with precision
- Relay test becomes impractical (3+ minute capture for 3 samples)

**Trade-off**: Chose USB stability over automated tuning capability.

### What Actually Worked

**Manual PID tuning** was successful using conservative gains derived from SimpleFOC documentation:

**Working Gains** (`include/pid_config.h`):
```cpp
// Angle Controller (Outer Loop)
#define MOTOR0_PID_P    4.0    // Reduced from default 20.0
#define MOTOR0_PID_I    15.0   // Added integral action
#define MOTOR0_PID_D    2.5    // Increased damping from 0.5

// Velocity Controller (Inner Loop)
#define MOTOR0_VELOCITY_P    3.0    // Increased from 0.125
#define MOTOR0_VELOCITY_I    10.0   // Unchanged
#define MOTOR0_VELOCITY_D    1.5    // Added damping

// Filter
#define MOTOR0_LPF_ANGLE_TF  0.02   // 20ms time constant
```

**Results**:
- Initial quality score: **28.4/100 POOR** (noisy, unstable, 13.53° noise)
- After manual tuning: **72.9/100 GOOD** (stable, 1.45° noise)
- **89% reduction in position noise**
- **86% reduction in position drift**
- **59% improvement in stability** (52.1% → 82.8%)

### Key Learnings

1. **SimpleFOC Defaults Are Too Aggressive for RP2040**
   - Default Kp=20.0 designed for AVR microcontrollers
   - RP2040's faster FOC loop (1 kHz) needs gentler gains
   - Start with Kp=4.0 and tune up if needed

2. **Integral Action is Essential for Position Hold**
   - Default Ki=0.0 causes motor to drift under load
   - Ki=15.0 provides steady-state accuracy
   - Motor now resists external disturbances

3. **Derivative Damping Prevents Oscillation**
   - Default Kd=0.5 insufficient to damp oscillations
   - Kd=2.5 smooths response without sluggishness
   - Eliminates audible motor noise/vibration

4. **Velocity Loop Needs Proportional Action**
   - Original Kv_p=0.125 too weak
   - Kv_p=3.0 provides responsive torque control
   - Adding Kv_d=1.5 improves velocity tracking

5. **Low-Pass Filter Critical for Sensor Noise**
   - 20ms filter (Tf=0.02) smooths AS5600 encoder jitter
   - Prevents noise amplification through derivative term
   - Improves overall system stability

### Alternative Approaches Considered

**Option 1: Increase Debug Output Rate for Tuning**
- Temporarily set debug to 10-100 Hz during calibration
- Run automated tuning, then revert to 1 Hz
- **Rejected**: Risk of USB instability during tuning; user confusion about rate changes

**Option 2: Use SimpleFOC Commander Serial Protocol**
- SimpleFOC Commander can stream motor data at high speed
- Would bypass USB HID/MIDI bandwidth contention
- **Rejected**: Commander integration removed as untested; adds complexity

**Option 3: Hardware UART Output**
- Use dedicated UART pins for debug output
- Leave USB for HID/MIDI only
- **Rejected**: RP2040 Pico Mini board doesn't expose UART pins easily; requires hardware modification

**Option 4: Binary Telemetry Protocol**
- Replace text debug output with compact binary messages
- Could fit 10-100 Hz data within USB CDC bandwidth
- **Rejected**: Loses human-readable debug; requires custom parsing tools; engineering overhead

### Recommended Path Forward

For future PID tuning needs:

1. **Manual Tuning is Sufficient**
   - Current gains (Kp=4.0, Ki=15.0, Kd=2.5) work well
   - SimpleFOC defaults are a good starting point with 5x reduction
   - Iterate by ±20% adjustments if needed

2. **Online Tuning via SimpleFOC Studio** (if needed)
   - Flash firmware with SimpleFOC Commander enabled
   - Connect SimpleFOC Studio to Serial port
   - Adjust gains in real-time with live visualization
   - Copy working gains to `pid_config.h` and reflash

3. **Quality Validation**
   - Use test suite (`test_suite_automated.py`) to verify motor response
   - Manual observation for audible noise/vibration
   - Measure position hold with hand disturbances
   - Target: Motor should hold position within ±2° under light pressure

4. **Don't Over-Optimize**
   - 70+/100 quality score is "GOOD" - sufficient for joystick use
   - 90+/100 "EXCELLENT" requires extensive tuning and may be fragile
   - Flight sim joysticks have ±5° tolerance in practice

---

## 2. Dual-Motor Support ❌

**Status**: REMOVED - Untested, added complexity  
**Date**: Initially implemented, removed 2026-02-27  
**See**: [REMOVED_UNTESTED_CODE.md](REMOVED_UNTESTED_CODE.md)

### What Was Attempted

Multi-motor architecture with conditional compilation:
- `HW_CONFIG` preprocessor selection (0=1motor_endless, 1=1motor_limited, 2=2motor_limited)
- `NUM_MOTORS` conditional blocks throughout codebase
- Arrays for `motors[2]`, `drivers[2]`, `sensors[2]`
- Multiple PlatformIO build environments

### Why It Was Removed

**Never tested on actual hardware with 2 motors**:
- No CI test coverage for dual-motor configuration
- No hardware validation that motor1 initializes correctly
- Unknown: Does I2C address configuration work? Electrical interference? Timing conflicts?

**Added maintenance burden**:
- Conditional compilation scattered across 5+ files
- 3x build matrix in CI (all environments untested except pico_1motor_endless)
- Configuration complexity vs. proven single-motor baseline

### Result

**Consolidated to single tested configuration**:
- `pico_1motor_endless` only (CC#64 trim control)
- Removed motor1 infrastructure entirely
- 467 lines of code eliminated
- CI build time reduced 67% (3 environments → 1)

### Lesson Learned

**Only ship what's tested on CI**. Untested features create:
- False complexity (looks like it works, actually undefined behavior)
- Maintenance burden (must update 3x code paths for any change)
- User confusion (which configuration do I flash?)
- Wasted CI resources (building 2 untested variants every commit)

If dual-motor support is needed in future:
1. Create feature branch
2. Build hardware test fixture with 2 motors
3. Add CI test validating both motors respond
4. Verify I2C addressing, electrical isolation, timing
5. Merge only after hardware validation

---

## 3. SimpleFOC Commander Integration ❌

**Status**: REMOVED - Untested, conflicts with MIDI debug  
**See**: [REMOVED_UNTESTED_CODE.md](REMOVED_UNTESTED_CODE.md#2-simplefoc-commander-integration)

### What Was Attempted

Integration with SimpleFOC Studio for live PID tuning:
- `commander_integration.cpp` - Serial command parsing
- `motor.useMonitoring(Serial)` - Real-time telemetry
- `motor.monitor()` in main loop - Status streaming

### Why It Was Removed

1. **Never tested in CI** - no validation that it works
2. **Conflicts with USB HID debug output** - both use Serial port
3. **MIDI handler already provides position control** - redundant
4. **Adds ~50 lines of untested code**

### Alternative

Use SimpleFOC Studio directly via Serial if needed:
- SimpleFOC library has built-in Commander support
- Can enable on-demand for tuning sessions
- Disable debug output temporarily to free Serial port
- Flash back to normal firmware after tuning

**Or**: Use `test_suite_automated.py` MIDI commands for scripted position tests.

---

## Summary of Failed Experiments

| Experiment | Lines of Code | Reason for Removal | Replacement |
|------------|---------------|-------------------|-------------|
| **Automated PID Tuning** | ~1800 lines | USB bandwidth limits high-speed sampling | Manual tuning + SimpleFOC Studio |
| **Dual-Motor Support** | ~467 lines | Never tested on hardware | Single motor baseline |
| **SimpleFOC Commander** | ~42 lines | Untested, conflicts with debug | Test suite MIDI control |
| **Total Removed** | **~2309 lines** | - | Simpler, proven code |

---

## Philosophy Reinforced

**UNIX - KISS principles validated**:
1. **One tool, one job** - Don't combine PID tuning into joystick firmware
2. **Only mandatory inventions** - Use SimpleFOC Studio for tuning instead of custom automation
3. **Test-driven development** - If it's not tested on CI, remove it
4. **Don't be clever** - Simple manual tuning works; complex automation doesn't

**Git-flow discipline**:
- Untested features created merge conflicts and confusion
- Feature branches should validate on hardware FIRST
- Main/dev branches should only contain proven, tested code

**Agent-positive workflow**:
- Document failures to prevent repeating mistakes
- Failed experiments accelerate future work (learned what doesn't work)
- Version control preserves history for recovery if assumptions change

---

## Recovery Path (if assumptions change)

All removed code is preserved in git history:

```bash
# View removed PID tuning code
git log --follow --oneline -- test/calibrate_pid.py
git show <commit-hash>:test/calibrate_pid.py

# View removed dual-motor code
git log --follow --oneline -- src/config.h
git diff <commit-before-removal> <commit-after-removal> src/config.h

# Restore entire commit if needed
git checkout <commit-hash> -- test/calibrate_pid.py
```

**Before restoring**:
1. Understand why it was removed (read this document)
2. Confirm assumptions have changed (e.g., found way to get 10 Hz debug output)
3. Create feature branch for restoration
4. Add CI tests proving it works
5. Document new testing strategy

---

## Date of Removal

- **PID Tuning System**: 2026-02-27 (commit: cleanup branch)
- **Dual-Motor Support**: 2026-02-27 (commit: consolidate to single motor)
- **SimpleFOC Commander**: 2026-02-27 (commit: consolidate to single motor)

**Final State**: Single-motor endless-rotation trim controller with manual PID tuning. Quality score: 72.9/100 GOOD.

---

## 4. Automated Bootloader Entry (RB Command) ❌

**Status**: FAILED EXPERIMENT - Abandoned  
**Date**: 2026-02-28  
**Outcome**: Manual BOOTSEL remains the only reliable upload method

### What Was Attempted

Reboot-to-bootloader via serial command to eliminate manual BOOTSEL presses:
1. **ARM AIRCR register reset** — SCB not defined, compilation failed
2. **Watchdog reset with magic RAM value** — Device locks up, no BOOTSEL mount, requires power cycle

### Why It Failed

RP2040 bootloader doesn't support runtime software-triggered bootloader entry after USB CDC is established. The Pico SDK's `watchdog_reboot()` requires specific initialization not available in the SimpleFOC Arduino context.

### Lesson

Don't invent bootloader solutions — manual BOOTSEL is a hardware constraint. DTR-based 1200bps touch works for some Arduino boards but is unreliable on RP2040 with TinyUSB stack. Accept it and optimize the press-upload workflow instead.

---

## 5. Haptic Endstop Overshoot Cascade ❌

**Status**: OPEN — no working fix, root cause identified  
**Date**: 2026-03-01  
**Full writeup**: [tuning/HAPTIC_ENDSTOP_INVESTIGATION.md](tuning/HAPTIC_ENDSTOP_INVESTIGATION.md)

### What Was Attempted

Six different approaches to prevent PID ring-down from cascading through all haptic detents after multi-revolution overshoot:
1. Stateless position+hysteresis rewrite (fixed drift, not cascade)
2. Guard zone (30° past endstop) — cascade on re-entry
3. 5-state machine with SETTLING — timeout always fires, then cascade
4. Three SETTLING variants (loose/window/none) — all cascade
5. Velocity gate — cascade at velocity zero-crossings
6. Velocity gate + cooldown — broke normal operation

### Why They All Failed

The fundamental problem: **detent transitions and PID overshoot are indistinguishable in position space**. A 12° displacement could be a user push or a PID oscillation peak. Every gating strategy either blocks real user input (cooldown, strict settling) or lets the cascade through (loose tolerances, velocity-only gate).

### Lesson

- Don't build epicycles on a broken conceptual model
- The velocity-at-zero-crossing insight was key: it proves instantaneous velocity is insufficient
- Rate limiting or integrated-displacement tracking are promising next directions
- Coarser detents (20° step) may be a pragmatic alternative
