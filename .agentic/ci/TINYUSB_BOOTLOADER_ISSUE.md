# TinyUSB Bootloader Issue & Minimal Rebuild Plan

**Issue**: Firmware upload fails on CI runner (and potentially on hardware) with:
```
RP2040 device at bus 1, address 3 appears to have a USB serial connection,
but picotool was unable to connect. Maybe try 'sudo' or check your permissions.
```

**Symptom**: 
- Motor is running fine on local firmware (user confirmed Feb 27)
- Upload from CI runner fails because device doesn't reboot to BOOTSEL mode
- Likely: TinyUSB library change broke bootloader reentry mechanism

**Hypothesis**: 
The current firmware in `src/main.cpp` uses TinyUSB for USB HID + MIDI, but a recent change (accident or library update) has broken the ability to reboot into bootloader mode from the running application.

**Strategy** (Feb 27, 2026):
1. **Branch**: `feature/tinyusb-minimal` (created)
2. **Minimal example**: Start with official PlatformIO/Pico example for TinyUSB
3. **Verify reboot**: Confirm device can reboot to BOOTSEL and be reflashed
4. **Layer on**: Add USB HID joystick support
5. **Layer on**: Add MIDI CC support
6. **Backport**: Apply working patterns to full `feature/modularize-main`

**⚠️ Manual Device Preparation Required**:
When pushing code that triggers a hardware test (CI runner will attempt upload):
- **Agent will pause and notify before each push**
- **User must press & hold RP2040 BOOTSEL button** during the upload window (typically ~5-10 seconds after upload starts)
- Release BOOTSEL after upload completes
- Device will reboot and run the new firmware
- This is required for picotool to reflash the device

**Current State**:
- `feature/modularize-main`: Motor working, upload broken
- `feature/tinyusb-minimal`: Fresh branch, starting from scratch
- `dev`: Base state before modularization
- `main`: Last release

**Next Step**:
1. Find minimal TinyUSB example in PlatformIO library
2. Test locally: build → upload → reboot cycle works
3. Then incrementally add HID and MIDI features

**See Also**:
- Adafruit TinyUSB Library 3.7.2 (current in platformio.ini)
- RP2040 datasheet: USB bootloader behavior
- PlatformIO examples: https://github.com/PlatformIO/platform-raspberrypi/tree/develop/examples
