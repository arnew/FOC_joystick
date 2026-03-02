# Roadmap — FOC Joystick

Version plan with increments. Detailed exit criteria, test results, and
hardware plans are in [.agentic/MILESTONES.md](.agentic/MILESTONES.md).
Requirements are tracked in [REQUIREMENTS.md](REQUIREMENTS.md).

---

## v0.1 — "It Works" ✅ RELEASING

Motor on breadboard: detent clicks, endstops, multi-revolution, HID joystick.

| What | Status |
|------|--------|
| SimpleFOC angle mode, PID tuned | Done |
| 11 control profiles (Cessna/A320/Glider/Bench) | Done |
| Haptic layer: detents, gates, smooth, endstops | Done |
| USB composite: HID + MIDI + CDC serial | Done |
| 16-bit HID axis, boot centering, dead-zone fix | Done |
| Quality suite 7/8 pass (1 accepted) | Done |

**Deferred to v0.2**: Windows joy.cpl validation, fast-transition overshoot tuning.

---

## v0.2 — "Trim Wheel" 🔜 NEXT

Physical trim wheel for MSFS elevator trim. First version a human uses.

| What | Priority |
|------|----------|
| Trim wheel hardware (3D-printed enclosure + knob) | MUST |
| Soldered wiring (no breadboard) | MUST |
| Windows HID joy.cpl validation (carried F-1.2) | MUST |
| MSFS axis assignment → fly Cessna 172 | MUST |
| Fast transitions tuning <10° overshoot (carried F-1.5) | SHOULD |
| Thermal soak: 1-hour flight OK | SHOULD |

**Entry**: v0.1 released, Windows PC available, 3D printer available.

---

## v0.3 — "A320 Throttle"

Lever/stick form factor. A320 throttle gates (IDLE → CLB → TOGA) in MSFS.

| What | Priority |
|------|----------|
| Lever knob (press-fit, ~60mm arm) | MUST |
| A320 gate detents felt through lever throw | MUST |
| MSFS throttle axis assignment | MUST |
| Profile switch Trim ↔ Throttle | SHOULD |

**Entry**: v0.2 complete. Same enclosure, only knob changes.

---

## v0.4 — "Sim Feedback"

Companion app closes the loop: sim → motor (autopilot trim moves wheel).

| What | Priority |
|------|----------|
| Companion app (SimConnect → MIDI CC → motor) | MUST |
| Bidirectional sync, no oscillation | MUST |
| Aircraft auto-detect → profile switch | NICE |

**Entry**: v0.3 complete, Windows PC with MSFS + Python.

---

## Backlog (ungrouped, unversioned)

- Dual motor (throttle + trim simultaneously)
- Encoder eccentricity calibration (±8° sinusoidal correction)
- Config/calibration TUI app
- Production PCB (KiCad)
- More aircraft profiles
- Thermal management (voltage backoff)
- Interchangeable knob system (D-shaft)
