# GitHub Actions Workflows

This directory contains CI/CD workflows for the FOC Joystick project.

## Workflows Overview

### 1. Build (`build.yml`)
**Trigger**: Push/PR to dev, main, feature/*, hotfix/*

**Purpose**: Compile firmware for all hardware configurations

**What it does**:
- Builds firmware for all environments (endless, limited, dual-motor)
- Checks firmware size limits
- Caches PlatformIO dependencies
- Uploads firmware artifacts (retained 30 days)

**Environments tested**:
- `pico_1motor_endless` - Single motor, 360° rotation
- `pico_1motor_limited` - Single motor, 0-180° range  
- `pico_2motor_limited` - Dual motors, both limited

**Success criteria**: All environments compile without errors

---

### 2. Code Quality (`code-quality.yml`)
**Trigger**: Push/PR to dev, main, feature/*, hotfix/*

**Purpose**: Validate code style and documentation completeness

**Checks performed**:
- C++ style linting (cpplint)
- TODO/FIXME marker detection
- Debug print statement checks
- Documentation file presence (KNOWLEDGE_BASE.md, README.md, etc.)
- README completeness (essential sections)
- platformio.ini validation (environments, dependencies)
- Configuration file structure (TinyUSB config flags)
- Hardcoded value detection (baud rates, I2C addresses)

**Non-blocking**: Warnings don't fail the workflow, but are reported

---

### 3. Hardware Integration Test (`hardware-test.yml`)
**Trigger**: 
- Push to `dev` or `feature/**` branches (automatic)
- Manual dispatch with custom parameters
- Nightly schedule (2 AM UTC)

**Purpose**: Test firmware on actual hardware (self-hosted runner with motor)

**Requirements**:
- Self-hosted runner with:
  - RP2040 Pico connected via USB
  - Motor + AS5600 encoder wired (for motor tests)
  - Python 3 + PlatformIO installed
  - Linux OS (uses /dev/ttyACM*, /dev/input/js*)

**Test sequence**:
1. Build firmware
2. Upload to hardware (automatic reset or manual BOOTSEL)
3. Verify serial port enumeration
4. Capture serial output (5 seconds)
5. Check HID joystick enumeration
6. Test motor angle tracking (if endless motor environment)

**Auto-run behavior** (push/schedule):
- Always tests `pico_1motor_endless` (matches runner hardware)
- Always uploads fresh firmware
- Provides fast feedback on each code change

**Manual trigger inputs** (workflow_dispatch):
- `environment`: Which config to test (default: pico_1motor_endless)
- `skip_upload`: Test existing firmware without re-uploading (advanced)

**Success criteria**:
- ✅ Firmware builds
- ✅ Upload succeeds (ideally automatic)
- ✅ Serial port appears (/dev/ttyACM*)
- ✅ Serial output contains expected patterns ("Motor", "A=", etc.)
- ✅ HID joystick device enumerated (/dev/input/js*)
- ✅ Motor angle data streaming (for motor configs)

---

### 4. Deploy to Hardware (`deploy.yml`)
**Trigger**: Manual dispatch only

**Purpose**: Quick firmware deployment to connected hardware (single motor, endless config)

**Requirements**:
- Self-hosted runner with tag: `pico_1motor_endless`
- RP2040 Pico connected via USB
- Motor + AS5600 encoder (endless/360° configuration)

**What it does**:
1. Builds firmware for selected environment
2. Uploads firmware to hardware
3. Verifies device enumeration (serial port, HID joystick, USB)
4. Quick serial output check (3 seconds)
5. Deployment status summary

**Manual trigger inputs**:
- `environment`: Which config to deploy (default: pico_1motor_endless)
- `force_manual_bootsel`: Skip automatic reset, require manual BOOTSEL button

**Use cases**:
- Quick firmware updates during development
- Deploy after merging features to dev
- Test firmware on actual hardware before release

**vs hardware-test.yml**:
- `deploy.yml`: Fast deployment + basic verification (~2-3 minutes)
- `hardware-test.yml`: Full integration test suite (~10-15 minutes)

---

### 5. Pull Request Validation (`pr-validation.yml`)
**Trigger**: PR opened/updated targeting dev or main

**Purpose**: Comprehensive PR validation before merge

**Checks performed**:
1. **Branch naming**: Git-flow convention (feature/*, hotfix/*, etc.)
2. **Commit messages**: Conventional commit format (feat:, fix:, etc.)
3. **Merge conflicts**: Detection with base branch
4. **File size limits**: Warns on files >1MB
5. **Build**: Calls build.yml workflow
6. **Code Quality**: Calls code-quality.yml workflow

**Result**: Summary table with all check statuses

**Blocking**: Build and code-quality must pass; others warn only

---

### 6. Release (`release.yml`)
**Trigger**: Push tag `v*.*.*` OR manual dispatch with version input

**Purpose**: Create GitHub release with firmware binaries

**Process**:
1. Generate changelog (commits since last tag)
2. Create GitHub release (draft=false)
3. Build firmware for all environments
4. Package each build:
   - `.uf2` file (for BOOTSEL upload)
   - `.elf` file (for debugging)
   - `README.txt` (installation instructions)
   - `.zip` archive (all of above)
5. Upload all packages as release assets

**Output artifacts**:
```
firmware-pico_1motor_endless-v1.0.0.zip
firmware-pico_1motor_limited-v1.0.0.zip
firmware-pico_2motor_limited-v1.0.0.zip
```

**Manual dispatch**: Allows creating releases without pushing tags

---

## Usage Examples

### Deploy firmware to hardware
```bash
# Quick deployment (automatic reset)
gh workflow run deploy.yml \
  --field environment=pico_1motor_endless

# Deploy with manual BOOTSEL
gh workflow run deploy.yml \
  --field environment=pico_1motor_endless \
  --field force_manual_bootsel=true
```

### Run hardware test manually
```bash
gh workflow run hardware-test.yml \
  --field environment=pico_1motor_endless \
  --field skip_upload=false
```

### Create a release
```bash
# Via tag
git tag v1.0.0
git push origin v1.0.0

# Via manual dispatch
gh workflow run release.yml --field version=v1.0.0
```

### Check workflow status
```bash
gh run list --workflow=build.yml
gh run watch  # Watch latest run
```

---

## Self-Hosted Runner Setup

For hardware testing and deployment, you need a self-hosted runner with the `pico_1motor_endless` tag:

### Requirements
- Linux machine (Ubuntu/Debian recommended)
- RP2040 Pico connected via USB
- Motor + AS5600 encoder wired (endless/360° configuration)
- Python 3.8+
- USB permissions configured
- Runner tagged with: `pico_1motor_endless`

### Installation
```bash
# On the runner machine:
# 1. Install dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv udev

# 2. Configure USB permissions
sudo usermod -a -G dialout $USER
sudo usermod -a -G plugdev $USER

# 3. Install PlatformIO
pip3 install --user platformio

# 4. Download and configure GitHub Actions runner
# (Follow instructions from repo Settings → Actions → Runners → Add runner)
# IMPORTANT: When adding labels, include: self-hosted,Linux,X64,pico_1motor_endless

# 5. Start runner
./run.sh
```

### Adding the "pico_1motor_endless" tag
The runner must have the `pico_1motor_endless` label to be selected by deploy.yml and hardware-test.yml.
This label identifies the specific hardware configuration (single motor, endless/360° rotation).

Add it during initial setup or update existing runner:
```bash
# During setup:
./config.sh --url https://github.com/USER/REPO --token TOKEN --labels self-hosted,Linux,X64,pico_1motor_endless

# Or via GitHub UI:
# Settings → Actions → Runners → [Your Runner] → Edit labels → Add "pico_1motor_endless"
```

**Future configurations**: When you add runners with different hardware (e.g., `pico_2motor_limited`),
use matching labels so workflows can target the correct hardware.

### Testing runner
```bash
# Verify Pico detection
lsusb | grep 2e8a

# Check serial ports
ls -l /dev/ttyACM*

# Test PlatformIO
platformio --version
```

---

## Workflow Dependencies

```
pr-validation.yml
├── validate-pr (branch/commit checks)
├── build.yml (firmware compilation)
└── code-quality.yml (linting & docs)

release.yml
├── create-release (tag & changelog)
└── build-release-firmware (all environments)

deploy.yml (standalone, self-hosted with "pico_1motor_endless" tag)

hardware-test.yml (standalone, self-hosted with "pico_1motor_endless" tag)
```

---

## Caching Strategy

PlatformIO dependencies are cached to speed up builds:
- Cache key: `${{ runner.os }}-pio-${{ hashFiles('platformio.ini') }}`
- Cached paths: `~/.platformio`, `.pio`
- Cache invalidation: When platformio.ini changes

---

## Artifacts Retention

| Workflow | Artifact | Retention |
|----------|----------|-----------|
| build.yml | Firmware binaries | 30 days |
| hardware-test.yml | Test logs | 7 days |
| release.yml | Release packages | Permanent (on release) |

---

## Troubleshooting

### Build fails with "Library not found"
- Check `platformio.ini` lib_deps section
- Clear cache: Delete `.pio` folder and retry

### Hardware test times out on upload
- Runner may need manual BOOTSEL button press
- Check USB cable and power supply
- Verify runner has USB permissions

### Self-hosted runner offline
- Check runner service: `./run.sh` status
- Verify network connectivity to GitHub
- Check runner token hasn't expired

### Release workflow fails
- Ensure tag follows `v*.*.*` format
- Check GitHub token permissions (Settings → Actions → General)
- Verify all environments compile successfully

---

## Configuration Files

Related configuration files:
- `platformio.ini` - Build environments and dependencies
- `include/my_tusb_config.h` - TinyUSB configuration
- `src/config.h` - Application configuration
- `.agentic/KNOWLEDGE_BASE.md` - Technical documentation

---

## Future Improvements

Potential workflow enhancements:
- [ ] Unit tests (when test suite exists)
- [ ] MIDI regression tests (send CC, verify motor response)
- [ ] Performance benchmarks (FOC loop frequency)
- [ ] Code coverage reporting
- [ ] Automated documentation generation (Doxygen)
- [ ] Multi-runner hardware tests (different Pico variants)
- [ ] Simulation-based tests (virtual motor + encoder)

---

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [PlatformIO CI Guide](https://docs.platformio.org/en/latest/integration/ci/index.html)
- [Self-hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- Project knowledge base: `.agentic/KNOWLEDGE_BASE.md`
