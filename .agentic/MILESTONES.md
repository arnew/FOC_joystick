# Milestone Plan — FOC Joystick

**Created**: 2026-03-01
**Basis**: Current dev HEAD (946b746), research in AIRCRAFT_CONTROLS_RESEARCH.md

---

## Version Summary

| Version | Codename | Goal | Hardware | Key Deliverable |
|---------|----------|------|----------|-----------------|
| **v0.1** | "It Moves" | Single motor works | 1 × motor+encoder | Motor holds position, serial tuning |
| **v0.2** | "It Clicks" | Haptic profiles | 1 × motor+encoder | 10 profiles, detents, smooth, gates |
| **v0.3** | "It Flies" | MSFS integration | 1 × motor+encoder | Companion app, end-to-end sim loop |
| **v0.4** | "It Feels Right" | Production quality | 1 × motor+encoder (refined) | Encoder cal, endstop fix, thermal mgmt |
| **v0.5** | "Two Hands" | Dual motor | 2 × motor+encoder | Independent axes, e.g. throttle+trim |
| **v1.0** | "Release" | Stable release | Final enclosure | Documented, tested, reproducible |

---

## v0.1 — "It Moves" ✅ DONE

**Status**: Shipped (dev HEAD).

What exists:
- RP2040 + AS5600 + BLDC 7pp + 3PWM driver
- SimpleFOC angle mode, unbounded rotation
- PID tuned (P=16, I=0.2, D=1.0, vel_P=0.1, vel_I=0.5, Tf=0.001)
- USB composite: HID joystick + MIDI + CDC serial
- Commander serial interface (M/T/A/W commands)
- Telemetry @T lines at 10Hz, EMA RMS + ring buffer variance
- Quality goals test suite (8 tests × 6 sequences)
- PID auto-optimizer (coordinate descent)

**Quality**: Unloaded limits pass (±10° accuracy). Loaded limits (±1°) need encoder calibration.

---

## v0.2 — "It Clicks" ✅ DONE

**Status**: Shipped (dev HEAD).

What exists:
- 10 control profiles (Cessna×4, A320×4, Glider×2)
- ControlProfile struct: range, center, detents, gate mode, USB identity
- Custom DetentPoint maps with per-detent strength
- Gate mode (A320 throttle: proportional between gates)
- Smooth mode (all trims: no clicks, like real aircraft)
- Profile switch: EEPROM persist + USB re-enumeration reboot
- Research-verified against real aircraft data (RC-1..RC-9)
- MIDI CC → haptic position, CC#121 → profile select
- Documentation: AIRCRAFT_PROFILES.md, AIRCRAFT_CONTROLS_RESEARCH.md

**Quality**: All profiles configure correctly. Haptic feel verified on hardware for smooth/click/gate modes.

---

## v0.3 — "It Flies" 🔜 NEXT

**Goal**: Close the loop between Microsoft Flight Simulator and the physical device. The motor follows the sim, the user pushes back, the sim sees the result.

### Features

| ID | Feature | Priority | Effort |
|----|---------|----------|--------|
| F-3.1 | MSFS companion app (SimConnect → MIDI) | MUST | 3 days |
| F-3.2 | HID joystick validated in MSFS | MUST | 1 day |
| F-3.3 | Profile auto-select from sim aircraft | NICE | 1 day |
| F-3.4 | Bidirectional sync (sim ↔ motor position) | MUST | 2 days |
| F-3.5 | Detent feel tuning with sim feedback | NICE | 1 day |

### F-3.1 — Companion App

The README describes: "a companion app/script that closes the loop from MSFS to the joystick."

**Architecture**:
```
  MSFS ──SimConnect──► Companion App ──MIDI CC──► RP2040 ──HID──► MSFS
                            │
                            └── reads sim variables (throttle %, trim %, flaps pos)
                                maps to MIDI CC for active profile
                                sends to device's MIDI port
```

**Implementation options** (research):
| Option | Language | SimConnect | MIDI Out | Complexity |
|--------|----------|------------|----------|------------|
| Python + SimConnect SDK | Python | python-simconnect | mido | Low |
| WASM gauge (in-sim) | JS/WASM | native | WebMIDI? | Medium |
| MobiFlight bridge | Config-only | MobiFlight | MobiFlight → MIDI | Zero code |
| FSUIPC + lua | Lua | FSUIPC | luamidi | Low |

**Recommended**: Python + python-simconnect + mido. Simplest, matches existing toolchain, runs on same PC as sim. Single .py file.

**Sim variables needed** (A320 example):
```
GENERAL ENG THROTTLE LEVER POSITION:1  → CC#7
TRAILING EDGE FLAPS LEFT PERCENT       → CC#11
ELEVATOR TRIM PCT                      → CC#64
SPOILERS HANDLE POSITION               → CC#2
```

### F-3.2 — HID Validation in MSFS

Current HID descriptor sends X/Y axes. Need to verify:
- MSFS recognizes device as joystick
- Axis mapping works (X axis = profile's control)
- No calibration drift
- No dead zones or scaling issues

**Test**: Plug in device → MSFS Controls → verify axis moves.

### F-3.4 — Bidirectional Sync

The hard problem: motor position must track the sim, but user push must override and feed back.

**Sync model**:
1. Companion app sends MIDI CC at ~20Hz (sim → device)
2. Device haptic layer receives via `haptic_set_position_normalized()`
3. User pushes motor → haptic snaps to new detent → HID reports new position
4. MSFS reads HID → sim variable changes
5. Companion app sees sim variable changed → sends matching CC (confirming)

**Conflict resolution**: Last writer wins. If user pushes, HID wins. If sim moves (autopilot), MIDI CC wins. Companion app backs off when HID and sim agree.

### Entry Criteria
- v0.2 complete ✅
- Windows PC with MSFS 2020/2024
- Device plugged in, profile selected

### Exit Criteria
- Companion app runs, reads sim throttle/trim, sends MIDI
- Motor follows sim control position
- User push reflected in sim within 100ms
- Profile documented for A320 (primary) and Cessna (secondary)

### Test Strategy
- **Manual**: Fly a circuit in MSFS, verify trim/throttle follow
- **Automated**: Replay saved SimConnect data → verify HID output matches

---

## v0.4 — "It Feels Right"

**Goal**: Fix known quality issues, production-grade robustness.

### Features

| ID | Feature | Priority | Effort |
|----|---------|----------|--------|
| F-4.1 | Encoder eccentricity calibration | MUST | 2 days |
| F-4.2 | Haptic endstop cascade fix | MUST | 3 days |
| F-4.3 | Thermal management (loaded operation) | MUST | 1 day |
| F-4.4 | Watchdog + error recovery | SHOULD | 1 day |
| F-4.5 | Config/calibration tool (profile select, endstop set) | SHOULD | 2 days |

### F-4.1 — Encoder Calibration

**Problem**: AS5600 magnet off-center → sinusoidal ±8° error at 0°/180°.
**Solution**: GenericSensor callback applying `offset = A * sin(θ + φ)`, calibrated at startup or stored in EEPROM.
**Impact**: Enables loaded limits (±1° accuracy).

### F-4.2 — Haptic Endstop Cascade

**Problem**: PID ring-down overshoot at endstops triggers detent walkthrough (6 experiments failed, documented in HAPTIC_ENDSTOP_INVESTIGATION.md).
**Approach** (not yet tried):
- Rate-limit detent transitions (max 1 per 200ms)
- Require velocity sign match (moving toward detent, not ringing past it)
- Integrated energy gate (accumulated intentional push energy threshold)
**Impact**: Safe detents at range limits. Critical for flaps/gear profiles.

### F-4.3 — Thermal Management

**Current**: 2V hard cap. Motor gets warm under sustained load.
**Need**: Exponential voltage backoff when current exceeds threshold. Monitor via motor voltage/current feedback. Warn via telemetry.

### F-4.5 — Config/Calibration Tool

The README describes: "a config/calibration app/script that selects the profile, allows configuring endstops, and aids parameterising the motor control."

**Scope**: Python GUI or TUI that:
- Lists profiles, sends A<n> to switch
- Walks user through endstop calibration (turn wheel to limit → mark)
- Shows live position + haptic detent state
- Saves calibration to EEPROM

### Entry Criteria
- v0.3 complete (sim integration works)
- Loaded operation reveals accuracy/thermal issues

### Exit Criteria
- Loaded limits (±1°) pass quality test suite
- No endstop cascade in any profile
- 2-hour continuous operation without thermal shutdown
- Config tool documented and tested

### Test Strategy
- **Encoder cal**: Compare motor angle vs external reference (protractor or second encoder)
- **Endstop**: Automated sweep test that moves past endstops, verifies no cascade
- **Thermal**: 2-hour soak test with periodic position changes, log temperature proxy (voltage feedback)
- **Quality suite**: Full matrix run with loaded limits

---

## v0.5 — "Two Hands"

**Goal**: Dual-motor support. Two independent axes on one Pico.

### Features

| ID | Feature | Priority | Effort |
|----|---------|----------|--------|
| F-5.1 | Second motor + encoder wiring | MUST | HW: 1 day |
| F-5.2 | Dual motor firmware (independent PID) | MUST | 3 days |
| F-5.3 | Dual HID axes (X = motor0, Y = motor1) | MUST | 1 day |
| F-5.4 | Dual profile assignment (e.g. throttle+trim) | SHOULD | 1 day |
| F-5.5 | I²C address conflict resolution (AS5600) | MUST | 1 day |

### F-5.5 — I²C Address Issue

AS5600 has fixed address 0x36. Two sensors on one I²C bus won't work.
**Options**:
1. **I²C multiplexer** (TCA9548A) — standard solution, $1 part
2. **Second I²C bus** — RP2040 has two I²C peripherals (I2C0 + I2C1), use different GPIO pins
3. **AS5600L** (programmable address variant) — drop-in, but less common

**Recommended**: Option 2 (second I²C bus on RP2040). Zero additional parts. SimpleFOC supports specifying Wire instance per sensor.

### Entry Criteria
- v0.4 encoder calibration works (per-sensor)
- Second motor + encoder physically wired

### Exit Criteria
- Both motors hold position independently
- HID reports X and Y axes from motor 0 and 1
- MIDI CC controls both axes (different CC# per axis)
- Quality test passes for each motor individually

### Test Strategy
- Per-motor quality suite (one motor at a time)
- Cross-talk test (command motor 0, verify motor 1 doesn't move)
- Simultaneous movement test

---

## v1.0 — "Release"

**Goal**: First stable, documented, reproducible release.

### Entry Criteria
- v0.5 dual motor working
- All quality goals met (loaded limits)
- Companion app tested with MSFS
- Documentation complete

### Checklist
- [ ] All tests green (quality suite + companion + endstop + thermal)
- [ ] ARCHITECTURE.md, AIRCRAFT_PROFILES.md, README.md current
- [ ] Hardware BOM (bill of materials) and wiring diagram
- [ ] Enclosure design files (3D print or laser cut)
- [ ] Build + flash instructions for end user
- [ ] `git flow release finish v1.0` → tag on main
- [ ] GitHub release with .uf2 binary artifact

---

## Integration & Test Strategy

### Test Pyramid

```
         ▲
        /  \      Manual: fly in MSFS, feel the detents
       / E2E \    
      /────────\  Integration: companion → MIDI → motor → HID → sim
     / Integr.  \
    /────────────\  Hardware-in-loop: quality_goals_test_suite.py
   /   HIL Tests  \   (Commander T → @T telemetry → assert)
  /────────────────\
 /   Unit (headless) \  test/unit/: config parsing, sim_device
/══════════════════════\
```

### Test Matrix per Milestone

| Test | v0.1 | v0.2 | v0.3 | v0.4 | v0.5 | v1.0 |
|------|------|------|------|------|------|------|
| Build compiles | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Unit tests pass | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HIL quality suite (unloaded) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HIL quality suite (loaded) | — | — | — | ✅ | ✅ | ✅ |
| Profile switch + haptic | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| Endstop cascade test | — | — | — | ✅ | ✅ | ✅ |
| Companion app ↔ sim | — | — | ✅ | ✅ | ✅ | ✅ |
| HID recognized in MSFS | — | — | ✅ | ✅ | ✅ | ✅ |
| Thermal soak (2h) | — | — | — | ✅ | ✅ | ✅ |
| Dual motor cross-talk | — | — | — | — | ✅ | ✅ |
| Full regression | — | — | — | — | — | ✅ |

### CI Pipeline

```
  push to dev
      │
      ├─ Build gate (pio run, size check)
      ├─ Unit tests (pytest test/unit/)
      └─ HIL tests (if runner has motor)
           ├─ Upload firmware
           ├─ quality_goals_test_suite.py --matrix
           └─ Artifact: test_results.json

  git flow release start vX.Y
      │
      └─ Full regression (all profiles, loaded + unloaded, thermal)
```

### Branch Strategy (unchanged from AGENTS.md)

```
main ← release/vX.Y ← dev ← feature/xxx
                               ← hotfix/xxx
                               ← experiment/xxx (never merged)
```

- **feature/**: One per milestone feature (F-3.1, F-4.2, etc.)
- **release/**: Created from dev when milestone complete, polish only
- **main**: Only via `git flow release finish` (human runs)

---

## Hardware Construction Roadmap

### Current State: "Breadboard Prototype"

```
  ┌─────────────┐
  │  RP2040 Pico│──USB──► PC
  │             │
  │  I2C (0,1)  │◄──► AS5600 ──magnets── BLDC Motor
  │  PWM (13-10)│──► 3PWM Driver ──────── BLDC Motor
  └─────────────┘
```

**What exists**: One motor + one encoder on a breadboard. Works. 12V PSU, 3PWM driver, magnet-on-shaft.

### Phase A: Single-Motor Enclosure (for v0.3)

**Goal**: Stable single-axis device you can plug in and use with MSFS.

| Step | Task | Parts | Notes |
|------|------|-------|-------|
| A1 | Design motor mount bracket | 3D print or aluminum L-bracket | Motor shaft exposed for knob |
| A2 | Knob/wheel for motor shaft | 3D print, ~40mm diameter | Knurled for grip (trim) or lever shape (throttle) |
| A3 | PCB or perfboard for driver + Pico | Custom PCB or solder perfboard | Eliminate breadboard wires |
| A4 | Enclosure (box) | 3D print, ~80×60×40mm | USB port accessible, knob on top |
| A5 | Strain relief for USB cable | Cable gland or printed clip | Prevent disconnect during use |
| A6 | Power: USB-only or 12V jack? | Depends on motor current draw | If motor draws >500mA, need barrel jack |

**Decision needed**: Can the motor run on USB 5V (via Pico VBUS)? If yes, one-cable solution. If not (likely — BLDC typically wants 6-12V), need separate power.

**BOM estimate (single motor)**:
| Part | Qty | ~Cost | Source |
|------|-----|-------|--------|
| RP2040 Pico | 1 | €4 | aliexpress |
| AS5600 breakout | 1 | €2 | aliexpress |
| BLDC motor (2804) | 1 | €8 | aliexpress |
| 3PWM driver (L6234 or similar) | 1 | €5 | aliexpress |
| Diametric magnet 6×2.5mm | 1 | €1 | aliexpress |
| 12V 1A PSU | 1 | €5 | local |
| Enclosure (3D printed) | 1 | €2 | filament cost |
| Knob (3D printed) | 1 | €0.50 | filament cost |
| Perfboard + connectors | 1 | €2 | local |
| **Total** | | **~€30** | |

### Phase B: Dual-Motor Board (for v0.5)

| Step | Task | Notes |
|------|------|-------|
| B1 | Second AS5600 on I2C1 (different GPIO pins) | Wire0 → motor0, Wire1 → motor1 |
| B2 | Second 3PWM channel (GPIO 6-9 or similar) | Check RP2040 PWM channel availability |
| B3 | Larger enclosure | Two knobs side-by-side or stacked |
| B4 | Shared power rail | Both motors from same 12V supply |

**RP2040 pin budget**:
| Function | Motor 0 | Motor 1 |
|----------|---------|---------|
| PWM A/B/C | GP13/12/11 | GP6/7/8 |
| Enable | GP10 | GP9 |
| I²C SDA | GP4 (I2C0) | GP2 (I2C1) |
| I²C SCL | GP5 (I2C0) | GP3 (I2C1) |
| **Total pins** | 6 | 6 |
| Remaining | 14 GPIO free for buttons, LEDs, etc. |

### Phase C: Production Board (for v1.0)

| Step | Task | Notes |
|------|------|-------|
| C1 | KiCad PCB design | Single board: Pico footprint + 2× driver + 2× encoder connector |
| C2 | JLCPCB / PCBWAY order | ~€15 for 5 boards |
| C3 | SMD assembly or hand-solder | Driver IC + passives |
| C4 | Final enclosure with interchangeable knobs | Trim wheel / throttle lever / flap lever attachments |
| C5 | Wiring diagram + build instructions | For reproducibility |

### Mechanical Attachments (interchangeable)

| Profile | Knob Style | Notes |
|---------|-----------|-------|
| Trim (Cessna/A320/Glider) | 40mm knurled wheel | Smooth rotation, no end stops |
| Throttle (Cessna) | 30mm round knob | Smooth, full rotation |
| A320 Throttle | Lever arm (60mm) | Gate detents felt through lever throw |
| Flaps | Small lever with positions marked | Click detents at each position |
| Gear | Toggle switch style | Two-position with strong click |
| Spoiler | Slider-style lever | Linear motion mapped to rotation |

**Common shaft interface**: D-shaft adapter (3D print) that press-fits onto motor shaft. All knobs mount to the D-shaft.

---

## Timeline Estimate

Assumes ~8 hours/week of human + agent time combined.

| Version | Weeks | Cumulative | Gate |
|---------|-------|------------|------|
| v0.1 | — | Done | Build + motor moves |
| v0.2 | — | Done | Profiles + haptic |
| v0.3 | 3–4 | +4 weeks | Flies in MSFS |
| v0.4 | 2–3 | +7 weeks | Quality + robustness |
| v0.5 | 2–3 | +10 weeks | Dual motor |
| v1.0 | 2 | +12 weeks | Release |

**Critical path**: v0.3 (companion app) is the longest single item and the first that delivers real user value. Start there.

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Endstop cascade unfixable | HIGH | MEDIUM | Rate-limit transitions; accept softer endstops; or disable endstops for now |
| Encoder eccentricity > ±1° | MEDIUM | HIGH | Software cal (GenericSensor); or replace magnet; or accept wider tolerance |
| MSFS doesn't recognize HID | HIGH | LOW | Standard gamepad descriptor; test early (v0.3 F-3.2) |
| 12V motor can't run on 5V USB | MEDIUM | HIGH | Plan for barrel jack from Phase A; two-cable-is-fine |
| AS5600 I²C conflict (dual motor) | MEDIUM | LOW | Second I²C bus on RP2040 — zero parts needed |
| Agent burns time without progress | MEDIUM | MEDIUM | AGENTS.md rule: stop and document when stuck |
| Scope creep (too many profiles) | LOW | MEDIUM | Freeze at 10 profiles until v1.0 |
