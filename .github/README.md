# GitHub Actions CI/CD Setup

## Self-Hosted Runner Configuration

This repository uses a self-hosted GitHub runner with attached RP2040 hardware for automated testing.

### Workflows

1. **Hardware Test** (`.github/workflows/hardware-test.yml`)
   - Triggers: Push to `dev`, `feature/*` branches, PRs to `dev`/`main`
   - Runs on: `self-hosted` runner with `hardware` label
   - Steps:
     1. Build firmware (`platformio run`)
     2. Upload to device (`platformio run --target upload`)
     3. Run automated test suite (`test/run_ci_tests.sh`)
     4. Upload test artifacts

2. **Headless Test** (`.github/workflows/headless-test.yml`)
   - Triggers: Push to `dev`, `feature/*` branches, PRs to `dev`/`main`
   - Runs on: `ubuntu-latest` (GitHub-hosted)
   - Steps:
     1. Install Python dependencies (`pytest`, `pyserial`)
     2. Run `pytest -q` (hardware tests skipped)

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
- Runner has `hardware` label

### HIL Verification (Manual)

On the self-hosted runner with attached hardware:

```bash
platformio run -e pico_1motor_endless --target upload
SERIAL_PORT=/dev/ttyACM0 ./test/run_ci_tests.sh
```

Expected: `=== All tests passed ===` in output.

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

**Quick Setup** (recommended):
1. Clone this repository on the runner machine
2. Run the setup script:
   ```bash
   .github/setup-runner.sh
   ```
3. Log out and back in for group changes to take effect
4. Follow GitHub's runner installation instructions

**Manual Setup**:
1. **GitHub Settings** → **Actions** → **Runners** → **New self-hosted runner**
2. Follow setup instructions for Linux
3. Install dependencies:
   ```bash
   # Install system packages
   sudo apt-get update
   sudo apt-get install python3-serial python3-pygame pipx
   
   # Install PlatformIO via pipx (recommended for CLI tools)
   pipx install platformio
   pipx ensurepath
   
   # OR use pip with --break-system-packages (not recommended)
   # python3 -m pip install --user --break-system-packages platformio
   ```
4. Add user to `dialout` group for serial access:
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and back in for group change to take effect
   ```
5. Verify installation:
   ```bash
   platformio --version
   ls -l /dev/ttyACM0  # Should show device
   ```
6. Connect RP2040 device to `/dev/ttyACM0`
7. Start runner:
   ```bash
   ./run.sh
   ```

**Note**: Dependencies must be pre-installed on the self-hosted runner. PlatformIO installed via `pipx` goes to `~/.local/bin` which the workflow adds to PATH.

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
