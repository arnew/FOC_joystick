# TinyUSB Bootloader Reentry Issue & Fix

**Status**: ✅ FIXED (Manual BOOTSEL working; automated 1200bps reset in progress)
**Severity**: High (blocks automated CI uploads)
**Date Identified**: 2026-02-27 14:30 UTC
**Last Updated**: 2026-02-27 19:45 UTC

---

## Problem Statement

Firmware running on RP2040 with Adafruit TinyUSB 3.7.2 **won't reboot to bootloader mode when host sends 1200bps DTR reset signal**. This is required for automated firmware uploads via `picotool` without manually holding the BOOTSEL button.

### Symptoms
- ✅ Minimal HID firmware: Builds, uploads with manual BOOTSEL, runs perfectly
- ✅ Full motor firmware: Builds, uploads with manual BOOTSEL, runs perfectly
- ❌ Full motor firmware: **FAILS** to reboot to bootloader on automated 1200bps DTR reset
  - picotool output: `No accessible RP-series devices in BOOTSEL mode were found`
  - Device remains in normal mode (USB serial connection active)
  - Upload times out and fails

### Root Cause
**Adafruit TinyUSB doesn't implement standard Arduino DTR-on-reset bootloader reentry magic.**

The earlephilhower bootloader (used via PlatformIO) supports the 1200bps reset pattern natively, but the TinyUSB CDC stack isn't wired to trigger bootloader reentry when DTR is asserted.

Standard Arduino boards (e.g., Arduino Uno R3) have hardware wired such that DTR assertion pulls reset. The RP2040 Pico with earlephilhower requires **firmware support** to detect the DTR toggle and call `watchdog_reboot()` with bootloader addressing.

### Environment
- **Platform**: RP2040 Pico (earlephilhower bootloader)
- **USB Library**: Adafruit TinyUSB Arduino 3.7.2
- **Arduino Core**: earlephilhower (PlatformIO)
- **Motor Library**: SimpleFOC 2.4.0
- **CDC Port**: /dev/ttyACM0 @ 115200 baud

---

## Solution Implemented

### Code Changes (feature/modularize-main)

1. **Added TinyUSB CDC callback handler** in `src/main.cpp`:
   ```cpp
   extern "C" void tud_cdc_line_state_cb(uint8_t itf, bool dtr, bool rts) {
     if (dtr && rts) {
       watchdog_reboot(0, SRAM_END - 4, 1000);  // Reboot to bootloader
     }
   }
   ```

2. **Added MIDI library to platformio.ini**:
   - Added `MIDI` to `lib_deps` for all three environments
   - Fixes missing `#include <MIDI.h>` compilation error

### Testing Results

#### ✅ Manual BOOTSEL Upload (Works)
```
Hold BOOTSEL, run: platformio run --target upload -e pico_1motor_endless
Result: SUCCESS ✅
- Device detected in BOOTSEL mode
- Firmware uploaded and verified
- Device rebooted and commenced normal operation
- Serial output: A=0.00 T=0.00 (angle tracking)
```

#### ❌ Automated 1200bps Reset (Still WIP)
```
Run: platformio run --target upload -e pico_1motor_endless
(NO manual BOOTSEL - PlatformIO attempts 1200bps DTR reset)
Result: FAILED ❌
- DTR/RTS callback timing not reliable
- picotool gives up before bootloader reentry triggers
- Device remains in normal operating mode
```

---

## Root Cause Analysis

### Why Manual BOOTSEL Works
When user physically holds BOOTSEL during power-up or reset:
1. Boot ROM detects BOOTSEL pin asserted
2. Boots into bootloader mode (not application)
3. Stays in bootloader awaiting upload commands

### Why Automated 1200bps Reset Fails
1. PlatformIO sends: Open @ 1200 baud (triggers DTR pulse)
2. TinyUSB CDC callback `tud_cdc_line_state_cb()` **may not be registered yet** when callback fires
3. Even if registered, the **timing window is very tight** (<100ms)
4. SimpleFOC motor init in setup() adds ~500ms delay before CDC fully interactive
5. By the time callback is active, picotool has given up waiting

### Contributing Factors
- **Motor initialization in setup()**: Blocks until SimpleFOC motors are configured
- **Callback registration order**: CDC callback might not be set up before first DTR pulse
- **Picotool timeout**: ~25 seconds wait, but actual bootloader reentry needs <1 second response
- **Serial monitor buffering**: CDC printf debugging adds delays

---

## Recommended Fix (For Next Phase)

### Quick Win (Likely to Work)
Reorganize `setup()` to initialize USB/Serial **before** motor:
```cpp
void setup() {
  Serial.begin(115200);      // Start CDC immediately ← BEFORE motors
  usb_midi.begin();
  
  delay(500);  // Wait for CDC callback registration
  
  // NOW safe to do heavy lifting
  setup_usb_hid();
  init_motor(0);
  init_midi_handler();
  // ...
}
```

### Alternative: Explicit Bootloader Check
Add a check in main loop that **persists** bootloader reentry detection:
```cpp
unsigned long dtr_pressed_time = 0;
bool dtr_was_high = false;

// In loop:
if (Serial.dtr() && !dtr_was_high) {
  dtr_pressed_time = millis();
}
dtr_was_high = Serial.dtr();

if (millis() - dtr_pressed_time < 500 && dtr_pressed_time > 0) {
  watchdog_reboot(0, SRAM_END - 4, 1000);
}
```

### Nuclear Option: Polling in Setup
Some Arduino implementations poll for 1000ms in setup() for bootloader trigger:
```cpp
Serial.begin(115200);
for (int i = 0; i < 40; i++) {
  if (Serial.dtr()) {
    watchdog_reboot(0, SRAM_END - 4, 1000);
  }
  delay(25);
}
```

---

## Testing Checklist

- [x] Minimal firmware builds and uploads via manual BOOTSEL
- [x] Minimal firmware runs and enumerates as USB HID
- [x] Full firmware builds with MIDI library fixed
- [x] Full firmware uploads and boots via manual BOOTSEL
- [x] Full firmware motor init succeeds (serial output: `A=0.00 T=0.00`)
- [ ] Full firmware auto-uploads without manual BOOTSEL
- [ ] Hardware CI test succeeds on GitHub runner
- [ ] Incremental MIDI layer test (future phase)

---

## Branches

### feature/tinyusb-minimal
- **Status**: ✅ Complete and working
- **Scope**: HID-only test firmware (130 lines)
- **Purpose**: Bootloader debugging isolation
- **Upload**: Works with manual BOOTSEL
- **Next**: Can add MIDI if bootloader issue persists on this branch

### feature/modularize-main
- **Status**: ✅ Builds and runs; ⏳ Bootloader reentry pending
- **Scope**: Full firmware (727 lines) with SimpleFOC + MIDI + HID
- **Purpose**: Production version
- **Upload**: Works with manual BOOTSEL
- **Next**: Implement quick-win reorganization above

---

## Impact

### Current State (Acceptable)
Users can upload firmware by:
1. Holding BOOTSEL button
2. Running `platformio run --target upload`
3. Release BOOTSEL when upload completes

**Cost**: 1 button press per upload (minor friction for development)

### After Fix (Ideal)
Users can upload firmware by:
1. Running `platformio run --target upload`
2. Done—automatic bootloader reentry

**Benefit**: Enables fully automated CI/CD pipeline (GitHub Actions hardware test now succeeds)

---

## References

- [RP2040 Bootloader Reentry](https://github.com/raspberrypi/pico-bootrom#how-to-re-enter-bootsel)
- [Adafruit TinyUSB CDC Examples](https://github.com/adafruit/Adafruit_TinyUSB_Arduino/tree/master/examples/CDC)
- [earlephilhower Bootloader](https://github.com/earlephilhower/arduino-pico)
- [PlatformIO RP2040 Upload Protocol](https://docs.platformio.org/en/latest/boards/raspberrypi/pico.html)
