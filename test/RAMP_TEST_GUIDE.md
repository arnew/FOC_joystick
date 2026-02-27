# Ramp Test & Calibration Workflow Guide

## Overview

The PID calibration script now includes a **3-phase workflow** for safe, intelligent motor tuning:

### Phase 1: Ramp Test (Sanity Check)
- **Purpose**: Verify motor responds to MIDI, detect hardware issues early
- **Duration**: ~4 seconds
- **Output**: Motor angle range, motor type (endless vs limited-range)
- **Command**: `python3 test/calibrate_pid.py --ramp-only`

### Phase 2: Relay Tuning (Ziegler-Nichols Calculation)
- **Purpose**: Inject square wave, measure oscillation, calculate PID gains
- **Duration**: ~5 seconds
- **Output**: Ku (ultimate gain), Pu (period), Kp/Ki/Kd values
- **Command**: `python3 test/calibrate_pid.py --relay-only`

### Phase 3: Step Response Validation (Tuning Check)
- **Purpose**: Measure rise time, overshoot, settling time with applied gains
- **Duration**: ~3 seconds
- **Output**: Overshoot %, settling time
- **Command**: `python3 test/calibrate_pid.py --step-only`

### Full Workflow
**Command**: `python3 test/calibrate_pid.py`

Runs all three phases sequentially, with early exit if hardware issues detected in Phase 1.

---

## Hardware Diagnostics

### Problem: Motor Not Responding to MIDI

If the ramp test shows **"MOTOR NOT RESPONDING"** (angle stays constant):

```
⚠️ MOTOR NOT RESPONDING TO MIDI:
  Angle stayed constant at 0.6283 rad during ramp
  Check:
    - Motor power supply
    - Encoder connection (I2C address 0x36)
    - Motor driver Enable pin (GPIO 10) is HIGH
    - SimpleFOC motor initialization (check serial output at startup)
```

**Troubleshooting steps**:

1. **Check motor power**: Verify 5V/12V supply to motor driver
   ```bash
   # Monitor device serial output
   timeout 3 python3 << 'EOF'
   import serial, time
   ser = serial.Serial("/dev/ttyACM0", 115200, timeout=1)
   time.sleep(0.5)
   ser.reset_input_buffer()
   for _ in range(30):
       if ser.in_waiting:
           print(ser.readline().decode().strip())
       time.sleep(0.1)
   ser.close()
   EOF
   ```

2. **Check encoder (I2C)**:
   - AS5600 should be on I2C bus (0x36)
   - Verify SDA/SCL pullups present
   - Check I2C connection with `i2cdetect` if available

3. **Check motor driver Enable pin (GPIO 10)**:
   - Should be HIGH when motor is running
   - Verify wiring: Motor 0 Enable → Pico GPIO 10

4. **Check SimpleFOC initialization**:
   - Look for initialization messages at startup
   - Verify `foc_current` loop running without errors

---

## Example Workflow: Full Calibration

### Step 1: Run Ramp Test (Sanity Check)
```bash
python3 test/calibrate_pid.py --ramp-only --debug
```

**Expected output** (motor working):
```
RAMP TEST: Motor 0
Duration: 4.0s, Serial output rate: ~1 Hz
Ramping CC#64: 0 → 127

✓ Collected 4 samples over 4.0s
  Angle range: 0.000 → 6.283 rad
  Total range: 6.283 rad (360.0°)
  Motor type: Endless

✓ Ramp test complete
  Motor type: Endless
```

### Step 2: Run Full Calibration
```bash
python3 test/calibrate_pid.py
```

**Expected sequence**:
1. Phase 1: Ramp test (verify motor responds)
2. Phase 2: Relay tuning (measure oscillation)
3. Phase 3: Step response (validate gains)
4. Display recommended Kp, Ki, Kd values

**Example output**:
```
[Phase 1/3] Sanity Check & Motor Characterization
✓ Ramp test complete (motor type: Endless)

[Phase 2/3] Ziegler-Nichols Relay Tuning
✓ Relay oscillation detected (Ku=1.5, Pu=0.8s)
✓ Ziegler-Nichols PID Gains (with 0.65 safety factor):
  Kp: 0.584999
  Ki: 1.170000
  Kd: 0.039000

[Phase 3/3] Step Response Validation
✓ Step response complete
  Overshoot: 3.2% (target: <5%)
  Settling Time: 0.85s (target: <1.5s)

CALIBRATION SUMMARY
✓ Recommended PID Gains:
  Kp = 0.584999
  Ki = 1.170000
  Kd = 0.039000
```

### Step 3: Apply Gains
```bash
# Edit include/pid_config.h with calculated values
nano include/pid_config.h

# Change:
#define MOTOR0_PID_P  0.584999f
#define MOTOR0_PID_I  1.170000f
#define MOTOR0_PID_D  0.039000f

# Rebuild and upload
platformio run -e pico_1motor_endless
platformio run -e pico_1motor_endless --target upload

# Test
bash test/run_tests.sh pico_1motor_endless
```

---

## Serial Output (1 Hz Monitor)

The device outputs debug info once per second (~1 Hz rate):

```
Angle: 0.6283 rad (36.0°) | Target: 6.1842 | USB: 512 (0-1023)
```

**Key fields**:
- **Angle**: Current motor position (radians, 4 decimals)
- **Target**: Setpoint from MIDI CC# command
- **USB**: Joystick output (0-1023 for USB HID)

The calibration script reads this output and parses the angle values for tuning.

---

## Tuning Results Interpretation

### Kp (Proportional Gain)
- Controls **responsiveness** to error
- Higher = faster response, but may overshoot
- Typical range: 0.1 - 2.0

### Ki (Integral Gain)
- Eliminates **steady-state error**
- Higher = faster error correction, but may cause oscillation
- Often 0.0 for position control (SimpleFOC only)
- Typical range: 0.0 - 1.0

### Kd (Derivative Gain)
- **Dampens oscillation** and reduces overshoot
- Higher = smoother, more stable response
- Too high = sluggish
- Typical range: 0.0 - 0.5

### Safety Factor (0.65x)
All calculated gains are multiplied by **0.65** for real hardware:
- Accounts for model mismatch
- Prevents aggressive tuning that could cause instability
- Can be adjusted in `calibrate_pid.py` after validation

---

## Troubleshooting

### "No motor response data" (Phase 1 fails)
- MIDI port not found → Check `pygame.midi` initialization
- Device not responding to MIDI → Check MIDI CC# 64 mapping in `config.h`
- Motor angle stuck → Motor power/encoder issue

### "Very few samples" or "Weak oscillation" (Phase 2 issues)
- Motor inertia too high → May need longer relay test (increase `duration`)
- PID gains too low → Motor doesn't oscillate enough
- Serial buffer overflow → Increase `timeout` in `read_debug_lines()`

### Overshoot too high after applying gains
- Reduce Kd (increase damping)
- Reduce Kp (decrease responsiveness)
- Check encoder resolution and filter settings

### Motor doesn't move at all
- Verify `foc_current` loop starts (check serial output at startup)
- Check motor wiring and phase ordering
- Verify PWM pins 13/12/11 connected correctly

---

## Configuration

**Calibration script defaults** (`test/calibrate_pid.py`):
- Ramp duration: 4.0s
- Relay frequency: 1.5 Hz (period: 0.67s)
- Relay amplitude: 10° → 90°
- Safety factor: 0.65x
- Step response time: 3.0s

**Motor config** (`src/config.h`):
- Voltage limit: 2.0V
- Angle filter: 10ms LPF
- Pin mapping: See hardware config section

**Firmware** (`src/main.cpp`):
- FOC loop: ~1 kHz
- Serial output: 1 Hz (115200 baud)
- USB HID output: 100 Hz

