# Technical Knowledge Base

**Last Updated**: 2026-03-02 (v0.1 released)

---

## Hardware

- **MCU**: RP2040 Pico — dual Cortex-M0+ @ 133 MHz, 264 KB RAM, 2 MB flash
- **Sensor**: AS5600 12-bit magnetic encoder (I2C @ 0x36)
- **Motor**: 3-phase BLDC, 7 pole pairs, PWM driver
- **Control**: SimpleFOC 2.4.0 angle mode, ~1 kHz FOC loop
- **Thermal limit**: 2.0 V — motor heats above this on sustained holds

## USB Interfaces (TinyUSB composite)

| Interface | Details |
|-----------|---------|
| HID | Joystick: 2 axes (16-bit, 0–65535), 8 buttons, 50 Hz (20 ms) |
| MIDI | Native USB MIDI (raw TinyUSB, no external MIDI library) |
| CDC | Serial @ 115200 — Commander + @T telemetry |

## Build

Single environment: `pico_1motor_endless`.

```bash
pio run                              # build
pio run -t upload                    # needs 1200bps reset or manual BOOTSEL
```

Libraries (platformio.ini `lib_deps`): `Simple FOC`, `MIDI`.

## PID Configuration (`include/pid_config.h`)

```
Angle:  P=16  I=0.2  D=1.0
Vel:    P=0.1 I=0.5  D=0
LPF Tf: 0.001 s
Voltage limit: 2.0 V   Velocity limit: 4.0 rad/s
```

18 iterations of tuning (Ziegler-Nichols → manual → coordinate-descent
optimizer). Key insight: LPF_Tf=0.001 removes phase lag, allowing higher P
without oscillation.

## Profiles

11 control profiles in `src/config.h`, switched via MIDI CC#0 bank select.
Details: `ARCHITECTURE.md` § Profile table.

## Testing

| Test | Purpose | Run |
|------|---------|-----|
| Quality suite (8 tests) | Accuracy, speed, stability, overshoot, etc. | `python test/quality_goals_test_suite.py` |
| Cessna Trim linearity | Linearity & endstop verification for profile 0 | `python test/test_cessna_trim.py` |
| Simulator unit tests | Axis mapping without hardware | `pytest test/unit/` |

Quality gate at v0.1: **7/8 pass** (Test G Random Walk 18/20 — accepted).

Tools in `test/tools/`: debug_joystick, debug_midi, diagnostic_tuning_report,
endstop_observer, hid_monitor, linearity_scan, pid_optimizer,
profile_monitor, quick_tuning_check, trim_setup, trim_wheel_test.

## Known Issues (all resolved in v0.1)

| Issue | Resolution |
|-------|-----------|
| BOOTSEL required for uploads | `rb` serial command → watchdog reboot to BOOTSEL |
| USB CDC buffer overflow | Reduced telemetry rate, ring buffer in telemetry.cpp |
| Motor ignores commands (intermittent) | Hardware flakiness — power cycle resolves |

## Development Workflow

```bash
git flow feature start my-feature
# edit → build → upload → test
pio run -e pico_1motor_endless -t upload
python test/quality_goals_test_suite.py

git commit -m "feat: description"
git push origin feature/my-feature
# merge via --no-ff into dev
```

## References

- [SimpleFOC Docs](https://docs.simplefoc.com/)
- [TinyUSB Examples](https://github.com/adafruit/Adafruit_TinyUSB_Arduino/tree/master/examples)
- [RP2040 Datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf)
- [AS5600 Datasheet](https://ams.com/documents/20143/36005/AS5600_DS000365_5-00.pdf)
