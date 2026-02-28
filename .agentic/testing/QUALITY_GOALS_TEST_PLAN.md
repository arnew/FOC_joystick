# Quality Goals Test Suite Plan

**Date**: February 28, 2026  
**Target Device**: Raspberry Pi Pico (RP2040) - pico_1motor_endless  
**Hardware Status**: ✅ DETECTED (/dev/ttyACM0)

---

## Quality Goals (from README.md)

### Primary Objectives

1. **Resolution**: 1 degree or better
2. **Speed**: 60 rpm or better
3. **Position Hold Precision**:
   - Target must be met within ±1 degree
   - Position noise <1 degree variance (500ms rolling average)
4. **Movement Precision**:
   - Overshoot must be <5 degrees
5. **Sampling**:
   - Rolling average of last 500ms
   - Resettable min/max position tracking

---

## Test Suite Architecture

### TEST A: Resolution & Sampling
**Objective**: Verify 1° resolution and proper statistical sampling  
**Duration**: ~30 seconds  
**Measurement Points**: 10 samples across 0-360°

| Test Case | Command | Expected Result | Pass Criteria |
|-----------|---------|-----------------|---------------|
| A1 | Set target: 0° | Report: 0° ± 0.5° | Error ≤ 1.0° |
| A2 | Set target: 45° | Report: 45° ± 0.5° | Error ≤ 1.0° |
| A3 | Set target: 90° | Report: 90° ± 0.5° | Error ≤ 1.0° |
| A4 | Set target: 180° | Report: 180° ± 0.5° | Error ≤ 1.0° |
| A5 | Set target: 270° | Report: 270° ± 0.5° | Error ≤ 1.0° |
| A6 | Set target: 330° | Report: 330° ± 0.5° | Error ≤ 1.0° |

**Measurement**: Position samples captured at 1Hz (debug output)

---

### TEST B: Speed / RPM Measurement
**Objective**: Verify motor achieves ≥60 rpm  
**Duration**: ~10 seconds per rotation  
**Measurement**: Time from 0° to 360° (wrap)

| Test Case | Command | Expected | Pass Criteria |
|-----------|---------|----------|---------------|
| B1 | Sweep 0°→360° (forward) | ≥60 rpm (~100ms/°) | Time ≤ 6 sec for 360° |
| B2 | Sweep 360°→0° (reverse) | ≥60 rpm | Time ≤ 6 sec for 360° |
| B3 | Multiple reversals | Consistent speed | All ≤6 sec |

**Measurement**: Timestamp start/stop, calculate angular velocity

**Formula**: RPM = 360° / time_seconds / 60

---

### TEST C: Position Hold Stability
**Objective**: Verify ±1° target accuracy and <1° noise  
**Duration**: 5 seconds per position  
**Measurement**: Capture 5 samples (1 Hz) at each position, calculate mean & variance

| Test Case | Target | Expected Avg | Max Variance | Pass Criteria |
|-----------|--------|-------------|--------------|---------------|
| C1 | Hold at 0° | 0° ± 0.5° | σ < 0.5° | Mean error ≤ 1°, σ < 1° |
| C2 | Hold at 90° | 90° ± 0.5° | σ < 0.5° | Mean error ≤ 1°, σ < 1° |
| C3 | Hold at 180° | 180° ± 0.5° | σ < 0.5° | Mean error ≤ 1°, σ < 1° |
| C4 | Hold at 270° | 270° ± 0.5° | σ < 0.5° | Mean error ≤ 1°, σ < 1° |

**Measurement**:
```
Mean = Σ(samples) / N
Variance = Σ(sample - mean)² / N
StdDev = √Variance
```

---

### TEST D: Movement Overshoot
**Objective**: Verify <5° overshoot during target changes  
**Duration**: 10 seconds per movement  
**Measurement**: Track max angle after target set, calculate overshoot

| Test Case | Start | Target | Max Measured | Pass Criteria |
|-----------|-------|--------|--------------|---------------|
| D1 | 0° | 90° | < 95° | Overshoot < 5° |
| D2 | 90° | 180° | < 185° | Overshoot < 5° |
| D3 | 180° | 270° | < 275° | Overshoot < 5° |
| D4 | 270° | 0° (wrap) | < 5° | Wrapping OK |
| D5 | 0° | 270° (wrap) | > 355° or < 5° | Wrapping OK |

**Measurement**: Capture all samples during movement, find peak

---

### TEST E: Multi-Position Sequence
**Objective**: Verify consistency across repeated movements  
**Duration**: 60 seconds  
**Measurement**: 20 random target changes, verify each settles

| Metric | Target | Measured | Pass Criteria |
|--------|--------|----------|---------------|
| Settle time | <2 sec | ? | 95% settle ≤2 sec |
| Position accuracy | ±1° | ? | All within ±1° |
| No oscillation | Damped | ? | No sustained oscillation |

---

### TEST F: Edge Cases & Stress
**Objective**: Verify robustness to extreme inputs  
**Duration**: 30 seconds

| Test Case | Input | Expected | Pass Criteria |
|-----------|-------|----------|---------------|
| F1 | Rapid fire commands (10/sec) | Graceful degradation | No crashes, lags recoverable |
| F2 | Hold at boundary (0°) | Stable | No jitter >1° |
| F3 | Hold at wrap point (359.9°) | Smooth wrap to 0° | Continuous motion |
| F4 | Reset statistics mid-test | Counters reset | Stats reset confirmed |

---

## Test Methodology

### Hardware Setup
```
Device: RPi Pico (RP2040) running pico_1motor_endless firmware
Connection: USB Serial (/dev/ttyACM0)
Debug interface: SimpleFOC Commander + statistics
```

### Test Execution Flow

```
1. Device Detection
   └─ Enumerate /dev/ttyACM*
   └─ Send 'M0?' to verify responsiveness
   
2. Baseline Measurement
   └─ Request statistics with 'S'
   └─ Record initial state
   
3. Run Test Suites (A → F)
   ├─ TEST A: Resolution (10 positions, verify accuracy)
   ├─ TEST B: Speed (measure RPM across sweeps)
   ├─ TEST C: Position hold (5-sec stability at 4 positions)
   ├─ TEST D: Overshoot (5 movements, verify <5°)
   ├─ TEST E: Sequence (20 random targets, check consistency)
   └─ TEST F: Stress (rapid commands, edge cases)
   
4. Post-Test Analysis
   ├─ Calculate statistics for each test
   ├─ Generate pass/fail report
   ├─ Export to JSON & human-readable format
   └─ Request final 'S' stats
```

### Data Collection

**Per-sample data** (captured from debug output line `A=X.XX T=Y.YY JS=...`):
- `A`: Current actual angle (radians) → convert to degrees
- `T`: Target angle (radians) → convert to degrees
- Sample rate: 1 Hz (default)
- Timestamp: Record system time for each sample

**Derived metrics**:
- Error: |actual - target|
- Overshoot: max(actual) - target (after target set)
- Variance: σ² of samples
- Settling time: time to reach ±1° and stay within
- RPM: 360° / (time in seconds) for full rotation

---

## Pass/Fail Criteria Summary

| Goal | Test | Criteria | Status |
|------|------|----------|--------|
| **Resolution** | TEST A | All positions ≤1° error | ? |
| **Speed** | TEST B | ≥60 rpm (360° ≤6 sec) | ? |
| **Hold Accuracy** | TEST C | Mean ≤1°, σ<1° | ? |
| **Overshoot** | TEST D | Peak ≤5° above target | ? |
| **Consistency** | TEST E | 95% settle ≤2 sec | ? |
| **Robustness** | TEST F | No crashes under stress | ? |

**Overall Pass**: ALL tests PASS

---

## Test Implementation Language

**Python 3** with `pyserial`

### Key Modules
```python
import serial
import time
import math
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Tuple

@dataclass
class Sample:
    timestamp: float
    actual_deg: float
    target_deg: float
    error_deg: float
```

### Test Class Structure
```python
class QualityGoalsTestSuite:
    def __init__(self, port='/dev/ttyACM0'):
        self.ser = serial.Serial(port, 115200, timeout=1)
        self.results = {}
    
    def test_a_resolution(self) -> bool:
        """TEST A: Resolution & Sample Accuracy"""
        ...
    
    def test_b_speed(self) -> bool:
        """TEST B: RPM Measurement"""
        ...
    
    def test_c_position_hold(self) -> bool:
        """TEST C: Position Hold Stability"""
        ...
    
    def test_d_overshoot(self) -> bool:
        """TEST D: Movement Overshoot"""
        ...
    
    def test_e_sequence(self) -> bool:
        """TEST E: Multi-Position Consistency"""
        ...
    
    def test_f_stress(self) -> bool:
        """TEST F: Edge Cases & Robustness"""
        ...
    
    def run_all(self) -> bool:
        """Run complete test suite"""
        ...
    
    def print_report(self):
        """Print human-readable results"""
        ...
    
    def export_json(self, filename: str):
        """Export results to JSON"""
        ...
```

---

## Expected Results (Reference)

Based on quality goals from README, expected outcomes:

### TEST A: Resolution
```
Position 0°:   Measured 0.3° ± 0.2° ✓
Position 45°:  Measured 45.1° ± 0.3° ✓
Position 90°:  Measured 89.8° ± 0.2° ✓
Position 180°: Measured 180.2° ± 0.1° ✓
Position 270°: Measured 269.9° ± 0.2° ✓
Position 330°: Measured 330.4° ± 0.3° ✓
```

### TEST B: Speed
```
Sweep 0→360°:  6.0 seconds → 60 rpm ✓
Sweep 360→0°:  5.8 seconds → 62 rpm ✓
Reverse sweep: 6.1 seconds → 59 rpm ✓
Average: ~60 rpm ✓
```

### TEST C: Position Hold (5s each, 5 samples @ 1Hz)
```
Hold at 0°:
  Samples: [0.1, 0.2, 0.0, 0.1, 0.2]
  Mean: 0.12° ✓ (≤1°)
  StdDev: 0.08° ✓ (<1°)

Hold at 90°:
  Samples: [89.9, 90.1, 89.8, 90.2, 90.0]
  Mean: 90.0° ✓
  StdDev: 0.16° ✓
```

### TEST D: Overshoot
```
Move 0° → 90°:
  Target: 90°
  Peak measured: 93.2°
  Overshoot: 3.2° ✓ (<5°)
  
Move 90° → 180°:
  Target: 180°
  Peak measured: 182.8°
  Overshoot: 2.8° ✓
```

---

## Test Execution Schedule

```
Estimated Runtime:
  - Setup & connectivity: 2 min
  - TEST A (Resolution): 3 min
  - TEST B (Speed): 3 min
  - TEST C (Hold): 5 min
  - TEST D (Overshoot): 3 min
  - TEST E (Sequence): 3 min
  - TEST F (Stress): 2 min
  - Analysis & reporting: 2 min
  ───────────────────────
  TOTAL: ~23 minutes

Optimal execution: Run full suite once, document results
```

---

## Next Steps

1. ✅ Detect hardware (DONE)
2. ⏳ Implement quality_goals_test_suite.py
3. ⏳ Run TEST A-F on device
4. ⏳ Document results in .agentic/QUALITY_GOALS_TEST_RESULTS.md
5. ⏳ Update quality metrics database
