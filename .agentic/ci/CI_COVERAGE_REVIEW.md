# CI Test Coverage Review vs. Stated Purpose

**Reviewed:** 2026-02-27  
**Scope:** GitHub Actions workflows + test_suite_automated.py  
**Status:** ⚠️ GAPS FOUND - Tests do not comprehensively validate stated purpose

---

## Executive Summary

The CI pipeline runs tests but **has significant coverage gaps**. Critical features from PURPOSE.md are either untested or only partially tested:

| Feature | Purpose Status | CI Test Status | Issue |
|---------|---------|---------|---------|
| Motor control (single axis) | ✅ Primary | ⚠️ Partial | Only CC#64 tested, no multi-axis validation |
| USB HID output | ✅ Primary | ✅ Tested | Joystick scaling verified (0-1023 range) |
| MIDI input | ⏳ Primary | ⚠️ Partial | Only single CC command, no protocol validation |
| **Dual-axis support** | ⏳ Primary | ❌ **NOT TESTED** | No multi-motor CI test |
| **PID tuning** | ✅ Primary | ❌ **NOT TESTED** | calibrate_pid.py exists but not run in CI |
| Motor limits | ⚠️ Implicit | ❌ **NOT TESTED** | Limited motors never verify min/max |
| **SimpleFOC Commander** | Mentioned in purpose | ❌ **NOT TESTED** | No integration testing |
| Bootloader reentry | ⚠️ Nice-to-have | ✅ Manual acceptable | Not automated (acceptable per guidelines) |
| Code quality | Secondary | ✅ Tested | Function size check (43-line limit) |
| Compilation | Secondary | ✅ Tested | 3 environment matrix build |
| Headless testing | Secondary | ✅ Tested | pytest runs simulator tests |

---

## Current CI Pipeline

### 1. Code Quality Workflow (`code-quality.yml`)
**What it does:**
- Checks function sizes comply with AGENTS.md (≤43 lines)
- Compiles firmware for `pico_1motor_endless`

**Gaps:**
- Only builds single environment (should test all 3)
- No static analysis beyond function size
- No unused-code detection

---

### 2. Headless Test Workflow (`headless-test.yml`)
**What it does:**
- Runs pytest on simulator
- Tests: `test_sim_device.py` (3 tests)
  - `test_limited_axis_scaling()`
  - `test_reversed_axis_scaling()`
  - `test_endless_axis_delta()`

**Coverage:**
- ✅ Validates simulator axis mapping (0-1023 range)
- ❌ Does NOT test actual hardware
- ❌ Does NOT test MIDI protocol
- ❌ Does NOT validate multi-axis scenarios

---

### 3. Build Workflow (`build.yml`)
**What it does:**
- Matrix build all 3 environments:
  - `pico_1motor_endless`
  - `pico_1motor_limited`
  - `pico_2motor_limited` ← **Dual motor config!**
- Checks firmware size (warning at >1800KB)
- Uploads artifacts to GitHub

**Coverage:**
- ✅ Compiles all 3 hardware configs
- ❌ Does not verify they work correctly on hardware
- ❌ Missing: Upload the hardware-test.yml to run on CI runner

---

### 4. Hardware Test Workflow (`hardware-test.yml`)
**What it does:**
- Builds/deploys firmware to RP2040
- Runs 5 sequential test jobs:
  1. `test-connectivity` → `test_system_identification()`
  2. `test-position` → `test_motor_initial_position()`
  3. `test-midi` → `test_motor_response_to_midi()`
  4. `test-sweep` → `test_motor_sweep()`
  5. `test-scaling` → `test_joystick_scaling()`

**Current Coverage:**
- ✅ Verifies device responds to commands
- ✅ Checks motor reaches initial position
- ⚠️ **Partial MIDI**: Sends CC#64 but doesn't verify other CCs (CC#7, CC#5, etc.)
- ⚠️ **Single-axis only**: All tests hardcoded for Motor 0
- ⚠️ **Sweep is limited**: Tests CC#64 value range 0-64 only
- ❌ **Does NOT test multi-motor configuration** (`pico_2motor_limited`)
- ❌ **Does NOT test motor limits** for limited-range configs
- ❌ **Does NOT test PID tuning quality**

---

## Missing Tests (Critical Gaps)

### Gap 1: Dual-Motor Support Never Validated ⚠️ HIGH PRIORITY
**Purpose says:** "Dual-axis support (throttle + trim)" - PRIMARY GOAL

**Current reality:** 
- `pico_2motor_limited` compiles but is never tested on hardware
- No CI test sends commands to Motor 1 (CC#5, CC#11, CC#64 for Motor 1)
- No test verifies independent motor control

**Missing test:**
```python
def test_dual_motor_independent_control():
    """Verify Motor 0 and Motor 1 move independently"""
    # Send CC#7 (Motor 0) - should move Motor 0 only
    # Verify Motor 1 doesn't move
    # Send CC#64 (Motor 1) - should move Motor 1 only
    # Verify Motor 0 doesn't move
```

**Action required:** Add dual-motor test to hardware-test.yml

---

### Gap 2: PID Tuning Quality Never Verified ⚠️ HIGH PRIORITY
**Purpose says:** "Reliable motor control with tunable PID" - PRIMARY GOAL & SUCCESS CRITERION

**Current tools:**
- `calibrate_pid.py` exists and can:
  - Auto-tune PID gains via Ziegler-Nichols
  - Measure tuning quality (overshoot, settling time, noise, drift, stability)
  - Generate detailed reports

**Current CI reality:**
- ❌ `calibrate_pid.py` is NEVER called in any CI workflow
- ❌ No tuning quality metrics collected
- ❌ No validation that PID tuning meets quality criteria

**Success criteria from PURPOSE.md:**
- [ ] Motor spins and tracks target angle
- [ ] USB HID reports joystick position
- **[MISSING] Validate PID tuning quality**

**Action required:**
1. Add PID calibration job to hardware-test.yml
2. Define quality acceptance criteria (e.g., settling time <1s, overshoot <5%)
3. Fail CI if tuning quality is below threshold

---

### Gap 3: Motor Limits Not Validated ❌ UNTESTED
**Config supports:**
- `pico_1motor_limited`: 0-180° (tested but limits never checked)
- `pico_2motor_limited`: Motor 0 limited, Motor 1 endless

**Current tests:**
- Sweep test only goes CC#0-64 (roughly 0-90° range)
- No test verifies motor clamps at max angle
- No test checks that opposing commands don't overshoot

**Missing test:**
```python
def test_motor_limits_clamping():
    """Verify limited motors clamp at bounds"""
    # Send CC#127 (max) - verify angle clamps to max_angle
    # Send CC#0 (min) - verify angle clamps to min_angle
    # Try to send beyond bounds - verify no jumping/wrapping
```

**Action required:** Add limit-clamping test for `pico_1motor_limited` and `pico_2motor_limited`

---

### Gap 4: MIDI Protocol Not Fully Validated ⚠️ MEDIUM PRIORITY
**Purpose says:** "MIDI input for flight controls" - PRIMARY GOAL

**Config defines 5 MIDI CCs:**
- CC#7 (Throttle, Motor 0)
- CC#5 (Flaps, Motor 0)
- CC#11 (Spoilers, Motor 0)
- CC#64 (Trim, Motor 1 endless)
- (And more for dual-motor config)

**Current test:**
- Only sends CC#64 with single value (127)
- Does NOT test:
  - CC#7, CC#5, CC#11 (other axes)
  - Full value range (0-127)
  - MIDI protocol validation (error handling, invalid CCs)

**Missing test:**
```python
def test_all_midi_axes():
    """Verify all configured CCs control their motors"""
    for axis in A320_CONFIG:
        cc_num = axis.midi_cc
        # Test CC at 0, 64, 127
        # Verify motor position changes correspond to CC value
        # Verify motor mapping is correct
```

**Action required:** Parameterize MIDI test to cover all configured axes

---

### Gap 5: Configuration Never Validated ❌ UNTESTED
**Status:**
- `test_config.cpp` exists (217 lines of GoogleTest)
- **Not compiled or run by any CI workflow**
- No validation that config structures are correct

**Current situation:**
- Config changes could introduce bugs and CI wouldn't catch them
- No test verifies mapping between MIDI CCs and motors

**Action required:**
1. Compile and run `platformio test -e test` in CI
2. Or migrate test_config.cpp tests to pytest for easier CI integration

---

### Gap 6: SimpleFOC Commander Integration Not Tested ⚠️ LOWER PRIORITY
**Purpose mentions:** "Real-time PID tuning via SimpleFOC Commander"

**Current state:**
- Infrastructure exists (`commander_integration.cpp`)
- No CI test verifies it works
- No test validates parameter persistence

**Note:** This is lower priority if Commander is primarily for development/debugging

---

## Test Coverage Matrix

| Feature | Test Case | CI Workflow | Status | Notes |
|---------|-----------|-------------|--------|-------|
| **Motor Control** | | | | |
| - Single motor responds | `test_sweep` | hardware-test.yml | ✅ | CC#64 only |
| - Multi-motor independent | *(missing)* | ❌ | ❌ | Never tested |
| - PID tuning quality | `calibrate_pid.py` | ❌ | ❌ | Exists but not run |
| - Motor limits clamping | *(missing)* | ❌ | ❌ | Never tested |
| **USB HID** | | | | |
| - Joystick reports | `test_joystick_scaling` | hardware-test.yml | ✅ | 0-1023 range verified |
| - Axis mapping | *(implicit in sweep)* | hardware-test.yml | ⚠️ | Only axis 0 tested |
| **MIDI Input** | | | | |
| - CC message parsing | `test_motor_response_to_midi` | hardware-test.yml | ⚠️ | CC#64 only |
| - All axes respond | *(missing)* | ❌ | ❌ | 4 other CCs untested |
| - Full value range | `test_motor_sweep` | hardware-test.yml | ⚠️ | Limited to 0-64 |
| **Build Quality** | | | | |
| - Compiles all configs | `build.yml` | github | ✅ | 3 environments |
| - Function size limit | `code-quality.yml` | github | ✅ | ≤43 lines enforced |
| **Headless Tests** | | | | |
| - Simulator axis mapping | `test_sim_device.py` | headless-test.yml | ✅ | Full coverage |
| - Configuration structure | `test_config.cpp` | ❌ | ❌ | Exists but not run |

---

## Recommendations (Priority Order)

### 🔴 CRITICAL (Block CI on failure)
1. **Add dual-motor test** to hardware-test.yml
   - Required for `pico_2motor_limited` environment
   - Purpose lists "Dual-axis support" as PRIMARY goal
   - Prevents shipping broken dual-motor config

2. **Add PID quality validation** to hardware-test.yml
   - Run `calibrate_pid.py` after deployment
   - Define acceptance criteria (settling time, overshoot, stability)
   - Purpose lists "Reliable motor control" as PRIMARY goal

### 🟠 HIGH (Should fix before release)
3. **Parameterize MIDI test** to cover all configured CCs
   - Currently only tests CC#64
   - Config defines 5+ CCs (CC#7, CC#5, CC#11, CC#64, etc.)
   - Prevents shipping with silent MIDI failures on untested axes

4. **Add motor limit clamping tests**
   - Required for `pico_1motor_limited` and `pico_2motor_limited`
   - Verify motors don't overshoot bounds
   - Simple but critical for safety

### 🟡 MEDIUM (Nice to have)
5. **Run configuration unit tests** (`test_config.cpp`)
   - Catch config structure bugs early
   - Migrate to pytest or add `platformio test` to CI

6. **Extend sweep test range**
   - Currently tests CC#0-64 only
   - Should test full 0-127 range (at least for single-axis configs)

### 🟢 LOW (Consider for future)
7. **Add SimpleFOC Commander integration test**
   - Verify tuning parameter persistence
   - Lower priority if Commander is development-only tool

---

## Implementation Plan

### Phase 1: Dual-Motor & MIDI Coverage (Required)
```yaml
  test-dual-motors:
    name: Test - Dual Motor Control
    needs: [deploy]
    runs-on: [self-hosted, hardware]
    steps:
      - run: python3 test/test_suite_automated.py --tests dual-motors
  
  test-all-midi:
    name: Test - All MIDI Axes
    needs: [deploy]
    runs-on: [self-hosted, hardware]
    steps:
      - run: python3 test/test_suite_automated.py --tests all-midi
```

### Phase 2: PID & Limits Validation
```yaml
  test-pid-quality:
    name: Test - PID Tuning Quality
    needs: [deploy]
    runs-on: [self-hosted, hardware]
    steps:
      - run: |
          cd test
          python3 calibrate_pid.py --motor 0 --json-out ci_pid_report.json
          python3 - << 'PY'
          import json
          report = json.load(open('ci_pid_report.json'))
          if report['score'] < 70:
              exit(1)  # Fail CI if tuning quality is poor
          PY
  
  test-motor-limits:
    name: Test - Motor Limits
    needs: [deploy]
    runs-on: [self-hosted, hardware]
    steps:
      - run: python3 test/test_suite_automated.py --tests limits
```

### Phase 3: Configuration Validation
```yaml
  validate-config:
    name: Validate Configuration
    runs-on: ubuntu-latest
    steps:
      - run: platformio test -e test
```

---

## Detailed Gap Analysis by Goal

### ✅ Goal: USB HID Joystick Output
- **Purpose:** "USB HID output as joystick (TinyUSB)"
- **CI Coverage:** ✅ **GOOD**
  - `test_joystick_scaling` verifies 0-1023 range
  - Simulator tests validate axis mapping
  - Both single and dual configs compile
- **Verdict:** ✅ Sufficient

### ⏳ Goal: MIDI Input for Flight Controls  
- **Purpose:** "MIDI input for flight sim controls (throttle, flaps, spoilers, trim, gear)"
- **CI Coverage:** ⚠️ **PARTIAL**
  - ✅ Verifies CC#64 works
  - ❌ Does NOT test CC#7 (Throttle), CC#5 (Flaps), CC#11 (Spoilers)
  - ❌ No test for multi-motor MIDI routing
- **Verdict:** ❌ **INSUFFICIENT** - only 1 of 5+ axes tested

### ✅ Goal: Reliable Motor Control with Tunable PID
- **Purpose:** "Reliable motor control with tunable PID"
- **CI Coverage:** ⚠️ **PARTIAL**
  - ✅ Motor spins and reaches target (sweep test)
  - ✅ PID auto-tuning tool exists (calibrate_pid.py)
  - ❌ **PID quality NEVER validated in CI**
  - ❌ No threshold for acceptable tuning quality
- **Verdict:** ⚠️ **INCOMPLETE** - tool exists but not integrated to CI

### ⏳ Goal: Dual-Axis Support
- **Purpose:** "Dual-axis support (throttle + trim)" - Listed as PRIMARY
- **CI Coverage:** ❌ **NONE**
  - ✅ Firmware compiles (`pico_2motor_limited`)
  - ❌ No hardware test for dual motors
  - ❌ No test sends commands to Motor 1
- **Verdict:** ❌ **NOT TESTED** - Critical gap for stated primary goal

### ✅ Goal: Automated Headless Testing
- **Purpose:** "Automated headless testing"
- **CI Coverage:** ✅ **GOOD**
  - pytest simulator tests (3 tests pass)
  - Validates axis mapping without hardware
- **Verdict:** ✅ Sufficient

### ⏳ Goal: Automated Hardware Testing
- **Purpose:** "Automated hardware testing (requires manual BOOTSEL trigger)"
- **CI Coverage:** ⚠️ **PARTIAL**
  - ✅ Build & deploy workflow functions
  - ✅ 5 test jobs run (connectivity, position, MIDI, sweep, scaling)
  - ❌ Tests only single-motor scenario
  - ❌ Missing dual-motor validation
- **Verdict:** ⚠️ **INCOMPLETE** - Works for single-motor, missing multi-motor

---

## Questions for Human Review

1. **Is dual-motor support a requirement for this phase?**
   - If YES: Add dual-motor tests to hardware-test.yml (Phase 1)
   - If NO: Mark as "future" and update PURPOSE.md success criteria

2. **What is the minimum acceptable PID tuning quality?**
   - Settling time: <1s? <2s?
   - Overshoot: <5%? <10%?
   - Position stability: >90%? >80%?

3. **Should all MIDI CCs be tested in every CI run?**
   - Pro: Catches silent failures on untested axes
   - Con: Longer CI runtime, requires full config knowledge
   - Suggestion: Mock/parameterize based on config

4. **Is SimpleFOC Commander integration a requirement?**
   - If development-only: Lower priority
   - If production feature: Needs integration test

---

## Summary

**CI Status: ⚠️ MAJOR GAPS - Does not comprehensively validate stated purpose**

### What's Tested ✅
- Single-motor CC#64 response (sweep, scaling, connectivity)
- USB HID 0-1023 range
- Firmware compiles for all environments
- Code follows 43-line function limit

### What's NOT Tested ❌
- **Dual-motor independent control** (stated PRIMARY goal)
- **PID tuning quality** (stated PRIMARY goal, tool exists)
- **Motor limits clamping** (required for limited-range motors)
- **MIDI axes other than CC#64** (stated PRIMARY feature)
- **Configuration correctness** (test exists but not run)

### Immediate Actions (1-day fix)
1. Document test gaps in `.agentic/CI_COVERAGE_REVIEW.md` ← **This file**
2. Decide: Is dual-motor support required NOW?
3. Define: What PID quality is acceptable?
4. Decide: Should calibrate_pid.py run in CI pipeline?

**Recommendation:** Do NOT merge to `main` or release until dual-motor and PID quality tests are added (both are stated PRIMARY goals with existing implementation).
