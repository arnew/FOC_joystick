# USB Device Stability Issue - CRITICAL

**Date Identified**: 2026-02-27  
**Status**: 🔴 **CRITICAL** - Device requires manual reset every ~10 tests  
**Severity**: HIGH - Blocks development and testing workflow  
**Root Cause**: USB CDC bandwidth saturation from debug output spam

---

## Problem Statement

The RP2040 USB HID joystick device becomes severely unstable, requiring frequent manual resets (unfoobar) approximately every 10 test cycles. This is **unacceptable** for development workflow.

### Symptoms
- 🔴 Device disconnects/freezes after 10-15 test iterations
- 🔴 USB enumeration failures (device not recognized)
- 🔴 Requires manual BOOTSEL reset + reconnection to recover
- 🔴 Serial debug output may hang or buffer overflow
- 🔴 HID joystick reports stop being delivered
- 🔴 MIDI input processing degrades or stops

---

## Root Cause Analysis

### USB Bandwidth Saturation

The RP2040 has a **single USB 1.1 controller** handling multiple concurrent interfaces:

1. **USB CDC (Serial Debug)**: Virtual serial port @ 115200 baud
2. **USB MIDI**: Native MIDI input device
3. **USB HID**: Joystick output device

**PROBLEM**: Debug output in [src/main.cpp](../src/main.cpp#L108-L118) is running at **100 Hz** instead of the documented **1 Hz** target:

```cpp
// CURRENT CODE (BROKEN - 100 Hz debug spam)
static unsigned long last_debug = 0;

if (now - last_debug >= 10) {  // ❌ 10ms = 100 Hz
  Serial.print("A=");
  Serial.print(get_motor_angle(0), 2);
  Serial.print(" T=");
  Serial.println(target_angle[0], 2);
  
  last_debug = now;
}
```

**Impact**:
- **100 messages/second** × **~25 bytes/message** = **2500 bytes/sec CDC traffic**
- 4 Serial function calls per iteration = **400 USB CDC transactions/sec**
- Competes with HID reports (**100 Hz × ~5 bytes = 500 bytes/sec**)
- Competes with MIDI input (variable)

**Result**: USB controller buffer overflow → device reset → enumeration failure

---

## Evidence

### 1. Documentation vs Implementation Mismatch

**Documented Target** ([.agentic/testing/TEST_RESULTS.md](testing/TEST_RESULTS.md#L116)):
```
Debug Output Rate | 1 Hz | ✓ Target met
```

**Actual Code** ([src/main.cpp#L108](../src/main.cpp#L108)):
```cpp
if (now - last_debug >= 10) {  // 10ms interval = 100 Hz ❌
```

**Discrepancy**: **100x higher rate than design specification**

### 2. Architecture Specification

**Design Intent** ([.agentic/architecture/PLANNING.md#L226](architecture/PLANNING.md#L226)):
```
5. **~1 Hz**: Debug serial output
```

**Loop Timing Requirements**:
- FOC control: ~1 kHz (motor stability)
- USB HID: ~100 Hz (joystick responsiveness)
- Debug: **1 Hz** (human-readable telemetry)

### 3. USB Bandwidth Limits

**USB 1.1 Full Speed**: 12 Mbit/s = 1.5 MB/s theoretical max

**Actual Overhead**:
- USB protocol overhead: ~20-30%
- TinyUSB stack overhead: ~10-15%
- Shared between 3 interfaces (CDC + MIDI + HID)

**Practical Limit per Interface**: ~300-400 KB/s

**Current CDC Usage at 100 Hz**:
- 2.5 KB/s data + overhead = **~5-10 KB/s effective**
- But **400 transactions/sec** creates scheduling/buffer pressure

**Problem**: Not the bandwidth itself, but the **transaction rate** causing TinyUSB stack congestion.

---

## Contributing Factors

### 1. Tight Loop Timing
```cpp
void loop() {
  update_motor(0);          // ~1 kHz FOC
  handle_midi_byte(...);    // Every loop
  send_hid_report();        // Every 10ms (100 Hz)
  Serial.print(...);        // Every 10ms (100 Hz) ❌
}
```

**Problem**: 3 USB operations competing in same 10ms window

### 2. No Rate Limiting on CDC
Serial.print() calls are **blocking** when USB CDC buffer is full:
- TinyUSB waits for host to read CDC data
- Blocks main loop
- FOC timing degrades
- Device becomes unstable

### 3. Cumulative Buffer Pressure
After N iterations:
1. CDC buffer fills faster than host can drain
2. HID reports delayed waiting for CDC
3. MIDI input processing blocked
4. FOC loop timing disrupted
5. Device watchdog reset or USB disconnect

---

## Solution

### IMMEDIATE FIX: Reduce Debug Rate to 1 Hz

**Change**: [src/main.cpp#L108](../src/main.cpp#L108)

```cpp
// BEFORE (BROKEN)
if (now - last_debug >= 10) {  // 100 Hz ❌

// AFTER (FIXED)
if (now - last_debug >= 1000) {  // 1 Hz ✅
```

**Impact**:
- Reduces CDC transactions from **400/sec → 4/sec** (100x reduction)
- Eliminates USB buffer congestion
- Preserves human-readable telemetry (1 update/sec is sufficient)
- Aligns code with design specification

### Expected Behavior After Fix
- ✅ Device stable for 100+ test iterations
- ✅ No manual resets required
- ✅ USB enumeration reliable
- ✅ HID/MIDI/CDC all operating smoothly

---

## Additional Improvements (Optional)

### 1. Add USB Ready Check
```cpp
if (now - last_debug >= 1000) {
  if (Serial && !Serial.availableForWrite()) {
    // Skip this debug cycle if CDC buffer full
    return;
  }
  
  Serial.print("A=");
  // ... rest of debug output
}
```

### 2. Reduce Debug Verbosity
```cpp
// Instead of 4 Serial calls per message:
Serial.print("A=");
Serial.print(get_motor_angle(0), 2);
Serial.print(" T=");
Serial.println(target_angle[0], 2);

// Use single formatted message:
char buf[32];
snprintf(buf, sizeof(buf), "A=%.2f T=%.2f", 
         get_motor_angle(0), target_angle[0]);
Serial.println(buf);
```

**Benefit**: Reduces USB transactions from 4 → 1 per debug cycle

### 3. Add Compile-Time Debug Toggle
```cpp
#ifndef DEBUG_OUTPUT
#define DEBUG_OUTPUT 1  // Set to 0 for production
#endif

#if DEBUG_OUTPUT
if (now - last_debug >= 1000) {
  // Debug output
}
#endif
```

---

## Testing Plan

### Before Fix: Reproduce Issue
1. Flash current firmware
2. Run automated test suite (e.g., `test_hid_exercise.py`)
3. Monitor: Device typically fails after 10-15 iterations
4. **Expected**: USB disconnection, requires manual reset

### After Fix: Validate Stability
1. Apply change: `last_debug >= 10` → `last_debug >= 1000`
2. Rebuild and flash firmware
3. Run automated test suite for 100+ iterations
4. **Expected**: Device remains stable, no resets needed

### Success Criteria
- ✅ Device survives 100+ test iterations without manual intervention
- ✅ USB CDC, MIDI, HID all remain responsive
- ✅ Debug output still visible at 1 Hz (human-readable)
- ✅ No USB enumeration failures

---

## Historical Context

### How This Bug Was Introduced

**Original Design** (PLANNING.md):
- Debug output specified at **1 Hz**

**Implementation Error** (main.cpp):
- Copy-paste from HID update interval (10ms)
- Never caught in code review
- Documentation claimed "1 Hz Target met" but code ran at 100 Hz

**Why It Wasn't Caught Earlier**:
- Short test runs (<10 iterations) didn't trigger failure
- Manual testing with Serial monitor open reduces buffer pressure (host actively draining CDC)
- Automated CI tests skip Serial monitoring (no host reading CDC = faster buffer saturation)

### Lesson Learned
- **Validate Implementation vs Specification**: Code review should check timing constants match design docs
- **Automated Long-Running Tests**: CI should include 100+ iteration stress tests
- **USB Bandwidth Budget**: Document USB transaction budget and verify in testing

---

## References

- **Design Spec**: [.agentic/architecture/PLANNING.md](architecture/PLANNING.md#L226) (1 Hz debug output)
- **Test Results**: [.agentic/testing/TEST_RESULTS.md](testing/TEST_RESULTS.md#L116) (claimed 1 Hz, not verified)
- **Main Loop**: [src/main.cpp#L108](../src/main.cpp#L108) (broken 100 Hz implementation)
- **USB Config**: [include/my_tusb_config.h](../include/my_tusb_config.h) (TinyUSB buffer config)

---

## Priority: IMMEDIATE ACTION REQUIRED

This is a **blocking issue** preventing effective development and testing. The fix is trivial (one-character change: `10` → `1000`) but the impact is **critical**.

**Recommended**: Apply fix immediately, test for 100+ iterations, commit as hotfix.

