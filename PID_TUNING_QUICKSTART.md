# PID Tuning Calibration System - Quick Start

## What Was Added

A complete **automatic PID tuning framework** using the proven **Ziegler-Nichols relay method** to eliminate motor oscillations and optimize response.

### Files Created
- **`test/calibrate_pid.py`** - Automated calibration script (300+ lines)
- **`include/pid_config.h`** - Centralized PID configuration
- **`test/CALIBRATION.md`** - Complete tuning guide with theory
- **Modified `src/main.cpp`** - Uses configurable PID gains

## Problem Solved

**Motor oscillating in idle state** → Use relay tuning to auto-calculate optimal Kp, Ki, Kd gains

## How It Works (Simple Overview)

```
1. Run calibration script
   ↓
2. Script sends square wave to motor via MIDI
   ↓
3. Measures oscillation frequency & amplitude
   ↓
4. Applies Ziegler-Nichols equations
   ↓
5. Calculates optimized PID gains
   ↓
6. You update pid_config.h and rebuild firmware
```

## Usage

### One-Command Fix
```bash
# Full automatic tuning (relay + step response validation)
cd /home/arnew/Notebooks.st.rasentrimmer.org/FOC/rp2040_mini_as5600
python3 test/calibrate_pid.py
```

### Output Example
```
✓ Relay Test Results:
  Oscillation Period (Pu): 0.542s
  Ultimate Gain (Ku): 3.241
  
✓ Ziegler-Nichols PID Gains (with safety factor):
  Kp: 1.265230
  Ki: 0.004521
  Kd: 0.318475

To apply, edit include/pid_config.h:
  #define MOTOR0_PID_P  1.265230
  #define MOTOR0_PID_I  0.004521
  #define MOTOR0_PID_D  0.318475
```

## Current Configuration (Safe Defaults)

In `include/pid_config.h`:
```cpp
#define MOTOR0_PID_P  2.5f    // Proportional (responsiveness)
#define MOTOR0_PID_I  0.0f    // Integral (steady-state error)
#define MOTOR0_PID_D  0.5f    // Derivative (damping oscillation)
```

These are **conservative values** that work on most setups. Calibration will fine-tune them for YOUR hardware.

## What Happens After Calibration

If oscillations detected:
- Script **increases Kd** (damping) and/or **decreases Kp** (responsiveness)
- Reduces overshoot and settling time
- Makes motor control smoother and more stable

## Key Features

✅ **Automated** - One command to run entire tuning  
✅ **Theory-based** - Ziegler-Nichols proven method  
✅ **Safe** - Includes 0.65x safety factor  
✅ **Flexible** - Relay test, step response, custom frequency  
✅ **Documented** - Full CALIBRATION.md guide  
✅ **Configurable** - Centralized pid_config.h  

## Files Reference

| File | Purpose |
|------|---------|
| `test/calibrate_pid.py` | Run: `python3 test/calibrate_pid.py` |
| `include/pid_config.h` | Edit after calibration, then rebuild |
| `test/CALIBRATION.md` | Theory, manual tuning, troubleshooting |
| `src/main.cpp` | Uses gains from pid_config.h at startup |

## Next Steps

1. **Try it** (optional test without changes):
   ```bash
   python3 test/calibrate_pid.py --relay-only
   ```

2. **If oscillations confirmed**, run full calibration and apply gains

3. **Rebuild and upload**:
   ```bash
   platformio run -e pico_1motor_endless
   platformio run -e pico_1motor_endless --target upload
   bash test/run_tests.sh pico_1motor_endless
   ```

4. **Fine-tune manually** if needed (see CALIBRATION.md table)

## Technical Details

- **Relay Method**: Induces oscillation, measures frequency → calculates ultimate gain
- **Ziegler-Nichols Equations**: Proven across decades of controls engineering
- **Safety Factor**: 0.65x reduces gains 35% → prevents instability on real hardware
- **Cascaded Loops**: Angle loop (tuned) + velocity loop (conservative)

See `test/CALIBRATION.md` for advanced tuning and troubleshooting.

