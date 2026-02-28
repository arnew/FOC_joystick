# CI Test Implementation Roadmap

**Last Updated:** 2026-02-27  
**Scope:** Closing gaps identified in CI_COVERAGE_REVIEW.md

---

## Gap 1: Dual-Motor Test (Critical)

### Implementation: Add `test_dual_motor_independent_control()` 

**File:** `test/test_suite_automated.py`

**Test Logic:**
```python
def test_dual_motor_independent_control(self):
    """Test motor 0 and motor 1 respond independently"""
    print("\n" + "=" * 70)
    print("TEST 6: Dual-Motor Independent Control")
    print("=" * 70)
    
    # Verify we're on dual-motor config
    if NUM_MOTORS != 2:
        print(f"⊘ SKIP: Not a dual-motor config (NUM_MOTORS={NUM_MOTORS})")
        self.results.append(("Dual Motor Control", None, "Single-motor config"))
        return None
    
    # Test sequence:
    # 1. Get baseline (all at rest)
    # 2. Send CC#7 (Motor 0) - verify Motor 0 moves, Motor 1 stays
    # 3. Send CC#64 (Motor 1) - verify Motor 1 moves, Motor 0 doesn't follow
    
    baseline = self._get_dual_motor_status()  # Returns (angle0, angle1)
    
    # Test Motor 0 isolation
    self.send_midi_cc(7, 100)  # CC#7 = Throttle
    time.sleep(0.5)
    motor0_moved, motor1_moved = self._verify_motor_isolation(baseline)
    
    if not motor0_moved:
        print("✗ FAIL: Motor 0 did not respond to CC#7")
        return False
    if motor1_moved:
        print("✗ FAIL: Motor 1 moved when CC#7 sent (crosstalk!)")
        return False
    
    # Test Motor 1 isolation
    self.send_midi_cc(64, 100)  # CC#64 = Trim
    time.sleep(0.5)
    motor0_moved, motor1_moved = self._verify_motor_isolation(baseline)
    
    if not motor1_moved:
        print("✗ FAIL: Motor 1 did not respond to CC#64")
        return False
    if motor0_moved:
        print("✗ FAIL: Motor 0 moved when CC#64 sent (crosstalk!)")
        return False
    
    print("✓ PASS: Motors control independently")
    self.results.append(("Dual Motor Control", True, None))
    return True
```

**Requirements for test:**
- Read debug output at 2+ positions to estimate angles for both motors
- Parse output format to extract both angle values
- Timeout: 10 seconds per motor
- Accept hardware-test.yml: Single dual-motor run on `pico_2motor_limited` env

**CI Integration:** Add to hardware-test.yml
```yaml
  test-dual-motors:
    name: Test - Dual Motor Control
    needs: [deploy]
    runs-on: [self-hosted, hardware]
    if: contains(github.event.head_commit.message, 'dual') ||
        contains(github.ref, 'feature/dual') ||
        github.event_name == 'workflow_dispatch'
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Run dual-motor test
        run: |
          cd test
          python3 test_suite_automated.py --tests dual-motors
```

**Status:** ⚠️ **BLOCKED** - Requires configuration to expose motor count and dual debugging info

---

## Gap 2: PID Quality Validation (Critical)

### Implementation: Add `ci_validate_pid_quality()` wrapper

**File:** `test/validate_pid_quality.py` (new)

```python
#!/usr/bin/env python3
"""Validate PID tuning quality for CI"""

import json
import subprocess
import sys
from pathlib import Path

def run_calibration(motor_id=0):
    """Run PID calibration and collect metrics"""
    result = subprocess.run([
        'python3', 'test/calibrate_pid.py',
        f'--motor {motor_id}',
        '--json-out ci_pid_metrics.json'
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"✗ Calibration failed: {result.stderr}")
        return None
    
    with open('ci_pid_metrics.json') as f:
        return json.load(f)

def validate_quality(metrics):
    """Check if tuning quality meets CI thresholds"""
    
    thresholds = {
        'overshoot_percent': 10.0,      # <10% overshoot
        'settling_time_sec': 2.0,         # <2s settling
        'position_noise_deg': 2.0,        # <2° jitter
        'position_drift_deg': 5.0,        # <5° drift over test
        'stability_percent': 80.0,        # >80% stable
    }
    
    failures = []
    for metric, threshold in thresholds.items():
        actual = metrics.get(metric)
        if actual is None:
            continue
        
        # For percentage metrics, higher is better
        if 'percent' in metric:
            if actual < threshold:
                failures.append(f"{metric}: {actual:.1f}% < {threshold}%")
        else:
            # For other metrics, lower is better
            if actual > threshold:
                failures.append(f"{metric}: {actual:.2f} > {threshold}")
    
    return failures

def main():
    print("=" * 70)
    print("PID QUALITY VALIDATION FOR CI")
    print("=" * 70)
    
    metrics = run_calibration(motor_id=0)
    if not metrics:
        print("✗ FAIL: Could not collect PID metrics")
        sys.exit(1)
    
    print("\nTuning Quality Report:")
    print(f"  Overshoot: {metrics['overshoot_percent']:.1f}%")
    print(f"  Settling Time: {metrics['settling_time_sec']:.2f}s")
    print(f"  Position Noise: {metrics['position_noise_deg']:.2f}°")
    print(f"  Position Drift: {metrics['position_drift_deg']:.2f}°")
    print(f"  Stability: {metrics['stability_percent']:.1f}%")
    
    failures = validate_quality(metrics)
    if failures:
        print("\n✗ FAIL: Tuning quality below CI thresholds:")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)
    
    print("\n✓ PASS: PID tuning quality acceptable")
    sys.exit(0)

if __name__ == '__main__':
    main()
```

**CI Integration:** Add to hardware-test.yml
```yaml
  test-pid-quality:
    name: Test - PID Tuning Quality
    needs: [deploy]
    runs-on: [self-hosted, hardware]
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Validate PID tuning quality
        run: |
          cd test
          python3 validate_pid_quality.py
      
      - name: Upload PID metrics
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: pid-metrics-${{ github.run_number }}
          path: test/ci_pid_metrics.json
```

**Status:** ⚠️ **READY** - calibrate_pid.py exists, just needs CI wrapper

---

## Gap 3: All-MIDI-Axes Test (High Priority)

### Implementation: Parameterize MIDI test

**File:** `test/test_suite_automated.py` - Extend `test_motor_response_to_midi()`

**Current:** Only tests CC#64
**Needed:** Test all axes from config

```python
def test_all_midi_axes(self):
    """Test all MIDI axes control their assigned motors"""
    print("\n" + "=" * 70)
    print("TEST 3B: MIDI All Axes (Parameterized)")
    print("=" * 70)
    
    if not self.midi_output and not self.midi_ser:
        print("⊘ SKIP: MIDI port unavailable")
        return None
    
    # Read config to find all axes
    # This would require parsing config.h or having firmware report it
    
    failures = []
    for axis in A320_CONFIG:
        cc_num = axis.midi_cc
        motor_id = axis.motor_id
        label = axis.label
        
        try:
            # Get baseline
            baseline = self._read_motor_angle(motor_id)
            
            # Send MIDI command
            self.send_midi_cc(cc_num, 100)
            time.sleep(0.3)
            
            # Check if motor moved
            final = self._read_motor_angle(motor_id)
            delta = abs(final - baseline)
            
            if delta >= 0.05:  # 0.05 rad = ~3°
                print(f"✓ CC#{cc_num:3d} ({label:10s}) → Motor {motor_id} moved {delta:.3f} rad")
            else:
                print(f"✗ CC#{cc_num:3d} ({label:10s}) → NO RESPONSE")
                failures.append(f"CC#{cc_num} {label}")
        except Exception as e:
            print(f"✗ CC#{cc_num:3d} ({label:10s}) → ERROR: {e}")
            failures.append(f"CC#{cc_num} {label}: {e}")
    
    if failures:
        print(f"\n✗ FAIL: {len(failures)} axes did not respond")
        return False
    
    print(f"\n✓ PASS: All {len(A320_CONFIG)} axes respond to MIDI")
    return True
```

**Challenge:** Firmware must report motor count and axis config somehow
- Option A: Firmware prints config at startup
- Option B: Test hard-codes expected CCs per environment
- Option C: Add firmware command to query config

**Recommendation:** Option B (simplest)
```python
EXPECTED_CCS = {
    'pico_1motor_endless': [64],           # Trim only
    'pico_1motor_limited': [7, 5, 11],    # Throttle, Flaps, Spoilers
    'pico_2motor_limited': [7, 5, 11, 64], # All axes
}
```

**Status:** 🟡 **MEDIUM EFFORT** - Requires firmware config parsing or static mapping

---

## Gap 4: Motor Limits Test (High Priority)

### Implementation: Add limit clamping validation

**File:** `test/test_suite_automated.py`

```python
def test_motor_limits(self):
    """Verify limited motors clamp at bounds"""
    print("\n" + "=" * 70)
    print("TEST 7: Motor Limits Clamping")
    print("=" * 70)
    
    # Check if this is a limited-motor config
    limited_motors = []
    for motor in MOTORS:
        if not motor.is_endless:
            limited_motors.append(motor)
    
    if not limited_motors:
        print("⊘ SKIP: No limited-range motors in this config")
        return None
    
    failures = []
    
    for motor in limited_motors:
        motor_id = motor.id
        cc_num = get_cc_for_motor(motor_id)  # Find controlling CC
        min_angle = motor.min_angle
        max_angle = motor.max_angle
        
        print(f"\nTesting Motor {motor_id} limits: {min_angle:.2f}..{max_angle:.2f} rad")
        
        # Test min bound
        self.send_midi_cc(cc_num, 0)
        time.sleep(0.5)
        angle_min = self._read_motor_angle(motor_id)
        
        if angle_min < min_angle - 0.05:  # Allow 0.05 rad tolerance
            failures.append(f"Motor {motor_id} undershot min by {min_angle - angle_min:.3f} rad")
        print(f"  Sent CC#0 → angle={angle_min:.4f} rad (min={min_angle:.4f})")
        
        # Test max bound
        self.send_midi_cc(cc_num, 127)
        time.sleep(0.5)
        angle_max = self._read_motor_angle(motor_id)
        
        if angle_max > max_angle + 0.05:  # Allow tolerance
            failures.append(f"Motor {motor_id} overshot max by {angle_max - max_angle:.3f} rad")
        print(f"  Sent CC#127 → angle={angle_max:.4f} rad (max={max_angle:.4f})")
    
    if failures:
        print(f"\n✗ FAIL: {len(failures)} limit violations:")
        for f in failures:
            print(f"  - {f}")
        return False
    
    print(f"\n✓ PASS: All {len(limited_motors)} limited motors clamp correctly")
    return True
```

**Status:** 🟡 **MEDIUM EFFORT** - Needs motor config exposure

---

## Gap 5: Run Configuration Tests (Medium Priority)

### Implementation: Run `test_config.cpp` in CI

**File:** `.github/workflows/build.yml` (add step)

```yaml
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [pico_1motor_endless, pico_1motor_limited, pico_2motor_limited]
    steps:
      # ... existing steps ...
      
      - name: Run configuration unit tests
        run: |
          platformio test -e test
      
      - name: Upload test results
        uses: actions/upload-artifact@v4
        with:
          name: config-tests-${{ matrix.environment }}
          path: .pio/test/
```

**Status:** ✅ **EASY** - Just needs to be added to CI job

---

## Phased Implementation Plan

### Phase 1: Immediate (This sprint)
- ✅ Document gaps (CI_COVERAGE_REVIEW.md) ← DONE
- ⏳ Run configuration tests (test_config.cpp in CI)
- ⏳ Add PID quality validation wrapper

**Time estimate:** 2-4 hours  
**Benefit:** Catches configuration bugs, validates PID tuning

### Phase 2: Dual-Motor Support (Next sprint)
- Design: How to parse/expose motor count to tests
- Implement: Dual-motor CC routing test
- Validate: Both `pico_2motor_limited` dual-axis scenarios

**Time estimate:** 4-6 hours  
**Benefit:** Validates stated PRIMARY goal

### Phase 3: Complete MIDI Coverage
- Parameterize test for all configured CCs
- Test full value range (0-127) for each axis
- Validate multi-axis MIDI routing

**Time estimate:** 3-5 hours  
**Benefit:** No silent MIDI failures

### Phase 4: Motor Limits (Future)
- Add limit clamping tests
- Validate both limited-motor configs
- Test edge cases (rapid direction changes)

**Time estimate:** 2-3 hours

---

##Dependencies & Blockers

| Gap | Status | Blocker | Solution |
|-----|--------|---------|----------|
| Dual-motor test | ⚠️ BLOCKED | Need motor count in debug output | Add "NUM_MOTORS" line to firmware startup |
| MIDI all-axes | ⚠️ BLOCKED | Need CC-to-motor mapping | Pass config to test or hard-code per environment |
| Motor limits | ⚠️ BLOCKED | Need axis config in test | Same as MIDI test |
| PID quality | ✅ READY | None | Just wrap calibrate_pid.py |
| Config tests | ✅ READY | None | Add `platformio test` to CI |

---

## Success Criteria

Once implemented:
- ✅ All PRIMARY goals have CI tests
- ✅ Dual-motor config runs on hardware
- ✅ All MIDI axes tested per config
- ✅ Motor limits validated for limited-range configs
- ✅ PID tuning quality measured & gated
- ✅ Configuration changes validated automatically

**Exit criteria for release:**
- All 5 test jobs pass in hardware-test.yml
- PID quality above threshold
- Zero configuration regressions
- 100% of PRIMARY goals tested
