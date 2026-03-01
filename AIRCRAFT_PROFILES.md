# Aircraft Control Profiles

10 pre-configured control profiles for Cessna 172, Airbus A320, and Glider.
Each profile configures one motor axis with realistic haptic feedback.

Source data: [.agentic/AIRCRAFT_CONTROLS_RESEARCH.md](.agentic/AIRCRAFT_CONTROLS_RESEARCH.md)

## Profile Table

| # | Profile | MIDI CC | Range | Haptic | USB PID |
|---|---------|---------|-------|--------|---------|
| 0 | Cessna Trim | CC#64 | 180° | Smooth | 0x1701 |
| 1 | Cessna Throttle | CC#7 | 180° | Smooth | 0x1702 |
| 2 | Cessna Flaps | CC#5 | 120° | 4 stops (0/10/20/30°) | 0x1703 |
| 3 | 172RG Gear | CC#35 | 90° | 2 stops (DOWN/UP) | 0x1704 |
| 4 | A320 Trim | CC#64 | 180° | Smooth | 0x3201 |
| 5 | A320 Throttle | CC#7 | 120° | 6 gates (REV→TOGA) | 0x3202 |
| 6 | A320 Flaps | CC#11 | 100° | 5 stops (0/1/2/3/FULL) | 0x3203 |
| 7 | A320 Spoilers | CC#2 | 90° | 3 pts (retract/mid/full) | 0x3204 |
| 8 | Glider Trim | CC#64 | 120° | Smooth | 0x7001 |
| 9 | Glider Spoiler | CC#2 | 90° | 2 stops (locked/full) | 0x7002 |

Single-motor hardware: one profile active at a time.
Profile switch persists to EEPROM and reboots for USB identity change.

## Switching Profiles

### Serial (Commander 'A')

```
A          — List all profiles + show active
A0         — Switch to Cessna Trim
A5         — Switch to A320 Throttle
...
A9         — Switch to Glider Spoiler
```

### MIDI CC#121

Send CC#121 with value = profile index (0–9).
Example: CC#121 value 5 → A320 Throttle.

## Haptic Modes

Each profile uses one of three haptic modes:

- **Smooth** — Free rotation, no detents. Trims and throttles.
- **Custom detent map** — Defined stop positions with per-detent strength.
  Flaps, gear, spoilers.
- **Gate mode** — Like custom map, but snaps only within a capture zone.
  Free proportional movement between gates. A320 throttle.

Detent maps are defined in [src/config.h](src/config.h) as `DetentPoint` arrays.
Each point has a position (0–100%) and strength (0.0–1.0).

## Profile Details

### Cessna 172

| Control | Haptic | Notes |
|---------|--------|-------|
| Trim | Smooth, 180° | Real trim wheel: ~18 turns, no clicks, cable friction hold |
| Throttle | Smooth, 180° | Real: push-pull plunger, friction lock |
| Flaps | 4 stops, 120° | 172SP: 0°/10°/20°/30° (pre-1981 had 5 stops to 40°) |
| 172RG Gear | 2 stops, 90° | Standard 172 has fixed gear; this is the RG variant |

### Airbus A320

| Control | Haptic | Notes |
|---------|--------|-------|
| Trim | Smooth, 180° | THS trim wheels: 12 turns, no clicks, motor-driven in normal law |
| Throttle | 6 gates, 120° | REV FULL→REV IDLE→IDLE→CLB→FLX→TOGA, proportional between gates |
| Flaps | 5 stops, 100° | Lever positions: 0/1/2/3/FULL (1+F is a flight law, not a lever stop) |
| Spoilers | 3 pts, 90° | Proportional: hard stops at 0%/100%, soft midpoint reference |

**A320 Throttle Gate Spacing** (matches real A320 / TCA quadrant):

| Gate | Position | Strength |
|------|----------|----------|
| REV FULL | 0% | 1.0 (hard) |
| REV IDLE | 12% | 0.8 |
| IDLE | 25% | 1.0 (hard) |
| CLB | 52% | 1.0 (hard) |
| FLX/MCT | 73% | 0.8 |
| TOGA | 100% | 1.0 (hard) |

### Glider (ASK-21 / Discus / LS4 class)

| Control | Haptic | Notes |
|---------|--------|-------|
| Trim | Smooth, 120° | Real: spring trim, 90–120° travel, lighter range than airplane |
| Spoiler | 2 stops, 90° | Locked closed (hard) + full open (stop). Proportional between. |

## MIDI Protocol

Standard MIDI Control Change (0xB0). Value 0–127 maps linearly to 0–100% of the profile's travel range.

```python
import mido
out = mido.open_output("FOC - Cessna Trim")
# Set trim to 50%
out.send(mido.Message('control_change', control=64, value=64))
# Switch to profile 5 (A320 Throttle)
out.send(mido.Message('control_change', control=121, value=5))
```

## Live Tuning (Commander 'W')

Haptic parameters are adjustable at runtime without recompiling:

```
W        — Show current haptic config
WE0/WE1  — Disable/enable haptic layer
WR180    — Set range (degrees)
WC90     — Set center position (degrees)
WN18     — Set uniform detent count (clears custom map)
WS0.5    — Set detent strength (0.0–1.0)
WM5.0    — Set endstop margin (degrees)
```

## Design Rationale

Profile data verified against real aircraft references:
- Cessna 172S/SP POH (Pilot's Operating Handbook)
- Airbus A320 FCOM (Flight Crew Operating Manual)
- Glider manuals (ASK-21, Discus, LS4)
- Thrustmaster TCA Quadrant gate measurements

Key design choices:
- **Trims are smooth** — no real trim wheel has clicks (RC-6)
- **Glider trim is 120°** — real glider trim has less travel than airplane trim (RC-7)
- **A320 throttle uses gate mode** — proportional between detents, snap within capture zone
- **A320 spoilers have no intermediate clicks** — real speed brake is proportional
- **Each profile gets a unique USB PID** — host OS sees distinct devices
