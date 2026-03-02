# Hardware Test Automation Issues

**Status**: Known issue - CI hardware tests unreliable, manual testing required  
**Date Identified**: 2026-02-28  
**Priority**: Medium (workaround available)

## Problem Summary

CI hardware tests fail consistently since Feb 27, 21:07 (commit 5052b1b), but **manual testing works**. Investigation reveals this is a **CI infrastructure issue**, not motor control code issue.

## Evidence

### Timeline
- **Feb 27, 18:15-18:20**: Last successful CI hardware tests (commits b0871be, e1f45f6)
- **Feb 27, 21:07+**: 40+ consecutive CI hardware test failures
- **Feb 28, 00:00-00:50**: Aircraft profile implementation - builds pass, code quality pass, headless tests pass
- **Feb 28, 00:12**: Experiment baseline (e1f45f6) also fails in CI

### Test Behavior Comparison

| Scenario | MIDI Target (T) | Motor Angle (A) | Interpretation |
|----------|----------------|-----------------|----------------|
| **Experiment baseline (e1f45f6) in CI** | 0.00 | 0.00 | Device not receiving MIDI - firmware not running properly |
| **Modern dev in CI** | 6.28 | 0.00 | MIDI received, motor init ran, but motor stuck |
| **Manual test by user** | 6.28 | moves | **Works correctly** |

### Key Finding

**User observation**: "Tests only worked when I manually ran the script"

This indicates the firmware **code is functional**, but the **CI upload/reset workflow** doesn't properly:
1. Reset the device after upload
2. Wait for USB re-enumeration
3. Ensure firmware actually boots and runs

## Root Cause

**CI automated picotool upload → device doesn't reliably boot new firmware**

Symptoms:
- Firmware uploads successfully (100% progress)
- Device enumerates as `/dev/ttyACM0`
- BUT: Device appears stuck in pre-initialization state
- No motor init logs appear
- In baseline: no MIDI received (T=0.00)
- In modern: MIDI partially processed but incomplete

## Workaround

**Manual hardware testing is authoritative**

1. Build firmware: `platformio run -e pico_1motor_endless`
2. Enter BOOTSEL manually (press button while plugging in, or double-reset)
3. Upload: `platformio run -e pico_1motor_endless --target upload`
4. Verify device reset and re-enumerated
5. Run tests: `cd test && python3 test_suite_automated.py`

## What Still Works in CI

✅ **Build Firmware** - compiles successfully, code quality checks pass  
✅ **Headless Tests** - pytest unit tests, simulators (3 passing)  
✅ **Code Quality** - function size, lint checks  

## Plan to Fix

### Phase 1: Document and Accept (DONE)
- ✅ Document issue in knowledge base
- ✅ Update CI to mark hardware tests as informational
- ✅ Provide manual testing guide

### Phase 2: Simple, Slow Tests (IN PROGRESS)
- Add explicit device communication verification
- Add generous delays after upload (5-10 sec)
- Test USB enumeration explicitly before running motor tests
- Add "ping" test that just verifies device responds
- Make tests defensive and verbose

### Phase 3: Investigate Upload Workflow
- Research RP2040 TinyUSB bootloader behavior
- Compare picotool reset vs manual BOOTSEL
- Test different upload protocols (openocd, jlink)
- Consider using `picotool reboot` explicitly

### Phase 4: Device State Verification
- Add firmware heartbeat on USB CDC
- Verify motor initialization completed before testing
- Add device state query commands
- Implement "ready" signal from firmware

## Related Issues

- `.agentic/ci/TINYUSB_BOOTLOADER_ISSUE.md` - Known TinyUSB bootloader reentry issues
- PID parameter changes (b168379) **work in manual testing** - confirms code is functional

## References

- Last working CI test: e1f45f6 (Feb 27, 18:20)
- First failing CI test: 5052b1b (Feb 27, 21:07)
- Experiment branch: experiment/motor-movement-diagnosis (316b41a)
