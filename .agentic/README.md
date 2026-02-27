# Agent Knowledge Base

**Purpose**: Graph database of agent knowledge for USB HID joystick controller with dual motorized axes and MIDI input.

**Status**: Living documentation updated with each development phase.

---

## Quick Navigation

```
.agentic/
├─ architecture/     System design, build procedures, code style
├─ ci/               GitHub workflows, `gh` CLI, CI monitoring
├─ tuning/          PID calibration (implementation + guides)
├─ quality/         Performance evaluation & fixes
├─ testing/         Hardware issues & test results
└─ sessions/        Development session notes
```

---

## Getting Started Paths

- **New to project?** → [architecture/PLANNING.md](architecture/PLANNING.md) → [architecture/QUICKSTART.md](architecture/QUICKSTART.md)
- **Need to build?** → [architecture/QUICKSTART.md](architecture/QUICKSTART.md)
- **Testing & CI workflow?** → [ci/GITHUB_INTEGRATION.md](ci/GITHUB_INTEGRATION.md)
- **Code refactoring?** → [architecture/REFACTORING_PLAN.md](architecture/REFACTORING_PLAN.md)
- **Tuning motors?** → [tuning/guides/DUAL_LOOP_TUNING.md](tuning/guides/DUAL_LOOP_TUNING.md)
- **GUI tuning?** → [tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md](tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md) (SimpleFOC Studio)
- **Motor noisy/unstable?** → [quality/QUICK_FIX.md](quality/QUICK_FIX.md)
- **Real-time tuning?** → [tuning/guides/ONLINE_PARAMETER_TRANSFER.md](tuning/guides/ONLINE_PARAMETER_TRANSFER.md)
- **Fixing issues?** → [testing/TESTING_FINDINGS.md](testing/TESTING_FINDINGS.md)

---

## Current Status (February 2026)

- ✅ Dual-loop PID tuning implemented
- ✅ Quality evaluation system (72.9/100 after fixes)
- ✅ Online parameter transfer working
- 🔄 Code refactoring planned (main.cpp 727→80 lines)
- 🔄 SimpleFOC Studio integration planned (replace custom protocol)
- ⚠️ Motor reliability issues identified (see [sessions/](sessions/))
- 🔄 4/6 automated tests passing
- ✅ Headless pytest gated by `RUN_HARDWARE_TESTS=1`

---

## Key Documents by Use Case

| Use Case | Primary Reference |
|----------|------------------|
| System architecture | [architecture/PLANNING.md](architecture/PLANNING.md) |
| Build & upload firmware | [architecture/QUICKSTART.md](architecture/QUICKSTART.md) |
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
