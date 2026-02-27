# Agent Knowledge Base

**Purpose**: Graph database of agent knowledge for USB HID joystick controller with dual motorized axes and MIDI input.

**Status**: Living documentation updated with each development phase.

---

## Quick Navigation

```
.agentic/
├─ architecture/     System design, build procedures, code style
├─ tuning/          PID calibration (implementation + guides)
├─ quality/         Performance evaluation & fixes
├─ testing/         Hardware issues & test results
└─ sessions/        Development session notes
```

---

## Getting Started Paths

- **New to project?** → [architecture/PLANNING.md](architecture/PLANNING.md) → [architecture/QUICKSTART.md](architecture/QUICKSTART.md)
- **Need to build?** → [architecture/QUICKSTART.md](architecture/QUICKSTART.md)
- **Code refactoring?** → [architecture/REFACTORING_PLAN.md](architecture/REFACTORING_PLAN.md)
- **Tuning motors?** → [tuning/guides/DUAL_LOOP_TUNING.md](tuning/guides/DUAL_LOOP_TUNING.md)
- **GUI tuning?** → [tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md](tuning/implementation/SIMPLEFOC_STUDIO_PLAN.md) (SimpleFOC Studio)
- **Motor noisy/unstable?** → [quality/QUICK_FIX.md](quality/QUICK_FIX.md)
- **Real-time tuning?** → [tuning/guides/ONLINE_PARAMETER_TRANSFER.md](tuning/guides/ONLINE_PARAMETER_TRANSFER.md)
- **Fixing issues?** → [testing/TESTING_FINDINGS.md](testing/TESTING_FINDINGS.md)

---

## Current Status (February 2026)

**Development Model**: Git-flow with feature branches, experiments documented in sessions/

**Active Branches**:
| Branch | Status | Description |
|--------|--------|-------------|
| `feature/modularize-main` | ✅ Working baseline | SimpleFOC + knowledge base + CI framework |
| `feature/hid-report` | ✅ Ready for testing | Full HID+MIDI+SimpleFOC integration |
| `feature/tinyusb-minimal` | ✅ Completed | Minimal HID-only for bootloader isolation |
| `experiment/tinyusb_bootloader` | ✅ **BREAKTHROUGH** | Bootloader reentry verified working! |

**Recent Breakthrough** (2026-02-27):
- 🎯 **Bootloader reentry NOW WORKS** via automatic 1200bps DTR reset
- Was documented as critical blocker requiring manual BOOTSEL
- Multiple fix attempts failed (DTR callbacks, timing adjustments)
- Silently resolved by earlephilhower toolchain updates
- 5/5 sequential reboots successful in automated testing
- **Impact**: Fully automated CI/CD now possible without manual intervention

**Project State**:
- ✅ SimpleFOC motor control baseline working
- ✅ USB HID joystick implementation complete
- ✅ MIDI command parsing ready (skeleton present)
- ✅ TinyUSB configuration correct (HID + MIDI + CDC)
- ✅ Test infrastructure established (headless + hardware markers)
- ✅ Knowledge base comprehensive (all experiments documented)
- ⏳ Hardware integration testing pending (motor wiring on CI runner)
- ⏳ MSFS companion script integration (next phase)

**All Experiments Documented**: See [KNOWLEDGE_BASE.md#experiments](KNOWLEDGE_BASE.md#experiments-branch-history) for complete history across all branches

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
