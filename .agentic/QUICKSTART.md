# Quick Start Guide

## Build for Current Hardware (Single Endless Motor)

```bash
# Compile
platformio run -e pico_1motor_endless

# Upload to RP2040
platformio run -e pico_1motor_endless --target upload
```

## Test Motor Response

### Monitor Debug Serial Output

```bash
# Watch motor angles and configuration at 115200 baud
python3 test/hid_monitor.py --serial
```

You should see:
```
=== USB HID Joystick Controller ===
Initializing...
Motor 0 initialized
MIDI input on Serial1 (31250 baud)

=== Loaded Configuration ===
Number of axes: 1
  0: Trim (Motor0, CC#64, endless)

=== Ready ===
```

Then every second:
```
Angle: 0.0000 rad (0.0°) | Target: 0.0000 | USB: 512 (0-1023)
```

**Note:** USB joystick value shows much finer resolution (0-1023) than the coarse motor angle print. This is expected — the motor control is smooth internally.

### Send MIDI CC Messages

✅ **No adapter needed!** Both debug and MIDI are now over USB.

```bash
python3 test/midi_controller.py
```

The script will auto-detect both USB serial ports:
- `/dev/ttyACM0` → Debug serial (115200)
- `/dev/ttyACM1` → MIDI input (31250)

Menu:
```
=== MIDI Controller Test Menu ===
1. Test endless motor (CC#64 Trim)
2. Test limited motor (CC#7 Throttle)
3. Send custom CC
4. Quick sweep
5. Exit

Select option (1-5): 1
```

Select **option 1** to sweep with **fine 128-step resolution** (smooth, not coarse).

Watch debug serial as angles change smoothly:
```
MIDI: CC#64 = 1 → Trim Motor0 angle: 0.0495
Angle: 0.0495 rad (2.8°) | Target: 0.0495 | USB: 8 (0-1023)
```

## Testing the Other Hardware Configurations

### Single Limited Motor (0-180°)

```bash
platformio run -e pico_1motor_limited --target upload

# Then test:
python3 test/midi_controller.py
# Select option 2 (Limited motor)
```

### Dual Motors

```bash
platformio run -e pico_2motor_limited --target upload

# Then test:
python3 test/midi_controller.py
# Option 1 tests Motor 0 (CC#7 Throttle)
```

## Troubleshooting

### Serial Port Issues

Find available ports:
```bash
ls /dev/tty* | grep -E "ACM|USB"
```

Manually specify port:
```bash
python3 test/midi_controller.py /dev/ttyACM1
```

### Permission Denied

Allow user to access serial ports:
```bash
sudo usermod -a -G dialout $USER
# Then log out and back in
```

### Motor Doesn't Respond to MIDI

1. **Check baud rate**: MIDI must be exactly 31250 (not 115200)
2. **Check port**: Debug is usually `/dev/ttyACM0`, MIDI is `/dev/ttyACM1`
3. **Check serial cable**: Make sure MIDI serial connection is wired correctly
4. **Check firmware**: Verify correct configuration was uploaded

## Key Files

| File | Purpose |
|------|---------|
| `src/main.cpp` | Motor control loop + MIDI handler |
| `src/config.h` | 3 hardware configurations |
| `platformio.ini` | Build environments |
| `test/midi_controller.py` | Send MIDI test commands |
| `test/hid_monitor.py` | Monitor debug output |
| `test/test_config.cpp` | Unit tests (GoogleTest) |

## Hardware Wiring Reference

**Motor 0** (3-phase PWM on RP2040):
- Phase A: GPIO 13
- Phase B: GPIO 12
- Phase C: GPIO 11
- Enable: GPIO 10
- I2C Encoder (AS5600): SDA/SCL (GPIO 4/5)

**Motor 1** (placeholder - configure as needed):
- PWM pins: (to be assigned)
- Enable: (to be assigned)
- Encoder: (separate I2C address or UART)

## MIDI CC Mapping (Default A320)

| Config | Axis | CC# | Motor | Range |
|--------|------|-----|-------|-------|
| 1-motor-endless | Trim | 64 | 0 | 0-360° |
| 1-motor-limited | Throttle | 7 | 0 | 0-180° |
| 2-motor-limited | Throttle | 7 | 0 | 0-180° |
| 2-motor-limited | Trim | 64 | 1 | 0-360° |

## Next Steps

1. ✅ Test Motor 0 with current endless configuration
2. ⬜ Verify MIDI CC→motor angle mapping
3. ⬜ Implement USB HID joystick output (Phase 5)
4. ⬜ Configure Motor 1 pins and encoder
5. ⬜ Test dual-motor configuration on real hardware

See [PLANNING.md](./PLANNING.md) for detailed architecture and [test/README.md](../test/README.md) for advanced testing.
