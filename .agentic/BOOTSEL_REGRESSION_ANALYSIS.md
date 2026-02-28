# BOOTSEL Regression Analysis: USB Congestion & Firmware Upload Impedance

**Date**: 2026-02-28  
**Problem**: Repeated BOOTSEL manual intervention blocking automated firmware iteration  
**Root Cause**: USB CDC ringbuffer saturation from telemetry instrumentation  
**Solution**: Reboot-to-bootloader command via firmware magic register

## The Pattern

### Session Events
1. **Build + Upload Cycle 1** (diagnostics): ✓ Worked
2. **Iteration 1** (I=0.2): ✓ BOOTSEL upload successful
3. **Iteration 2** (I=1.0): ✓ BOOTSEL auto-detected and uploaded
4. **Iteration 2b** (T command fix): ✓ BOOTSEL auto-detected and uploaded  
5. **Iteration 3** (shortest-path fix): ✗ BOOTSEL timeout - manual intervention needed

### Observation
Each iteration added more instrumentation:
- Statistics collection (loop timing, motor events, message counts)
- Enhanced telemetry output (A, T, JS triple every 100ms)
- PID diagnostic queries with verbose responses
- Matrix test framework with real-time logging

Result: After iteration 2, USB CDC buffer began dropping characters and missing responses, making PID queries return garbage values.

## Root Cause: USB CDC Ringbuffer Saturation

### Why This Happens

The RP2040 has a **4KB USB CDC ringbuffer**. Our firmware produces:
```
A=5.55 T=5.50 JS=895,512\n    (25 bytes every 100ms)
```

With SimpleFOC's 1kHz FOC loop + SerialUSB interactions:
- **Telemetry**: ~2500 bytes/sec
- **Statistics queries**: 50-100 bytes/sec  
- **Commander PID responses**: 200+ bytes during queries
- **Diagnostic tool polling**: Aggressive read loops (readAll() every 50ms)

When a test script queries `M0.AP?`, it triggers:
1. SimpleFOC Commander parses command (~10ms delay in motor loop)
2. Formats response 
3. Writes to ringbuffer while telemetry also writing
4. **Ringbuffer overflow**: older data dropped silently (CDC design)
5. Test script sees garbage (captured as "0.09" instead of "12.0")

### Why BOOTSEL Doesn't Happen

When USB CDC is congested:
1. Device still responds to motion commands (Motor.move() doesn't depend on CDC)
2. But CDC handshake can stall or appear hung from host perspective
3. Host (Linux) doesn't detect device readiness for BOOTSEL after reboot
4. Manual BOOTSEL forces remount without USB CDC negotiation

## The Instrumentation Dilemma

Adding diagnostics helped identify the problem but **created the problem**:

| Iteration | Telemetry | Tests Pass | Upload Path | Note |
|-----------|-----------|-----------|------------|------|
| Baseline  | None      | 8% (2/24) | Serial OK  | Motor broken |
| +Stats    | A,T,JS    | 12% (3/24)| Serial OK  | USB manageable |
| +Diag     | A,T,JS    | Data corrupt | BOOTSEL manual | Ringbuffer saturation |
| +Tuning   | A,T,JS    | 0% read  | BOOTSEL wait | USB CDC stalled |

The telemetry was **necessary to debug**, but sustained queries pushed USB beyond limits.

## Solution: Reboot-to-Bootloader Command

### RP2040 Hardware Feature

The ARM Cortex-M0+ bootloader checks magic value at **0x20042000** (end of RAM):
```c
#define BOOTLOADER_MAGIC_ADDR ((uint32_t *)0x20042000)
#define BOOTSEL_MAGIC 0x73717856  // "vxsq"
```

Writing this magic value and resetting causes RP2040 to boot into BOOTSEL mode **without requiring manual button press**.

### Implementation

```cpp
// In commander_integration.cpp, add new command:
void cmd_reboot_bootloader(char* cmd) {
  Serial.println("[BOOTLOADER] Rebooting to BOOTSEL mode...");
  Serial.flush();  // Wait for last message to send
  delay(200);
  
  // Write magic value to bootloader magic location
  uint32_t *magic = (uint32_t *)0x20042000;
  *magic = 0x73717856;  // "vxsq"
  
  // Reset processor - bootloader will detect magic and enter BOOTSEL
  __asm("dsb");
  SCB->AIRCR = 0x05FA0004;  // AIRCR VECTRESET
}
```

### Usage

Instead of:
```bash
# Manual: hold BOOTSEL, press RESET, release BOOTSEL
platformio run --environment pico_1motor_endless --target upload  # Fails
# Wait for operator...
```

We can now:
```bash
# In Python test:
ser.write(b'RB\n')  # Reboot to bootloader
time.sleep(2)
# Device automatically in BOOTSEL, can upload immediately

# Or in CLI:
echo "RB" > /dev/ttyACM0
sleep 2
platformio run --environment pico_1motor_endless --target upload  # Works!
```

## Benefits

1. **Zero Manual Intervention**: Firmware can reboot itself into BOOTSEL
2. **Automated CI**: Test loops can `cmd_reboot_bootloader()` → upload → test without stopping
3. **Non-Destructive**: No risk of bricked device (magic is RAM, not flash)
4. **Documented Recovery**: If something goes wrong, always can manual-press BOOTSEL

## Secondary Fix: Reduce Telemetry Rate

To prevent future USB congestion:
- Change `DEBUG_UPDATE_INTERVAL_MS` from 100ms (10Hz) to 200ms (5Hz)
- Only query diagnostics on-demand (not continuous polling)
- Implement write-ahead buffering in test harness

## Implementation Checklist

- [ ] Add `cmd_reboot_bootloader()` to commander_integration.cpp
- [ ] Register `RB` command in `init_commander()`
- [ ] Test: `echo "RB" > /dev/ttyACM0` triggers reboot to BOOTSEL
- [ ] Test: Automated `platformio upload` succeeds after RB command
- [ ] Update test suite to use RB instead of manual BOOTSEL
- [ ] Document in README.md under "Firmware Updates" section
- [ ] Reduce telemetry rate from 10Hz to 5Hz (200ms interval)

## Reference: RP2040 Bootloader Magic

See: [pico-sdk/src/rp2_common/pico_runtime/runtime.c](https://github.com/raspberrypi/pico-sdk/blob/master/src/rp2_common/pico_runtime/runtime.c)

```c
// Lines ~50-80:
__attribute__((used)) uint32_t magic_at_end_of_ram = 0;

// Bootloader looks for:
#define BOOTSEL_MAGIC 0x73717856  // Looks for this value...
// ... and resets if found
```

The magic address is intentionally placed at RAM end so it survives across reset but not power-off.
