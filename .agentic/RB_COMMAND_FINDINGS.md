# RB Command Investigation - Findings

**Status**: ❌ **ABANDONED** - RB command causes device lock-up. Manual BOOTSEL remains the only working method.

## Problem Statement

Attempted to implement automatic firmware upload via a reboot-to-bootloader (RB) command, eliminating the need for manual BOOTSEL button presses during development.

## Implementation Attempted

**Approach 1**: Direct ARM Cortex-M0+ AIRCR register reset
- Issue: SCB register not defined in project headers
- Result: Compilation failed

**Approach 2**: Watchdog-based reset with magic RAM value
- Method: Write 0x73717856 magic to RAM address 0x20042000
- Reset mechanism: Watchdog peripheral (40058000), 1µs timeout trigger
- Expected: Device enters bootloader mode, BOOTSEL mount appears
- **Actual Result**: Device locks up, becomes unreachable on /dev/ttyACM0
- No BOOTSEL mount appears
- Device requires manual power cycle to recover

## Root Cause Analysis

The RP2040 bootloader appears to **not** check the magic RAM location or respond to watchdog resets in the way tested. Possible causes:

1. **Pico bootloader design**: May not support runtime reboot-to-bootloader via magic values or watchdog (unlike some ARM Cortex designs)
2. **USB timing issue**: Sending RB command via CDC, then immediately resetting may break USB enumeration/driver handshake
3. **Missing bootloader configuration**: Pico SDK's `watchdog_reboot()` requires specific SDK initialization we didn't replicate
4. **Hardware constraints**: RP2040 may not support software-triggered bootloader entry after CDC connection established

## What DOES Work

✅ **Manual BOOTSEL button press** - Press button 2 seconds before USB power-up or while device is running, device enters bootloader mode reliably every time

✅ **PlatformIO automatic detection** - `platformio run --target upload` detects BOOTSEL mount and programs automatically (provided button is pressed at right time)

## Proven Mitigation for Upload Reliability

The **only known mitigation** for firmware upload reliability is **USB congestion management**:

From [BOOTSEL_REGRESSION_ANALYSIS.md](BOOTSEL_REGRESSION_ANALYSIS.md):
- Reduce telemetry output frequency (was 10Hz, reduced to 5Hz)
- Avoid concurrent diagnostic queries during upload
- Telemetry ringbuffer saturation causes test timeouts with no error messages
- USB CDC driver requires reliable handshake with bootloader

## Lessons Learned

1. **Don't invent solutions**: RP2040 bootloader behavior is documented in Pico SDK - if it's not in the SDK as working, it won't work
2. **Focus on what works**: Manual BOOTSEL + PlatformIO is reliable, proven, and documented
3. **USB is fragile**: CDC connections are stateful - reset during active communication breaks enumeration
4. **Keep diagnostics separate**: Telemetry/diagnostics and upload are different responsibilities - one shouldn't break the other

## Recommendation

- **STOP all efforts to automate bootloader entry** on RP2040
- **Use manual BOOTSEL** for all firmware uploads (documentation + shell alias for speed)
- **Focus on upload reliability**: Mitigate USB congestion by reducing telemetry rate and batching diagnostics
- **For CI/automation**: PlatformIO's native `--target upload` works reliably when BOOTSEL is pressed externally

## Files Affected

- `src/commander_integration.cpp`: RB command implementation removed
- `tools/multi_upload.py`: Unused, not deployed
- Watchdog reset logic: Not salvageable for bootloader entry

## Time Spent

~2 hours of investigation across 2 iterations with firmware testing and mount point monitoring - **concluded unproductive**. 

**Better approach**: Accept manual BOOTSEL as design constraint, document it clearly, and ensure development workflow is optimized around it (e.g., quick press-upload cycle).
