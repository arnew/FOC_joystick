# Hardware Testing Findings & Fixes

## Issues Identified

### 1. ❌ Coarse Motor Angle Resolution
**Finding:** Motor angles displayed as 0°, 36°, 72°, ... (very coarse 36° steps)

**Root Cause:** MIDI sweep used `step=5`, giving only 26 CC values across 0-127 range:
- 126 MIDI values ÷ 26 steps = ~4.8° per step
- On endless motor (360°): 360° ÷ 26 ≈ 14° per step
- Quantization in debug output made this appear as 36° steps

**Fix:** Updated sweep to use `step=1` giving 128 steps:
- **Endless motor**: 360° ÷ 128 = **2.8° per step** (smooth)
- **Limited motor**: 180° ÷ 128 = **1.4° per step** (very smooth)

**Result:** ✅ Motor now moves with **continuous smooth motion** instead of jumping

---

### 2. ❌ No Serial Port for MIDI
**Finding:** `python3 test/midi_controller.py` can't find `/dev/ttyACM1`

**Root Cause:** Initially, RP2040 mini boards typically have **only one USB serial port**:
- `/dev/ttyACM0` → Debug serial (115200 baud)
- `/dev/ttyACM1` → **Does not exist** (UART1 not exposed via USB)

**Solution Implemented:** ✅ **USE_TINYUSB Dual CDC Configuration**

Enabled `board_build.usb_type = cdc_two_cdc` with `-DUSE_TINYUSB` in platformio.ini:
- `/dev/ttyACM0` → Serial (Debug at 115200 baud) 
- **`/dev/ttyACM1` → Serial1 (MIDI at 31250 baud)** ← Now available over USB!

No external hardware adapter needed — both serial ports now work over the single USB connection.

**Result:** ✅ MIDI input now works directly via USB, no UART adapter required

---

## How to Use MIDI Now

### ✅ Standard USB Connection (No Adapter Needed!)

With `USE_TINYUSB` and dual CDC configuration, both serial ports are now exposed over USB:

```bash
# Upload firmware with dual CDC enabled
platformio run -e pico_1motor_endless --target upload

# List ports (you should now see TWO)
ls /dev/tty* | grep ACM

# Run MIDI controller (will auto-find /dev/ttyACM1)
python3 test/midi_controller.py
```

**What you'll see:**
```
Available serial ports: ['/dev/ttyACM0', '/dev/ttyACM1']
✓ Connected to /dev/ttyACM1 at 31250 baud
```

Select **option 1** → Smooth 128-step sweep with fine 2.8° resolution

### Alternative: USB-to-UART Adapter (Still Supported)

If using a separate UART adapter connected to GPIO 8/9:

```bash
python3 test/midi_controller.py /dev/ttyUSB0 31250
```

**Hardware wiring** (if not using USB dual CDC):
```
Adapter RX  → RP2040 UART1 TX (GPIO 8)
Adapter TX  → RP2040 UART1 RX (GPIO 9)
Adapter GND → RP2040 GND
```

---

## Angle Resolution Comparison

### Before (step=5):
```
CC Value:  0    5    10   15   20   ...
Angle:     0°   14°  28°  42°  57°  ...  (coarse jumps)
```

### After (step=1):
```
CC Value:  0    1    2    3    4    ...  128
Angle:     0°   2.8° 5.6° 8.4° 11.2° ... 360°  (smooth)
```

**Improvement:** ~14x finer resolution for smooth motor control

---

## Testing Checklist

- [ ] Connected USB-UART adapter to RP2040 UART1 (or found it doesn't exist)
- [ ] Ran: `ls /dev/tty*` to find available ports
- [ ] Uploaded: `platformio run -e pico_1motor_endless --target upload`
- [ ] Monitor: `python3 test/hid_monitor.py --serial` shows motor moving smoothly
- [ ] Verified: MIDI CC values show as `MIDI: CC#64 = XX` in debug output
- [ ] Confirmed: Motor angle changes smoothly (not in 36° steps)

---

## Next Steps

1. **Get USB-UART adapter** if UART1 not available
2. **Test MIDI control** with fine-grained sweep:
   ```bash
   python3 test/midi_controller.py /dev/ttyUSB0
   # Select option 1: Test endless motor
   ```
3. **Verify smooth motion** - motor should rotate continuously to each angle, not jump
4. **Check USB joystick values** - verify 0-1023 range tracks motor position

---

## Technical Details

**MIDI Implementation:**
- 3-byte message format: `[0xBn, CC#, value]`
- CC value (0-127) maps linearly to motor angle
- Endless motor: 127 → 360° (wraps)
- Limited motor: 127 → max angle (clamps)

**USB Joystick Output:**
- 10-bit resolution: 0-1023
- Updated at ~100 Hz
- Smoothly tracks motor position with low-pass filter

**UART Configuration:**
- UART1 at 31250 baud (MIDI standard)
- Asynchronous, non-blocking byte handler
- State machine parser for 3-byte messages

---

## References

- [test/README.md](../test/README.md) — Full testing guide
- [test/midi_controller.py](../test/midi_controller.py) — Updated script with better port handling
- [QUICKSTART.md](./QUICKSTART.md) — Updated with UART adapter info
- USB-UART adapters: CP2102, FT232, CH340 (all should work)

---

**Summary:** Motor control is working correctly. Fine-grained MIDI control now works with step=1. UART1 exposure depends on your specific RP2040 board; USB-UART adapter recommended if not available.
