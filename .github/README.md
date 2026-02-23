# GitHub Actions CI/CD Setup

## Self-Hosted Runner Configuration

This repository uses a self-hosted GitHub runner with attached RP2040 hardware for automated testing.

### Workflows

1. **Hardware Test** (`.github/workflows/hardware-test.yml`)
   - Triggers: Push to `dev`, `feature/*` branches, PRs to `dev`/`main`
   - Runs on: `self-hosted` runner
   - Steps:
     1. Build firmware (`platformio run`)
     2. Upload to device (`platformio run --target upload`)
     3. Run automated test suite (`test/run_ci_tests.sh`)
     4. Upload test artifacts

2. **Code Quality** (`.github/workflows/code-quality.yml`)
   - Triggers: Push to `dev`, `feature/*` branches, PRs to `dev`/`main`
   - Runs on: `ubuntu-latest` (GitHub-hosted)
   - Checks:
     - Function size compliance (≤43 lines per AGENTS.md)
     - Build compilation

### Runner Requirements

**Hardware:**
- RP2040 Pico connected via USB
- Device available at `/dev/ttyACM0`

**Software:**
- Python 3.11+
- PlatformIO Core
- pyserial, pygame (for MIDI testing)

### Test Suite

`test/run_ci_tests.sh` runs `test_suite_automated.py`:
- System identification
- Close-loop motor control
- Motor limits and scaling
- MIDI → HID joystick feedback

### Setting Up Self-Hosted Runner

1. **GitHub Settings** → **Actions** → **Runners** → **New self-hosted runner**
2. Follow setup instructions for Linux
3. Install dependencies:
   ```bash
   sudo apt-get update
   sudo apt-get install python3 python3-pip
   pip3 install platformio pyserial pygame
   ```
4. Add user to `dialout` group for serial access:
   ```bash
   sudo usermod -a -G dialout $USER
   ```
5. Connect RP2040 device to `/dev/ttyACM0`
6. Start runner:
   ```bash
   ./run.sh
   ```

### Environment Variables

- `SERIAL_PORT`: Serial port path (default: `/dev/ttyACM0`)

### Artifacts

Test results uploaded to GitHub Actions artifacts:
- `test/*.log` - Test execution logs
- `test/*.json` - Structured test results

## Local Testing

Run the same tests locally:
```bash
# Build and upload
platformio run -e pico_1motor_endless --target upload

# Run tests
./test/run_ci_tests.sh
```
