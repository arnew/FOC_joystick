# Device Testing Guide for Agents

**Purpose**: Help agents quickly determine where and how testing is possible.

## Quick Start: Detect Available Testing

At the beginning of any session, run this to understand testing capabilities:

```bash
cd /home/arnew/Notebooks.st.rasentrimmer.org/FOC/rp2040_mini_as5600

# Detect local device and save config
bash .agentic/ci/local_device_detect.sh --save

# Source the config for environment variables
source .agentic/local_device.conf
echo "DEVICE_AVAILABLE=$DEVICE_AVAILABLE"
echo "CAN_TEST_LOCAL=$CAN_TEST_LOCAL"
```

## Testing Scenarios

### Scenario 1: Local Device Available

**Signs**:
- `DEVICE_AVAILABLE=true`  
- `CAN_TEST_LOCAL=true`
- Serial port appears as `/dev/ttyACM0` or `/dev/ttyUSB0`

**What you can do**:
```bash
# Run quality goals test suite
python3 test/quality_goals_test_suite.py
```

**Typical commands**:
- First time: Flash firmware with `platformio run -e pico_1motor_endless --target upload`
- Subsequent tests: Use CI (see Scenario 3)

### Scenario 2: Local Device Bootloader Mode

**Signs**:
- `DEVICE_BOOTSEL=true`
- Device shows as `/dev/RPI-RP2` mount point
- USB shows as `2e8a:0003` (bootloader)

**What to do**:
```bash
# Upload firmware to device
platformio run -e pico_1motor_endless --target upload

# Once upload completes, device resets and becomes available
# Run: bash .agentic/local_device_detect.sh  # Verify reset
```

### Scenario 3: No Local Device - Use CI

**Signs**:
- `DEVICE_AVAILABLE=false`
- `CAN_TEST_LOCAL=false`
- No serial ports found

**What to do**:
```bash
# Push changes and trigger CI hardware test
git add .
git commit -m "my changes"
git push origin dev

# Monitor CI hardware test
gh workflow run hardware-test.yml --ref dev
gh run list --workflow=hardware-test.yml

# Watch progress
for i in {1..20}; do 
    gh run list --workflow=hardware-test.yml -L 1 --json status
    sleep 10
done
```

### Scenario 4: Device Not Responding

**Signs**:
- Serial port exists but device not responding
- `DEVICE_AVAILABLE=true` but `CAN_TEST_LOCAL=false`

**Troubleshooting**:
```bash
# 1. Check physical connection
ls -la /dev/ttyACM0
# If missing: "Device not found - reconnect USB"

# 2. Try to read telemetry
timeout 2 cat /dev/ttyACM0
# Should see: A=0.00 T=0.00 lines every ~100ms

# 3. Check permissions
sudo usermod -a -G dialout $USER
# Must log out and back in

# 4. Reset device (press reset button if available)
# Then run detection again

# 5. If still stuck, use CI or check commit history
```

## Device Status File

After running detection, `.agentic/local_device.conf` contains:

```bash
DEVICE_PORT=/dev/ttyACM0
DEVICE_AVAILABLE=true
DEVICE_BOOTSEL=false
CAN_TEST_LOCAL=true
```

This file is **NOT committed** to git (ignored in `.gitignore`).

## CI Hardware Tests

The remote hardware runner (`hil-motor`) always has:
- ✓ RP2040 device attached
- ✓ PlatformIO installed  
- ✓ Python test framework ready
- ✓ All dependencies pre-installed

**Run CI test**:
```bash
gh workflow run hardware-test.yml --ref dev
```

**Monitor status**:
```bash
# Check job status
gh run view <run-id>

# View logs
gh run view --job <job-id> --log

# Extract test output
gh api /repos/arnew/FOC_joystick/actions/jobs/<id>/logs | \
  grep -E "Step [1-6]:|Motor movement|PASS|FAIL"
```

## Test Output Formats

### Local test output
```
MOTOR MOVEMENT TEST
============================================================
This test verifies SimpleFOC motor responds to commands

✓ Connected to /dev/ttyACM0

Step 1: Read initial motor angle (collecting 10 samples)
  Samples: 10
  Mean:    0.000 rad
  StdDev:  0.0012 rad
  Range:   [-0.002, 0.003]

Step 2: Command motor to 3.14 rad (180°)
  Sending: T3.14 (direct command)
  Response: T3.14
  Response: [CMD] Set target_angle[0] = 3.14

...

Step 6: Evaluate movement
  Initial mean:  0.000 ± 0.0012 rad
  Final mean:    2.847 ± 0.0045 rad
  Movement:      2.847 rad (163.1°)
  Target:        3.14 rad (180°)
  Error:         0.293 rad (16.8°)

✓ PASS: Motor IS responsive (moved significantly)
```

### CI test output
- Same format as local test
- Available via `gh run view --job <id> --log`
- Extracted with grep as shown above

## Decision Tree: Where to Test?

```
START
  ├─ Need quick feedback?
  │  └─ Device available locally?
  │     ├─ YES → Run local tests
  │     └─ NO → Use CI (slower, but reliable)
  │
  ├─ Making breaking changes?
  │  └─ Use CI to ensure basic health (5 simple tests)
  │  └─ Motor movement test will reveal control issues
  │
  ├─ Debugging motor behavior?
  │  └─ Attach local device
  │  └─ Modify test, run locally
  │  └─ Commit fix, verify in CI
  │
  └─ Just pushing code?
      └─ Use CI (automatic on push)
      └─ Check status: gh run list --workflow=hardware-test.yml
```

## Common Issues & Fixes

| Problem | Check | Fix |
|---------|-------|-----|
| "No serial ports" | `ls /dev/ttyACM*` | Reconnect USB, power on device |
| Permission denied | `ls -l /dev/ttyACM0` | `sudo usermod -a -G dialout $USER` |
| Device not responding | `cat /dev/ttyACM0` | Press reset, wait 2s, try again |
| Firmware too old | CI simple test fails | Update firmware: `platformio run...upload` |
| Motor won't move | CI movement test fails | Check PID tuning, wiring, motor init |

## Agent Workflow Summary

1. **Session start**:
   ```bash
   bash .agentic/ci/local_device_detect.sh --save
   source .agentic/local_device.conf
   ```

2. **Check capability**:
   ```bash
   if [ "$CAN_TEST_LOCAL" = true ]; then
       # Run local tests
       python3 test/quality_goals_test_suite.py
   else
       # Use CI testing
       gh workflow run hardware-test.yml --ref dev
   fi
   ```

3. **Iterate**:
   - Make code changes
   - Run appropriate test (local or CI)
   - Check results
   - Commit and push
   - Repeat

---

**See also**: 
- [ci/local_device_detect.sh](ci/local_device_detect.sh) - Detection script
- [ci/ci_device_detect.sh](ci/ci_device_detect.sh) - CI validation script
- [quality_goals_test_suite.py](../test/quality_goals_test_suite.py) - Active test suite
