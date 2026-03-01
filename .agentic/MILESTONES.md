# Milestone Plan — FOC Joystick

**Created**: 2026-03-01, **Revised**: 2026-03-01
**Basis**: dev HEAD, honest assessment of what actually works

---

## Version Summary

| Version | Codename | Gate | Hardware |
|---------|----------|------|----------|
| **v0.1** | "It Works" | Motor clicks, endstops hold, multi-rev, useful HID joystick | Breadboard, bare motor |
| **v0.2** | "Trim Wheel" | Physical trim wheel, recognized and usable in MSFS | Enclosure + wheel knob |
| **v0.3** | "A320 Throttle" | Stick/lever form factor, A320 throttle gates work in MSFS | Enclosure + lever arm |
| **v0.4** | "Sim Feedback" | Sim sets motor position (autopilot, aircraft switch) | Same hardware + companion app |

**Later** (not planned in detail): dual motor, production PCB, config tool.

---

## v0.1 — "It Works" 🔜 CURRENT

**Goal**: A dummy motor on a breadboard that clicks to detent positions, has functional endstops, supports multiple revolutions, and gives a useful joystick axis in Windows.

### What Already Works
- RP2040 + AS5600 + BLDC 7pp + 3PWM driver on breadboard
- SimpleFOC angle mode, unbounded rotation (-∞ to +∞)
- PID tuned (P=16, I=0.2, D=1.0, vel_P=0.1, vel_I=0.5, Tf=0.001)
- 10 control profiles with ControlProfile struct
- Custom DetentPoint maps with per-detent strength
- Gate mode, smooth mode, uniform detents
- USB composite: HID joystick + MIDI + CDC serial
- Commander serial (M/T/A/W commands)
- Telemetry @T at 10Hz, EMA RMS + ring buffer
- MIDI CC → position, CC#121 → profile switch
- Profile persistence in EEPROM + USB re-enumerate on switch
- Quality test suite (8 tests × 6 sequences)

### What Doesn't Work Yet

| ID | Problem | Status | Notes |
|----|---------|--------|-------|
| F-1.1 | **Haptic endstop cascade** | OPEN | PID ring-down past endstop triggers walkthrough of ALL detents. 6 experiments failed. |
| F-1.2 | **HID not validated as joystick** | UNTESTED | Windows "Game Controllers" never checked. Could be broken descriptor. |
| F-1.3 | **Encoder eccentricity** | DEFERRED | ±8° sinusoidal error. Unloaded limits (±10°) accommodate it. |
| F-1.4 | **Main branch stale** | KNOWN | 5 commits, never updated from dev. |

### F-1.1 — Endstop Cascade (the hard one)

**Problem**: When motor overshoots an endstop, PID ring-down oscillation triggers snap_to_detent repeatedly, walking through every detent position.

**Failed approaches** (documented in HAPTIC_ENDSTOP_INVESTIGATION.md):
1. Stateless rewrite
2. Guard zone
3. 5-state machine
4. Velocity gate (3 variants)

**Remaining hypotheses** (not yet tried):
- **Rate-limit**: Max 1 detent transition per 200ms. Simple, predictable.
- **Velocity sign gate**: Only snap if motor velocity matches movement direction (not ringing).
- **Energy threshold**: Require accumulated intentional push energy before allowing transition.
- **Softer endstops**: Instead of hard wall, make endstop a very strong spring. No abrupt reversal = no ring-down.

**Acceptance**: Motor at endstop, push hard past it, release. Motor returns to endstop. No detent walkthrough.

### F-1.2 — HID Joystick Validation

**Test steps** (manual, takes 5 minutes):
1. Plug device into Windows PC
2. Open "Set up USB game controllers" (joy.cpl)
3. Verify device appears with correct name
4. Rotate motor shaft → verify axis moves smoothly 0–100%
5. Verify no axis jitter at rest

**Acceptance**: Windows sees a joystick with at least one axis that tracks motor position.

### Entry Criteria
- (None — this is where we are)

### Exit Criteria
- [ ] Detent clicks work at defined positions
- [ ] Endstops hold without cascade
- [ ] Multi-revolution profiles work (e.g. trim: 720°+)
- [ ] HID joystick recognized in Windows
- [ ] HID axis tracks motor position smoothly

### Test Strategy
- HIL quality suite (unloaded limits)
- Manual: endstop push test per profile with detents
- Manual: Windows joy.cpl verification

---

## v0.2 — "Trim Wheel"

**Goal**: A physical trim wheel that you plug into MSFS and use as elevator trim.

This is the first version a human would actually use. Requires hardware construction and MSFS validation.

### Features

| ID | Feature | Priority | Notes |
|----|---------|----------|-------|
| F-2.1 | Trim wheel hardware (enclosure + knob) | MUST | 3D-printed, wheel on shaft |
| F-2.2 | Stable wiring (no breadboard) | MUST | Perfboard or screw terminals |
| F-2.3 | MSFS recognizes device as joystick | MUST | Assign axis to elevator trim |
| F-2.4 | Smooth feel suitable for trim operation | MUST | No detent clicks, resistance only |
| F-2.5 | Trim-appropriate range (720°+) | MUST | Already implemented in profiles |
| F-2.6 | Thermal OK for 1-hour flight | SHOULD | Monitor motor temp during session |

### F-2.1 — Trim Wheel Hardware

**Form factor**: Vertical wheel, ~40mm diameter, knurled edge, mounted in a small box.

```
  Side view:           Top view:
  ┌──────────┐         ┌──────────┐
  │    ◯◯    │ ← wheel │  ┌────┐  │
  │  ┌────┐  │         │  │Pico│  │
  │  │mot │  │         │  └────┘  │
  │  │ or │  │         │  [drv]   │
  │  └────┘  │         └────┤├────┘
  └────┤├────┘              USB
       USB
```

**Build steps**:
| Step | Task | Parts |
|------|------|-------|
| H-2.1 | Motor mount (L-bracket or printed cradle) | 3D print |
| H-2.2 | Trim wheel knob (press-fit on shaft) | 3D print, ~40mm |
| H-2.3 | Solder perfboard (Pico + driver) | Perfboard, headers, wire |
| H-2.4 | Box enclosure (wheel protrudes from top/side) | 3D print, ~80×60×50mm |
| H-2.5 | 12V barrel jack + USB port accessible | Panel mount jack |

**BOM**:
| Part | Qty | ~Cost |
|------|-----|-------|
| RP2040 Pico | 1 | €4 |
| AS5600 breakout | 1 | €2 |
| BLDC motor (2804) | 1 | €8 |
| 3PWM driver board | 1 | €5 |
| Diametric magnet 6×2.5mm | 1 | €1 |
| 12V 1A PSU | 1 | €5 |
| 3D-printed parts (enclosure + wheel) | 1 | €3 |
| Perfboard + connectors | 1 | €2 |
| **Total** | | **~€30** |

### F-2.3 — MSFS Validation

**Test steps**:
1. Plug in device → Windows "Game Controllers" → verify axis
2. MSFS → Options → Controls → search for device by name
3. Assign X axis → Elevator Trim Axis
4. Fly Cessna 172 → trim nose up/down → verify aircraft responds
5. Verify smooth, proportional response (no dead zones, no jumps)

**Acceptance**: Fly a circuit in Cessna 172 using only the trim wheel for pitch. Aircraft trimmable to hands-off stable flight.

### Entry Criteria
- v0.1 complete (endstops work, HID validated)
- 3D printer available
- Soldering iron available

### Exit Criteria
- [ ] Physical trim wheel assembled and enclosed
- [ ] No breadboard wires — soldered connections
- [ ] MSFS assigns axis to elevator trim
- [ ] Cessna 172 trimmable to hands-off flight
- [ ] 1-hour flight without thermal or USB issues

### Test Strategy
- Manual: Build hardware, fly in MSFS
- HIL: Quality suite still passes after hardware assembly
- Thermal: 1-hour flight, check motor temperature after

---

## v0.3 — "A320 Throttle"

**Goal**: Same hardware platform, but now in a lever/stick form factor. The A320 throttle gates (IDLE → CLB → FLX → TOGA) click convincingly, and MSFS responds to throttle position.

### Features

| ID | Feature | Priority | Notes |
|----|---------|----------|-------|
| F-3.1 | Lever/stick knob for motor shaft | MUST | 3D-printed, ~60mm arm |
| F-3.2 | Gate detents felt through lever throw | MUST | Already in firmware (gate mode) |
| F-3.3 | MSFS throttle axis assignment | MUST | Assign to throttle lever axis |
| F-3.4 | Throttle range mapping (0-100%) | MUST | Verify HID output maps correctly |
| F-3.5 | Profile switch Trim ↔ Throttle | SHOULD | MIDI CC#121 or Commander A<n> |

### F-3.1 — Lever Hardware

**Form factor**: Lever arm clamped/press-fit to motor shaft. Pivots ~90° forward/back.

```
  Side view (lever back = IDLE):
  
       TOGA ←─── lever ───→ IDLE
              ╲         ╱
               ╲  ◯◯  ╱
                ╲    ╱
                │motor│
                └─────┘
```

The enclosure is the same box as v0.2 — only the knob changes. This validates the interchangeable attachment concept.

**Design constraint**: Lever arm must not exceed the motor's torque capability at 2V. Short arm (~60mm) with low-friction pivot.

### F-3.3 — MSFS Throttle Validation

**Test steps**:
1. Switch to A320 throttle profile (MIDI or Commander)
2. MSFS → Controls → assign axis to Throttle 1
3. Fly A320 → push lever forward through gates
4. Verify: IDLE click → CLB click → FLX/MCT click → TOGA
5. Verify: throttle percentage in cockpit matches lever position

**Acceptance**: A320 throttle moves through gates with clear detent feel. Sim responds proportionally.

### Entry Criteria
- v0.2 complete (trim wheel works in MSFS)
- Lever knob designed and printed

### Exit Criteria
- [ ] Lever arm assembled, swappable with trim wheel
- [ ] A320 gates felt clearly in lever throw
- [ ] MSFS throttle responds to lever position
- [ ] Profile switch between trim and throttle works

### Test Strategy
- Manual: Fly A320 approach with gate transitions
- HIL: Quality suite with A320 throttle profile

---

## v0.4 — "Sim Feedback"

**Goal**: The flight sim can set the motor position. When autopilot trims, the trim wheel moves. When you switch aircraft, the throttle moves to match.

This closes the feedback loop: sim → motor, not just motor → sim.

### Features

| ID | Feature | Priority | Notes |
|----|---------|----------|-------|
| F-4.1 | Companion app (SimConnect → MIDI) | MUST | Python script on Windows |
| F-4.2 | Motor follows sim variable | MUST | MIDI CC → haptic_set_position_normalized |
| F-4.3 | Bidirectional conflict resolution | MUST | User push overrides sim; sim overrides at rest |
| F-4.4 | Aircraft auto-detect → profile switch | NICE | SimConnect TITLE → matching profile |
| F-4.5 | Companion UI (tray icon or terminal) | NICE | Show status, allow manual override |

### F-4.1 — Companion App

**Architecture**:
```
  MSFS ──SimConnect──► companion.py ──MIDI CC──► RP2040
                                                    │
  MSFS ◄──────────────── HID joystick ◄────────────┘
```

**Implementation**: Python + python-simconnect + mido. Single .py file.

**Sim variables**:
| Profile | SimConnect Variable | MIDI CC |
|---------|-------------------|---------|
| Cessna Trim | ELEVATOR TRIM PCT | CC#64 |
| Cessna Throttle | GENERAL ENG THROTTLE LEVER POSITION:1 | CC#7 |
| A320 Trim | ELEVATOR TRIM PCT | CC#64 |
| A320 Throttle | GENERAL ENG THROTTLE LEVER POSITION:1 | CC#7 |
| A320 Flaps | TRAILING EDGE FLAPS LEFT PERCENT | CC#11 |
| A320 Spoilers | SPOILERS HANDLE POSITION | CC#2 |

**Update rate**: 10–20Hz from sim → MIDI. Device already handles MIDI CC at main loop rate.

### F-4.3 — Bidirectional Sync

The hard problem. Two entities want to control the motor position.

**Protocol**:
1. **Sim → Motor**: Companion sends MIDI CC at ~20Hz. Motor moves to match.
2. **User → Sim**: User pushes motor. HID reports new position. MSFS reads it.
3. **Conflict**: Companion sees HID ≠ sim position → backs off for 500ms (user is pushing).
4. **Settle**: When HID and sim agree within tolerance → companion resumes tracking.

**Key insight**: The MIDI CC → haptic position path already exists. The companion app just needs to read SimConnect and write MIDI. The device firmware doesn't need to change much.

### Entry Criteria
- v0.3 complete (throttle works in MSFS)
- Windows PC running MSFS + Python

### Exit Criteria
- [ ] Companion app runs, reads sim state, sends MIDI
- [ ] Autopilot trim change → trim wheel physically moves
- [ ] User push → sim responds within 100ms
- [ ] No oscillation between sim and user input
- [ ] Aircraft switch: motor moves to new aircraft's position

### Test Strategy
- Manual: Engage autopilot, watch trim wheel move
- Manual: Push throttle, verify sim responds, then release, verify companion re-syncs
- Automated: Replay SimConnect log → verify MIDI output matches expected

---

## Future (unplanned)

These are real goals but not committed to a version yet.

| Idea | Depends On | Complexity |
|------|-----------|------------|
| Dual motor (throttle + trim simultaneously) | HW: 2nd motor, I²C1 bus, pin budget OK | HIGH |
| Encoder eccentricity calibration | GenericSensor + EEPROM cal table | MEDIUM |
| Config/calibration TUI app | Serial Commander extensions | LOW |
| Production PCB (KiCad) | Stable pin assignment from dual motor | HIGH |
| More aircraft profiles | Research per type | LOW |
| Thermal management (voltage backoff) | Load testing → need longer flight sessions | MEDIUM |
| Interchangeable knob system (D-shaft) | Mechanical design iteration | MEDIUM |

---

## Integration & Test Strategy

### Test Pyramid

```
         ▲
        /  \      Manual: fly in MSFS, feel detents
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

| Test | v0.1 | v0.2 | v0.3 | v0.4 |
|------|------|------|------|------|
| Build compiles | ✅ | ✅ | ✅ | ✅ |
| Unit tests pass | ✅ | ✅ | ✅ | ✅ |
| HIL quality suite (unloaded) | ✅ | ✅ | ✅ | ✅ |
| Endstop holds (no cascade) | ✅ | ✅ | ✅ | ✅ |
| HID axis in Windows joy.cpl | ✅ | ✅ | ✅ | ✅ |
| MSFS assigns axis | — | ✅ | ✅ | ✅ |
| MSFS fly-test (manual) | — | ✅ | ✅ | ✅ |
| Gate detents in lever throw | — | — | ✅ | ✅ |
| Companion app → motor moves | — | — | — | ✅ |
| Bidirectional sync stable | — | — | — | ✅ |
| Thermal soak (1h flight) | — | ✅ | ✅ | ✅ |

### CI Pipeline

```
  push to dev
      │
      ├─ Build gate: pio run, size check
      ├─ Unit tests: pytest test/unit/
      └─ HIL tests (if runner has motor):
           ├─ Upload firmware
           ├─ quality_goals_test_suite.py
           └─ Artifact: test_results.json

  git flow release start vX.Y
      │
      └─ Full regression + MSFS manual test
```

### Branch Strategy (per AGENTS.md)

```
main ← release/vX.Y ← dev ← feature/xxx
                               ← hotfix/xxx
                               ← experiment/xxx (never merged)
```

- **feature/**: One branch per feature ID (F-1.1, F-2.3, etc.)
- **release/**: From dev when milestone exit criteria met
- **main**: Only via `git flow release finish` (human runs)

---

## Hardware Construction Roadmap

### Current State: Breadboard

```
  ┌─────────────┐
  │  RP2040 Pico│──USB──► PC
  │             │
  │  I2C0 (4,5)│◄──► AS5600 ──magnet── BLDC 7pp
  │  PWM (13-10)│──► 3PWM Driver ──────── BLDC 7pp
  └─────────────┘
     Breadboard, 12V PSU, loose wires
```

### v0.1 Hardware: Nothing to build
Use the breadboard. Bare motor shaft is fine for testing.

### v0.2 Hardware: Trim Wheel Enclosure

| Step | Task | Output |
|------|------|--------|
| H-2.1 | Design motor cradle (motor screw holes → box) | STL file |
| H-2.2 | Design trim wheel knob (press-fit on shaft, ~40mm) | STL file |
| H-2.3 | Solder perfboard (Pico + driver + AS5600 headers) | Wired board |
| H-2.4 | Design enclosure (wheel protrudes, USB + 12V accessible) | STL file |
| H-2.5 | Print, assemble, test | Physical device |

### v0.3 Hardware: Lever Arm (delta from v0.2)

| Step | Task | Output |
|------|------|--------|
| H-3.1 | Design lever knob (press-fit on shaft, ~60mm arm) | STL file |
| H-3.2 | Print and swap with trim wheel | Same enclosure, new knob |

The enclosure stays the same. Only the knob changes.

### v0.4 Hardware: Nothing to build
Same device. Companion app is pure software.

### RP2040 Pin Budget (current)

| Function | Pins | GPIO |
|----------|------|------|
| PWM A/B/C | 3 | GP11/12/13 |
| Enable | 1 | GP10 |
| I²C SDA/SCL | 2 | GP4/GP5 |
| USB | 1 | USB DP/DM (dedicated) |
| **Used** | **6** | |
| **Free** | **20** | For buttons, LEDs, 2nd motor later |

### BOM (one unit)

| Part | ~Cost |
|------|-------|
| RP2040 Pico | €4 |
| AS5600 breakout | €2 |
| BLDC motor (2804) | €8 |
| 3PWM driver | €5 |
| Diametric magnet | €1 |
| 12V 1A PSU | €5 |
| 3D-printed parts | €3 |
| Perfboard + wire | €2 |
| **Total** | **~€30** |

---

## Timeline Estimate

Assumes ~8 hours/week of human + agent time combined.

| Version | Effort | Cumulative | Blocker |
|---------|--------|------------|---------|
| v0.1 | 2–4 weeks | 2–4 wk | Endstop cascade fix |
| v0.2 | 3–4 weeks | 5–8 wk | 3D print + MSFS test |
| v0.3 | 1–2 weeks | 6–10 wk | Lever design only (firmware exists) |
| v0.4 | 3–4 weeks | 9–14 wk | Companion app + sync protocol |

**Critical path**: v0.1 endstop cascade is the blocker. Everything else is ready.

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Endstop cascade unfixable | HIGH | MEDIUM | Rate-limit transitions; or soft spring endstops (no hard wall) |
| HID descriptor broken in MSFS | HIGH | LOW | Test early in v0.1 (F-1.2); standard gamepad descriptor |
| Motor torque too weak for lever | MEDIUM | MEDIUM | Shorter lever arm; or higher voltage (carefully) |
| 12V motor can't run on USB 5V | LOW | HIGH | Already planning barrel jack; two cables is fine |
| Companion app SimConnect issues | MEDIUM | MEDIUM | python-simconnect is mature; MobiFlight as fallback |
| Encoder error breaks MSFS calibration | MEDIUM | MEDIUM | Software cal in Future; or MSFS dead zone setting |
| Agent burns time without progress | MEDIUM | MEDIUM | AGENTS.md: stop and document when stuck |
