# Agent Knowledge Base

**Purpose**: Graph database of agent knowledge for USB HID joystick controller with dual motorized axes and MIDI input.

**Status**: Living documentation updated with each development phase.

---

## ⚠️ START HERE (Required Reading)

**Before starting any work, read these in order:**

1. **[PURPOSE.md](PURPOSE.md)** - Project goals, hardware, success criteria
2. **[AGENT_GUIDELINES.md](AGENT_GUIDELINES.md)** - How agents should behave, decision framework, anti-patterns
3. **[KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md)** - Working baseline, known issues, technical details

---

## Quick Navigation

```
.agentic/
├─ PURPOSE.md                        ⭐ What this project is
├─ AGENT_GUIDELINES.md               ⭐ How agents work
├─ KNOWLEDGE_BASE.md                 ⭐ Technical baseline
├─ FAILED_EXPERIMENTS.md             📚 What didn't work (PID tuning, dual-motor)
├─ REMOVED_UNTESTED_CODE.md          📚 Code cleanup history
├─ USB_STABILITY_ISSUE.md            🔧 USB bandwidth fix details
├─ DEVICE_TESTING.md                 🧪 How to run tests (device detection)
├─ MOTOR_DEBUGGING_SESSION.md        🔧 Current motor control issue
├─ local_device_detect.sh            🛠️ Detect local RP2040 device
├─ ci_device_detect.sh               🛠️ Validate CI hardware runner
├─ architecture/                     System design, build procedures
├─ ci/                               GitHub workflows, `gh` CLI
├─ tuning/                           SimpleFOC integration guides
├─ testing/                          Hardware issues & test results
└─ sessions/                         Development session notes
```

---

## Getting Started Paths

- **New to project?** → [PURPOSE.md](PURPOSE.md) → [AGENT_GUIDELINES.md](AGENT_GUIDELINES.md) → [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md)
- **Need to build?** → [KNOWLEDGE_BASE.md#working-baseline](KNOWLEDGE_BASE.md#working-baseline)
- **Want to run tests?** → [DEVICE_TESTING.md](DEVICE_TESTING.md) (decide local vs CI)
- **Testing & CI workflow?** → [ci/GITHUB_INTEGRATION.md](ci/GITHUB_INTEGRATION.md)
- **Motor not moving?** → [MOTOR_DEBUGGING_SESSION.md](MOTOR_DEBUGGING_SESSION.md)
- **Code refactoring?** → [architecture/REFACTORING_PLAN.md](architecture/REFACTORING_PLAN.md)
- **Tuning motors?** → [tuning/guides/DUAL_LOOP_TUNING.md](tuning/guides/DUAL_LOOP_TUNING.md)
- **GUI tuning?** → [tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md](tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md)
- **What experiments failed?** → [FAILED_EXPERIMENTS.md](FAILED_EXPERIMENTS.md)
- **What code was removed?** → [REMOVED_UNTESTED_CODE.md](REMOVED_UNTESTED_CODE.md)
- **Fixing issues?** → [testing/TESTING_FINDINGS.md](testing/TESTING_FINDINGS.md)

---

## Current Status (February 2026)

**Latest Session** (2026-02-28):
- ✅ **FIRST SUCCESSFUL CI TEST** - All 5 basic hardware tests passing
- ✅ SimpleFOC Commander integration complete (status queries working)
- ✅ Telemetry rate increased to 10Hz (from 1Hz)
- ✅ Statistical sampling in tests (10 samples, mean ± stddev)
- ✅ Device detection infrastructure (local + CI)
- ❌ **BLOCKER: Motor target not executing** - Receives commands but doesn't move
- ✅ Code quality: All functions ≤ 43 lines (KISS principle)

**Overall Project**:
- ✅ Dual-loop PID tuning implemented
- ✅ Quality evaluation system (72.9/100 after fixes)
- ✅ Online parameter transfer working
- ✅ SimpleFOC Commander interface ready
- 🔄 Motor control physics debugging in progress
- 🔄 Code refactoring planned (main.cpp 727→80 lines)
- 🔄 4/6 automated tests passing (5/5 basic, but movement test needs fixing)
- ✅ Headless pytest gated by `RUN_HARDWARE_TESTS=1`

**See**: [MOTOR_DEBUGGING_SESSION.md](MOTOR_DEBUGGING_SESSION.md) for detailed blocker analysis and next steps.

---

## Key Documents by Use Case

| Use Case | Primary Reference |
|----------|------------------|
| System architecture | [architecture/PLANNING.md](architecture/PLANNING.md) |
| Build & upload firmware | [architecture/QUICKSTART.md](architecture/QUICKSTART.md) |
| Running tests (local/CI) | [DEVICE_TESTING.md](DEVICE_TESTING.md) |
| Debugging motor control | [MOTOR_DEBUGGING_SESSION.md](MOTOR_DEBUGGING_SESSION.md) |
| Code refactoring plan | [architecture/REFACTORING_PLAN.md](architecture/REFACTORING_PLAN.md) |
| Code style guidelines | [architecture/README.md](architecture/README.md) |
| Calibrate motor | [tuning/guides/DUAL_LOOP_TUNING.md](tuning/guides/DUAL_LOOP_TUNING.md) |
| GUI tuning (planned) | [tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md](tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md) |
| Real-time tuning | [tuning/guides/ONLINE_PARAMETER_TRANSFER.md](tuning/guides/ONLINE_PARAMETER_TRANSFER.md) |
| Fix noisy motor | [quality/QUICK_FIX.md](quality/QUICK_FIX.md) |
| Understand test failures | [testing/TEST_RESULTS.md](testing/TEST_RESULTS.md) |
| Latest implementation | [tuning/implementation/DUAL_LOOP_IMPLEMENTATION.md](tuning/implementation/DUAL_LOOP_IMPLEMENTATION.md) |

---

## File Naming Conventions

- `README.md` - Folder index (required in each folder)
- `IMPLEMENTATION.md` - Technical implementation details
- `GUIDE.md` / `TUNING.md` - User-facing how-to docs
- `RESULTS.md` / `FINDINGS.md` - Measurement data & observations
- `SUMMARY.md` - Session/feature summaries
