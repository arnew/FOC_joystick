# Planning Phase: Branch Consolidation & Next Steps

**Date**: 2026-02-27  
**Session**: Post-experiment synthesis and strategic planning  
**Author**: GitHub Copilot  
**Status**: 📋 Planning (awaiting human decision points)

---

## Executive Summary

All experiments completed. Bootloader blocker resolved. **Ready to merge `feature/hid-report` to dev and begin hardware integration testing.**

Key decision: Merge order and which branches to archive.

---

## 1. Merge Strategy Decision

### Recommended Path: Single Integration (Option C)

```bash
# Step 1: Ensure dev is current
git checkout dev
git pull origin dev

# Step 2: Merge feature/hid-report (most complete implementation)
git merge feature/hid-report --no-ff \
  -m "merge: Full HID+MIDI+SimpleFOC integration ready for testing"
git push origin dev

# Step 3: Archive completed experiments
git branch -d feature/tinyusb-minimal
git branch -d experiment/tinyusb_bootloader
git push origin --delete feature/tinyusb-minimal
git push origin --delete experiment/tinyusb_bootloader

# Step 4: Keep for reference
# feature/modularize-main (alternative approach baseline)
# usb-interfaces (MIDI experiment history)
```

**Why This Works**:
- ✅ All blockers resolved (bootloader verified)
- ✅ Most complete implementation (HID + MIDI + SimpleFOC)
- ✅ Knowledge base already on dev (no loss of documentation)
- ✅ Clean single merge point
- ✅ Reduces branch clutter

**What Gets Merged**:
- 727-line main.cpp with full integration
- TinyUSB HID joystick descriptor
- MIDI command dispatcher skeleton
- SimFOC baseline + motor control
- Test infrastructure (pytest + deployments script)

---

## 2. Branch Consolidation Plan

### Branches to Merge ✅
- **`feature/hid-report`** → `dev` (PRIMARY - ready now)

### Branches to Archive 📦
- **`feature/tinyusb-minimal`** → Close (isolation test complete)
  - Rationale: Served purpose (proved TinyUSB works, SimpleFOC wasn't blocker)
  - Keep as tag reference if needed: `git tag archive/isolation-test feature/tinyusb-minimal`

- **`experiment/tinyusb_bootloader`** → Close (hypothesis confirmed)
  - Rationale: Verification complete, findings documented in KNOWLEDGE_BASE.md
  - Keep as tag reference: `git tag archive/bootloader-verification experiment/tinyusb_bootloader`

### Branches to Keep 📚
- **`feature/modularize-main`** → Reference branch
  - Alternative baseline approach
  - Documents bootloader fix attempts (valuable for future troubleshooting)
  - Keep accessible but not active development

- **`usb-interfaces`** → Reference branch
  - MIDI integration history
  - Shows CDC vs Native MIDI exploration
  - Documentation value (lessons learned)

### Branches to Ignore ⏭️
- **`main`** → Stable baseline (don't touch)
- **`copilot-worktree-2026-02-23T05-51-02`** → Worktree artifact (can delete)
- **`feature/knowledge-base-foundation`** → Foundation already merged, can close

---

## 3. Next Steps by Priority

### 🚀 IMMEDIATE (This Sprint - Ready Now)

**Task 1: Merge to Dev**
```bash
git checkout dev
git merge feature/hid-report --no-ff
git push origin dev
```
- **Owner**: Agent
- **Effort**: 5 min
- **Blocker**: None
- **Success Criteria**: Merge clean, CI passes (code-quality + headless tests)
- **Status**: Ready to execute

**Task 2: Hardware Integration Test (CI Runner)**
```bash
# Push updated dev to GitHub
# Trigger hardware-test workflow manually
gh workflow run hardware-test.yml
```
- **Owner**: Agent (push) + Human (motor wiring verification)
- **Effort**: 30 min
- **Blocker**: Motor must be connected to CI runner, firmware must upload cleanly
- **Success Criteria**: 
  - ✅ Firmware builds without errors
  - ✅ Firmware uploads via automatic 1200bps reset (no manual BOOTSEL)
  - ✅ Motor spins (angle tracking shows `A=angle` output)
  - ✅ HID joystick enumerates (`/dev/input/js0` present or gamepad detected)
- **Status**: Ready after merge

**Task 3: Verify HID in Flight Sim**
- **Owner**: Human
- **Effort**: 15 min (if test hardware available)
- **Blocker**: Flight sim + USB device both needed
- **Success Criteria**: MSFS recognizes joystick, axis movement detected
- **Status**: Dependent on Task 2

---

### ⏭️ SHORT TERM (Next Sprint)

**Task 4: Implement MIDI Command Dispatcher**
- **Location**: `src/main.cpp` - `handle_midi_command()` function (skeleton present)
- **Scope**: Parse MIDI CC messages → motor commands
- **Definition**:
  ```cpp
  void handle_midi_command(uint8_t command, uint8_t control, uint8_t value) {
    // CC#7 (Throttle) → Motor 0 angle target
    // CC#5 (Flaps) → Motor 0 angle target  
    // CC#9 (Spoilers) → Motor 0 angle target
    // CC#10 (Trim) → Motor 1 angle target
    // CC#11 (Gear) → Motor 1 angle target
  }
  ```
- **Owner**: Agent
- **Effort**: 2 hours (logic + testing)
- **Blocker**: None
- **Success Criteria**:
  - ✅ MIDI CC received and parsed
  - ✅ Motor angle targets updated
  - ✅ Angle ranges correct (0-180° for throttle/flaps, 0-360° for trim)
  - ✅ Test: Send MIDI CC, verify motor moves
- **Status**: Ready (skeleton structure in place)

**Task 5: Dual Motor Wiring & Testing**
- **Location**: CI runner hardware setup
- **Scope**: Install second motor + encoder on CI runner
- **Owner**: Human (hardware) + Agent (testing)
- **Effort**: 1-2 hours (wiring + calibration)
- **Blocker**: Second motor + encoder hardware required
- **Success Criteria**:
  - ✅ Motor 0 angle tracking working
  - ✅ Motor 1 angle tracking working
  - ✅ Independent motor control functional
  - ✅ Dual MIDI CC mapping verified
- **Status**: Blocked on hardware availability

**Task 6: SimpleFOC Commander Integration**
- **Purpose**: Real-time PID tuning via serial commands
- **Implementation**: Add Commander object, enable terminal mode
- **Owner**: Agent
- **Effort**: 2 hours
- **Blocker**: None
- **Success Criteria**:
  - ✅ PID parameters readable via serial (`?` command)
  - ✅ PID parameters writable (`P1.2`, etc.)
  - ✅ Motor behavior tunable without recompile
- **Status**: Ready (SimpleFOC library already supports this)

---

### 📅 MEDIUM TERM (2-3 Weeks)

**Task 7: Settings Persistence (EEPROM/Flash)**
- **Purpose**: Save motor calibration + PID constants across power cycles
- **Scope**: 
  - EEPROM write: angle limits, PID gains, MIDI mappings
  - EEPROM read: restore on startup
- **Owner**: Agent
- **Effort**: 4-6 hours
- **Blocker**: None
- **Success Criteria**:
  - ✅ Settings stored in flash
  - ✅ Settings survive power cycle
  - ✅ Reset command available (factory defaults)
- **Status**: Design needed

**Task 8: Native USB MIDI Addition (Optional)**
- **Purpose**: Support direct MIDI tool connection (not just serial)
- **Scope**: Enable `CFG_TUD_MIDI` in tusb_config, poll `usb_midi.read()`
- **Trade-off**: Adds USB descriptor complexity, may break test harness again
- **Owner**: Agent (if pursued)
- **Effort**: 3-4 hours (implementation + test updates)
- **Blocker**: Design decision (CDC vs Native vs Hybrid)
- **Success Criteria**:
  - ✅ MIDI tools recognize native MIDI device
  - ✅ No test infrastructure regression
  - ✅ CDC MIDI still works (backward compat)
- **Status**: PostPoned pending design review

**Task 9: MSFS Companion Script (Python)**
- **Purpose**: Read MSFS sim data → send MIDI commands (e.g., throttle → pitch)
- **Scope**:
  - Connect to MSFS via SimConnect or UDP interface
  - Map sim variables to MIDI CCs
  - Send to Pico via USB serial
- **Owner**: Agent
- **Effort**: 8-10 hours
- **Blocker**: SimConnect library availability, MSFS running on dev machine
- **Success Criteria**:
  - ✅ Reads MSFS throttle/flaps/trim values
  - ✅ Converts to MIDI CC
  - ✅ Motors respond to sim commands
  - ✅ Latency <100ms
- **Status**: Design needed

---

### 🔮 LONG TERM (Future Enhancement)

**Task 10: Calibration Automation**
- Auto-detect servo limits
- Auto-tune PID gains
- Estimated effort: 8-12 hours

**Task 11: Haptic Feedback**
- Force feedback via motor vibration
- Estimated effort: 6-8 hours

**Task 12: Multi-Axis Expander**
- Support >2 motors via I2C/CAN daisy-chain
- Estimated effort: 12-16 hours

**Task 13: Wireless Option**
- BLE HID for standalone operation
- Estimated effort: 16-20 hours

---

## 4. Technical Decision Checkpoints

### Decision Point 1: After Task 2 (Hardware Test)
**If hardware test FAILS:**
- Check: Motor wiring correct?
- Check: Encoder I2C responsive?
- Check: encoder address matches config.h (0x36)?
- Check: SimpleFOC initialized without hanging?
- Fallback: Revert to `feature/modularize-main` baseline, debug incrementally

**If hardware test SUCCEEDS:**
- ✅ Proceed to Task 4 (MIDI dispatcher)
- Update GitHub Actions to remove manual BOOTSEL instructions
- Mark bootloader item as RESOLVED in documentation

### Decision Point 2: After Task 4 (MIDI Dispatcher)
**Test MIDI input:**
```bash
# Option A: Hardware test runner
RUN_HARDWARE_TESTS=1 pytest test/test_midi_cc.py

# Option B: Python script
python3 -c "import mido; m = mido.open_output(); \
  m.send(mido.Message('control_change', control=7, value=64))"
```
**If MIDI parsing works:**
- ✅ Proceed to Task 6 (Commander integration)
- Document MIDI CC mapping as working feature

**If MIDI parsing fails:**
- Debug: Check Serial1 baud rate (should be 31250)
- Debug: Check if CDC MIDI vs hardware serial MIDI
- Trace through dispatcher logic

### Decision Point 3: Native MIDI vs CDC Only
**Current approach**: CDC MIDI only (Serial1 @ 31250)
**Question**: Do we need native USB MIDI class?
- **Option A (CDC Only)**: Keep current, supports test harness, simpler
- **Option B (Add Native)**: Enable proper USB MIDI, needs test updates
- **Recommendation**: Decide after Task 4 succeeds

---

## 5. Success Criteria by Phase

### Phase 1: Merge ✅ (Immediate)
- [ ] `feature/hid-report` merged to dev
- [ ] Remote branches pushed
- [ ] Code quality CI passes
- [ ] Headless tests pass

### Phase 2: Hardware Integration ✅ (Immediate)
- [ ] Firmware uploads without manual BOOTSEL
- [ ] Motor angle tracking working
- [ ] HID joystick enumeration confirmed
- [ ] Serial debug output flowing

### Phase 3: MIDI Input ⏳ (Short Term)
- [ ] MIDI CC messages received
- [ ] Motor angle targets updated correctly
- [ ] Test harness validates dispatcher logic
- [ ] CC mapping documented

### Phase 4: Dual Motor (⏳ Medium Term)
- [ ] Second motor wired and detected
- [ ] Independent motor control working
- [ ] Dual MIDI mapping functional
- [ ] CI runner hardware test passes

### Phase 5: Settings Persistence ⏳ (Medium Term)
- [ ] Motor calibration saved to flash
- [ ] Settings restored after power cycle
- [ ] Reset-to-defaults command available

### Phase 6: Full Integration ✅ (Long Term)
- [ ] MSFS companion script reading sim data
- [ ] Throttle/flaps/trim responding to MSFS
- [ ] Latency within limits (<100ms)
- [ ] Haptic feedback (optional) working

---

## 6. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Hardware test fails | Low | Medium | Revert to modularize-main, debug incrementally |
| MIDI CC dispatcher logic wrong | Medium | Low | Unit tests before hardware test, trace serial output |
| Motor 2 wiring discovers new issues | Medium | Medium | Document issues, isolate SimpleFOC vs TinyUSB |
| CI runner connectivity drops | Low | Low | Keep local test setup as fallback |
| Test infrastructure breaks with native MIDI | Medium | High | Test backward compat thoroughly before merging |
| Flash space insufficient for settings | Low | Medium | Use EEPROM instead of flash, or compress config |

---

## 7. Git Workflow for Next Phase

**For Tasks 4-6 (MIDI + Commander + Dual Motor):**

```bash
# Create feature branch for MIDI work
git checkout dev
git pull
git checkout -b feature/midi-dispatcher

# Implement MIDI dispatcher
# Commit: "feat: implement MIDI CC dispatcher"

# Test locally
platformio run -e pico_1motor_endless

# Commit: "test: add MIDI CC parsing tests"

# Implement Commander
# Commit: "feat: add SimpleFOC Commander integration"

# Push and create PR for review
git push origin feature/midi-dispatcher

# After approval:
git checkout dev
git merge feature/midi-dispatcher --no-ff
```

**For Tasks 7+ (Settings, Native MIDI, MSFS):**
- Create experiment branches (not feature)
- Document hypothesis before starting
- Confirmation commit after successful testing
- Archive if abandoned, merge if successful

---

## 8. Known Unknowns Requiring Decision

### 1. Native USB MIDI: Now or Later?
- **Now**: Enable in tusb_config, update test harness (costs ~4 hours)
- **Later**: Keep CDC-only for stability, add native in next iteration (safer)
- **Recommendation**: **Later** (validate current implementation first)

### 2. SimpleFOC Commander: Serial or USB?
- **Serial**: Use CDC serial (simple, already working)
- **USB**: Proper USB control interface (more complex)
- **Recommendation**: **Serial** (fastest to implement)

### 3. Settings Persistence: Flash or EEPROM?
- **Flash**: Larger space, but slower writes (erases whole page)
- **EEPROM**: Slower speed, but byte-level writes
- **Recommendation**: **EEPROM** (simpler, sufficient for config size)

### 4. Dual Motor CI Runner: How to Test?
- **Option A**: Connect second motor + encoder to CI runner
- **Option B**: Mock second motor, test logic only
- **Recommendation**: **Option A** (full integration testing)

### 5. MSFS Companion: SimConnect or UDP?
- **SimConnect**: Official, requires Windows + SimConnect DLL
- **UDP**: Third-party tools (VPilot, FSUIPC UDP bridge)
- **Recommendation**: **UDP** (cross-platform, simpler setup)

---

## 9. Checkpoints for Human Review

Print this section for manual review before each phase:

### Before Task 1 (Merge):
- [ ] Have you reviewed the diff? (`git diff --stat dev feature/hid-report`)
- [ ] Are you comfortable with any code style changes?
- [ ] Should we create a backup tag? (`git tag pre-hid-merge dev`)

### Before Task 2 (Hardware Test):
- [ ] Is the CI runner hardware ready (motor connected)?
- [ ] Do you want to observe the first upload live?
- [ ] Should we record metrics for later analysis?

### Before Task 4 (MIDI Dispatcher):
- [ ] Which MIDI CC mapping? (throttle→7, flaps→5, etc.?)
- [ ] Angle range for each control? (0-180°? 0-360°?)
- [ ] Test with real MIDI source or simulated?

### Before Task 6 (Commander):
- [ ] Acceptable tuning window? (max PID change per step?)
- [ ] Store in RAM only (temporary) or persist?

---

## Summary

**Current State**: All experiments complete, blocker resolved, ready to merge.

**Next Action**: Human review → Approve merge → Execute Tasks 1-2 → Iterate.

**Timeline**: 
- Immediate (Task 1-2): 1-2 days
- Short term (Task 4-6): 1-2 weeks
- Medium term (Task 7-9): 2-4 weeks
- Long term (Task 10+): As needed

**Branch status after execution**:
```
main (stable)
└─ dev (active, merged hid-report)
   ├─ feature/midi-dispatcher (Task 4)
   ├─ feature/commander-integration (Task 6)
   └─ [future experiments]

[archived]
├─ feature/tinyusb-minimal (tag: archive/isolation-test)
├─ experiment/tinyusb_bootloader (tag: archive/bootloader-verification)
└─ [reference branches]
   ├─ feature/modularize-main (alternative baseline)
   └─ usb-interfaces (MIDI history)
```

---

**Document Version**: v1.0  
**Last Updated**: 2026-02-27 12:45 UTC  
**Status**: 📋 Awaiting human approval to proceed with merge
