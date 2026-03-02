# Online PID Parameter Transfer - User Guide

## Quick Start

With online parameter transfer, you can adjust PID gains in real-time without recompiling!

### Step 1: Connect to Serial Console
```bash
# Open serial monitor at 115200 baud (debug port)
python3 -c "
import serial
ser = serial.Serial('/dev/ttyACM0', 115200)
while True:
    ch = ser.read(1)
    if ch:
        print(ch.decode('utf-8', errors='ignore'), end='')
"
```

Or use any serial terminal:
```bash
# minicom
minicom -D /dev/ttyACM0 -b 115200

# picocom
picocom /dev/ttyACM0 -b 115200
```

### Step 2: View Current Gains
```bash
SHOW
# or
GET
```

Output:
```
=== Current PID Gains ===
Motor 0
  Angle:    Kp=20.000000  Ki=0.000000  Kd=0.500000
  Velocity: Kp=0.125000  Ki=10.000000  Kd=0.000000
Motor 1
  Angle:    Kp=20.000000  Ki=0.000000  Kd=0.500000
  Velocity: Kp=0.125000  Ki=10.000000  Kd=0.000000
```

### Step 3: Adjust a Gain
```bash
# Set Motor 0 angle Kp to 8.257
PID 0 P 8.257

# Set Motor 0 velocity Ki to 31.561
VEL 0 I 31.561

# Set Motor 0 angle damping (Kd)
PID 0 D 2.5
```

The gain is **applied immediately** - no reboot needed!

### Step 4: Evaluate Quality
In another terminal, run the quality test:
```bash
python3 test/calibrate_pid.py --motor 0 --step-only
```

This tests the motor with current gains and shows:
- Quality Score (0-100)
- Overshoot, settling time, noise, drift, stability

### Step 5: Iterate
```
Terminal 1 (Serial Monitor):
> PID 0 P 10.0
Motor 0 Angle Kp = 10.000000
Motor 0 gains updated

Terminal 2 (Test):
$ python3 test/calibrate_pid.py --motor 0 --step-only
  Quality Score: 72.5/100
  Position Noise: 0.45°
  ...
```

Repeat steps 3-4 until happy with quality.

## Command Reference

### Set Gains

```
PID <motor> <P|I|D> <value>
  
  motor: 0 or 1 (which motor to adjust)
  P|I|D: Proportional, Integral, or Derivative
  value: Floating point (e.g., 8.257 or 10.0)

Examples:
  PID 0 P 8.257       # Motor 0 angle Kp = 8.257
  PID 0 I 31.197      # Motor 0 angle Ki = 31.197  
  PID 0 D 0.546       # Motor 0 angle Kd = 0.546
```

```
VEL <motor> <P|I|D> <value>

  motor: 0 or 1
  P|I|D: Proportional, Integral, or Derivative (velocity loop)
  value: Floating point

Examples:
  VEL 0 P 5.440       # Motor 0 velocity Kp = 5.440
  VEL 0 I 31.561      # Motor 0 velocity Ki = 31.561
  VEL 0 D 0.234       # Motor 0 velocity Kd = 0.234
```

### View Gains

```
SHOW
GET

Shows all current gains for both motors and both loops (angle + velocity).
```

### Force Apply

```
APPLY <motor>

  motor: 0 or 1

Forces all stored gains to be written to the SimpleFOC controller.
Usually not needed (automatic on each PID/VEL command).
```

## Typical Tuning Session

```bash
# Terminal 1: Serial Console
$ minicom -D /dev/ttyACM0 -b 115200

(connected to motor)
> SHOW
=== Current PID Gains ===
Motor 0
  Angle:    Kp=20.000000  Ki=0.000000  Kd=0.500000
  Velocity: Kp=0.125000  Ki=10.000000  Kd=0.000000
```

```bash
# Terminal 2: Quality Test
$ python3 test/calibrate_pid.py --motor 0 --step-only
Quality Score: 87.6/100 (EXCELLENT)
Position Noise: 0.37°
Position Drift: 0.57°
Stability: 100%
```

See tremor is low but settling is slow. Increase Kp:

```bash
# Terminal 1:
> PID 0 P 12.0
Motor 0 Angle Kp = 12.000000
Motor 0 gains updated
```

```bash
# Terminal 2:
$ python3 test/calibrate_pid.py --motor 0 --step-only
Quality Score: 78.3/100 (GOOD)
Position Noise: 0.42°
Settling Time: 2.5s (improved!)
```

Settling improved but noise increased slightly. Maybe Kd needs adjustment:

```bash
# Terminal 1:
> PID 0 D 1.0
Motor 0 Angle Kd = 1.000000
Motor 0 gains updated
```

```bash
# Terminal 2:
$ python3 test/calibrate_pid.py --motor 0 --step-only
Quality Score: 82.1/100 (EXCELLENT)
Position Noise: 0.38°
Settling Time: 2.3s
```

Good! Found a better point. Continue exploring...

## Scripted Tuning

You can automate parameter sweep using Python:

```python
import serial
import time

ser = serial.Serial('/dev/ttyACM0', 115200)
time.sleep(1)

# Try different Kp values
for kp in [8.0, 10.0, 12.0, 14.0, 15.0]:
    cmd = f"PID 0 P {kp}\r\n"
    ser.write(cmd.encode())
    time.sleep(0.5)
    
    print(f"Testing Kp={kp}...")
    # Run quality test in another process
    # os.system(f"python3 test/calibrate_pid.py --motor 0 --step-only")
    
ser.close()
```

Then integrate with calibrate_pid.py to automate full tuning sweep!

## Limitations

- **Runtime only**: Gains don't persist after power cycle (reset to pid_config.h)
- **Motor 1**: Placeholder values; needs hardware setup first
- **No EEPROM**: To save tuned values, edit pid_config.h manually

## Next Steps

Once you find good gains:

1. **Transfer to firmware**:
   ```cpp
   // Edit include/pid_config.h
   #define MOTOR0_PID_P 12.0   // Your new value
   #define MOTOR0_PID_D 1.0    // Your new value
   ```

2. **Rebuild and upload**:
   ```bash
   platformio run -e pico_1motor_limited --target upload
   ```

3. **Verify persistence**:
   ```bash
   python3 test/calibrate_pid.py --motor 0 --step-only
   ```

## Troubleshooting

**"ERROR: Unknown command"**
- Check spelling and format: `PID 0 P 8.257` (space-separated)
- Use uppercase for command: `PID`, `VEL`, `SHOW`

**"ERROR: Format is 'PID <motor_id 0-1> <P|I|D> <value>'"**
- Missing or invalid parameter
- Motor ID must be 0 or 1
- Gain must be P, I, or D (uppercase)

**Gain changes don't take effect**
- Motor might be moving; wait for it to settle
- Try `APPLY 0` to force application
- Restart if still not working

**Serial port not found**
- Check USB connection: `ls /dev/ttyACM*`
- Try replugging the RP2040
- Check dmesg for enumeration errors

## Related

See [TUNING_QUALITY_ANALYSIS.md](TUNING_QUALITY_ANALYSIS.md) for:
- Detailed explanation of each quality metric
- Trade-offs between Kp, Ki, Kd
- Root cause analysis for tuning issues
- Hardware troubleshooting (encoder, power supply)

See [../../quality/QUICK_FIX.md](../../quality/QUICK_FIX.md) for:
- Recommended starting gains
- Common tuning patterns
- When to adjust each parameter
