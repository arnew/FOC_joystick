# PID Calibration Guide

This project includes an automated PID tuning system using the **Ziegler-Nichols relay method** to optimize motor response and eliminate oscillations.

## Problem: Why Motor Oscillates

The RP2040 motor controller uses a **proportional-derivative (PID) feedback loop** to position the motor accurately. If the PID gains are poorly tuned:

- **Low Kp (proportional gain)**: Motor responds too slowly, sluggish
- **High Kp**: Motor overshoots target and oscillates around setpoint
- **Low Kd (derivative gain)**: Oscillations are not damped
- **High Kd**: System becomes sluggish, jerky response

Current symptom: **Idle oscillation** → need higher Kd (damping) or lower Kp

## How Ziegler-Nichols Works

The relay method automatically tunes PID by:

1. **Relay Test** (~5 seconds):
   - Send a square wave input (0° → 90° → 0°)
   - Measure how the motor oscillates in response
   - Calculate oscillation frequency and amplitude

2. **Calculate Gains**:
   - Ultimate Gain (Ku): estimated from relay amplitude & response amplitude
   - Ultimate Period (Pu): measured oscillation frequency
   - Apply Ziegler-Nichols equations with safety factor (0.65x)

3. **Validate**:
   - Step response test to check overshoot and settling time
   - Confirm stable response without instability

## Quick Start

### 1. Run Calibration

```bash
cd /home/arnew/Notebooks.st.rasentrimmer.org/FOC/rp2040_mini_as5600

# Full automatic calibration (relay + step response)
python3 test/calibrate_pid.py

# Or individual tests:
python3 test/calibrate_pid.py --relay-only
python3 test/calibrate_pid.py --step-only --debug
```

### 2. Examine Results

Script will output:

```
✓ Relay Test Results:
  Oscillation Period (Pu): 0.542s
  Ultimate Gain (Ku): 3.241
  Oscillation Frequency: 1.85 Hz
  Peak Angle: 1.245 rad (71.4°)

✓ Ziegler-Nichols PID Gains (with 0.65 safety factor):
  Kp: 1.265230
  Ki: 0.004521
  Kd: 0.318475
```

### 3. Apply to Firmware

Edit `include/pid_config.h`:

```cpp
#define MOTOR0_PID_P  1.265230   // From calibration
#define MOTOR0_PID_I  0.004521
#define MOTOR0_PID_D  0.318475
```

### 4. Rebuild and Test

```bash
platformio run -e pico_1motor_endless
platformio run -e pico_1motor_endless --target upload
bash test/run_tests.sh pico_1motor_endless
```

## Manual Fine-Tuning

If calibration result is not perfect, adjust in small increments:

| Behavior | Adjustment | Rationale |
|----------|------------|-----------|
| Oscillating around target | ↑ Kd, ↓ Kp | Increase damping |
| Sluggish response | ↑ Kp, ↓ Kd | Increase responsiveness |
| Overshoots then oscillates | ↓ Kp, ↑ Kd | Reduce overshoot |
| Twitchy/jerky | ↓ Kd | Reduce excessive damping |
| Doesn't reach target | ↑ Kp or ↑ Ki | Increase error correction |

## PID Tuning Reference

### Ziegler-Nichols Equations

For process control (conservative tuning):

$$K_p = 0.6 \cdot K_u$$
$$K_i = 1.2 \cdot K_u / P_u$$
$$K_d = 3.0 \cdot K_u \cdot P_u / 40$$

Where:
- $K_u$ = **Ultimate Gain** (amplitude-dependent)
- $P_u$ = **Ultimate Period** (oscillation time in seconds)

**Safety Factor (0.65x)**: Reduces gains by 35% to avoid instability on real hardware

### SimpleFOC PID Structure

The motor uses **two cascaded loops**:

1. **Angle Loop** (outer):
   - Target: setpoint angle
   - Feedback: sensor angle
   - Output: velocity command
   - **Gains: Kp_angle, Ki_angle, Kd_angle**

2. **Velocity Loop** (inner):
   - Target: velocity from angle loop
   - Feedback: sensor velocity (calculated)
   - Output: voltage to motor
   - **Gains: Kp_velocity, Ki_velocity, Kd_velocity**

For smooth angle control, we focus on tuning the **angle loop** (Kp, Ki, Kd). The velocity loop is kept conservative with low gains.

## Advanced: Custom Relay Frequency

```bash
# Test at different frequencies to find best response (1-2 Hz typical):
python3 test/calibrate_pid.py --relay-only --debug

# Modify calibrate_pid.py line ~168:
relay_result = self.relay_test(duration=4.0, frequency=2.0)  # Change frequency here
```

## Troubleshooting

### No oscillation detected
- Motor might be over-damped
- Increase relay test duration: modify calibrate_pid.py
- Check physical motor connections and sensor

### Unstable after calibration
- Anti-windup: Motor might be hitting limits
- Check voltage_limit in pid_config.h (typical: 2-3V)
- Reduce Kd slightly if jerky

### Response too slow
- Increase Kp (proportional gain)
- Check if sensor is providing feedback (run `cat /dev/ttyACM0` during movement)

## Files

- **test/calibrate_pid.py** - Automated Ziegler-Nichols calibration script
- **include/pid_config.h** - PID gain configuration (edit after calibration)
- **src/main.cpp** - Motor initialization using pid_config.h values
- **.agentic/TEST_RESULTS.md** - Latest calibration results

## References

- SimpleFOC: https://docs.simplefoc.com/ (PID tuning section)
- Ziegler-Nichols: https://en.wikipedia.org/wiki/Ziegler%E2%80%93Nichols_method
- Relay Auto-Tuning: https://en.wikipedia.org/wiki/Relay_tuning

