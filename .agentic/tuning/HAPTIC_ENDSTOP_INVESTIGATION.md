# Haptic Endstop & Overshoot Investigation

**Status**: OPEN — root cause identified, no working fix yet  
**Date**: 2026-03-01  
**Branch**: `feature/trim-wheel-preview` (commit 50fd433 = last stable)

---

## 1. Problem Statement

The haptic detent system works correctly for normal in-range navigation
but **cascades through all detents** after the motor returns from a
large overshoot (multiple revolutions past an endstop).

**Symptoms observed**:
- User pushes motor 3–5 revolutions past 180° endstop
- Motor winds back to range (PID returns it)
- Target walks: 180→170→160→…→0, one detent per PID oscillation peak
- Eventually settles at detent 0, where it gets "stuck" (PID holds
  motor at −8° but `constrain()` clips to 0°, masking the error)

**The cascade takes 5–30 seconds depending on overshoot magnitude.**

## 2. Physical Setup

| Parameter         | Value                        |
|-------------------|------------------------------|
| Motor             | BLDC 7pp, AS5600 I2C sensor  |
| Controller        | RP2040 (Pico)                |
| SimpleFOC         | v2.4.0, angle mode           |
| PID               | P=16 I=0.2 D=1.0 vel_P=0.1 vel_I=0.5 |
| LPF Tf            | 0.001                        |
| Voltage limit     | 2V (thermal)                 |
| Haptic range      | 180° (0°–180°), 18 detents (10° step) |
| Hysteresis        | 60% of step = 6°             |
| PID holding error | ~3° mid-range, ~8° at endstops |

## 3. Root Cause Analysis

### The cascade mechanism

Each detent transition **moves the PID target in the direction the
motor is already overshooting**, creating positive feedback:

```
Motor returning from overshoot, PID aims at 180°:
  motor reads 192° → overshoot past 180° target
  → constrain(192, 0, 180) = 180° → deviation = 0 → no transition yet
  → PID pulls motor back, undershoots to 168°
  → constrain(168, 0, 180) = 168° → deviation = 168−180 = −12°
  → −12° > 6° threshold → decrement to detent 17, target now 170°
  → PID chases 170°, overshoots to 158°
  → deviation = 158−170 = −12° → decrement to detent 16, target 160°
  → ... cascade continues to detent 0
```

**Key insight**: The PID cannot settle on a target without overshoot.
Every overshoot triggers the next detent, which moves the target
further in the overshoot direction. This is a positive feedback loop.

### Why normal operation works

During normal user interaction:
- The user pushes slowly (1–2°/s)
- The deviation grows gradually to threshold
- One transition fires, PID moves 10° to new detent
- PID overshoot is ~3° (within the 6° threshold of the NEXT detent)
- Motor settles, no cascade

### Why large overshoot breaks it

- PID returning from 1000°+ overshoot has high velocity (~10–40 rad/s)
- Each oscillation around the target overshoots by 10–20°
- That's 1–2 full detent steps per oscillation
- Multiple transitions can fire per ring-down cycle

## 4. Experiments Conducted

### Experiment 1: Delta-accumulator → Stateless rewrite

**Hypothesis**: The delta-accumulator design integrates PID jitter,
causing drift. A stateless position+hysteresis design won't accumulate.

**Result**: ✅ Fixed rest-state drift. ❌ Did NOT fix post-overshoot
cascade. The cascade is position-based, not integration-based.

**Commit**: 50fd433

### Experiment 2: Guard zone (30° past range)

**Hypothesis**: If motor is far outside range, freeze haptic state.
Only re-engage when motor returns close.

**Result**: ❌ Guard correctly froze during overshoot, but on re-entry
the PID ring-down still cascaded. The re-entry snap (to nearest detent
at boundary) was immediately followed by oscillations that triggered
further transitions.

### Experiment 3: 5-state machine (INIT/TRACKING/RESYNC/GUARD/SETTLING)

**Hypothesis**: A SETTLING state that waits for motor to truly stop
(500 consecutive ticks within half-step of target) before resuming
TRACKING will prevent ring-down cascade.

**Problems found**:
1. PID endstop error (~8°) exceeds settle threshold (5°), so SETTLING
   never completes without a timeout
2. The timeout (3s) eventually releases into TRACKING where the
   cascade happens anyway
3. Endstop escape requires 14° push (8° PID error + 6° threshold)
   — feels completely stuck

**Added fixes**: 3s timeout, endstop escape using raw motor angle.
**Result**: ❌ Still cascades after timeout expires.

### Experiment 4: Three approach variants (A/B/C)

Built three UF2 firmwares with `#if HAPTIC_APPROACH`:

| Approach | Strategy | Result |
|----------|----------|--------|
| A: Loose settle | step×1.2 tolerance, 50 ticks, 500ms timeout | ❌ Same cascade — loose tolerance lets oscillations through |
| B: Window settle | Track min/max over 200-tick windows, settle when band < step×0.5 | ❌ Same cascade — 3s timeout fires before settling, then cascade |
| C: No settling | No SETTLING state, GUARD→RESYNC, tight reentry (within 1 step) | ❌ Same cascade — RESYNC 1s timeout releases into TRACKING, cascade |

**Key learning**: No gating strategy between GUARD and TRACKING can
work because the timeout always eventually fires, and TRACKING always
cascades during ring-down.

### Experiment 5: Velocity gate (minimal rewrite)

**Hypothesis**: Don't evaluate detent transitions when motor velocity
exceeds 3 rad/s. This eliminates the state machine entirely — just
one `if (|vel| > gate) return;` check.

**Result**: ❌ PID ring-down oscillates like a sine wave. Velocity
passes through zero at each oscillation peak — and at those peaks,
the position deviation is maximum. Transitions fire at every
zero-crossing.

**File**: Rewrote haptic_layer.cpp from 536→310 lines. Added
`get_motor_velocity()` API to motor_control.

### Experiment 6: Velocity gate + 500ms cooldown

**Hypothesis**: Block transitions for 500ms after last time motor
exceeded velocity gate. This catches zero-crossing peaks.

**Result**: ❌ Completely broken — even normal detent navigation
(test 1) stopped working. A normal user push briefly exceeds
3 rad/s, then the 500ms cooldown blocks the transition that
should fire 50–200ms later.

**Key learning**: Velocity and user-push are not separable with a
simple threshold. The PID response to a user push looks similar to
PID response recovering from overshoot.

## 5. Open Hypotheses

### H1: The problem is unsolvable with position-only tracking

The fundamental issue: **haptic detent transitions and PID ring-down
both look the same in position space**. A 12° deviation from a
detent could be a user pushing or PID overshooting. We need a signal
that distinguishes them.

### H2: Track integrated energy / displacement

Instead of instantaneous velocity, track total angular displacement
in recent history. PID ring-down covers hundreds of degrees in a few
seconds; a user push covers 10–20°. A sliding-window absolute
displacement tracker could distinguish them.

### H3: Limit detent transitions per second

Cap at 1–2 transitions per second. A user pushing through detents at
10°/step moves at most 2 steps/s. PID ring-down tries 5–10 steps/s.
Simple rate limiter might work without breaking normal use.

### H4: Re-snap after settling instead of during ring-down

Don't try to track during return from overshoot at all. When the motor
was outside range, mark a "just returned" flag. Keep monitoring
position but don't allow transitions until: (a) motor velocity has been
below threshold for N seconds AND (b) position has been stable for N
seconds. Only then do a single snap to nearest detent and resume
tracking. This is the SETTLING approach but with much more aggressive
criteria (e.g., 2s of both low velocity AND stable position).

### H5: Coarser detents

With 9 detents (20° step, 12° threshold), mid-range PID error (3°)
leaves 9° of margin. This doesn't fix the root cause but raises the
bar for cascade triggering. Combined with H3 (rate limiter), might
be sufficient.

### H6: Directional lock

After a non-user-initiated target change (from re-snap), only allow
detent transitions in the direction the user was last pushing. If
motor is returning from above, only allow upward transitions (which
won't fire during downward ring-down). Requires tracking "user's
intended direction" which may be tricky.

### H7: PID tuning for less overshoot

The root cause is PID overshoot during ring-down. If PID could return
from 1000° with <5° overshoot, the cascade wouldn't trigger. This
likely requires:
- Much lower velocity limit (currently 4.0 rad/s)
- Higher damping (D term)
- Velocity feedforward
But would make normal operation sluggish.

## 6. Key Observations from Telemetry

From the endstop observer captured during the original bug:

```
Motor pushed to ~1375° (4 revolutions past 180° endstop)
Guard held target at 180° correctly
Motor returned: 1375→1052→785→537→308→192°
Once below 210° (guard boundary), recovery fired
Target cascaded: 180→170→160→150→…→10→0
Motor overshot each new target by 10-20°
Each overshoot triggered next transition (positive feedback)
Settled at detent 0, motor at −8°, trapped by constrain()
```

## 7. Code State

### Working baseline (committed)
- **50fd433**: Stateless position+hysteresis, no guard/settling/velocity
- Normal operation works fine; overshoot cascade is the only failure mode

### Current working tree (uncommitted)
- `src/haptic_layer.cpp`: Velocity gate + cooldown (BROKEN for test 1)
- `src/motor_control.cpp`: Added `get_motor_velocity()` (useful, keep)
- `src/motor_control.h`: Added `get_motor_velocity()` declaration
- `test/tools/endstop_observer.py`: Updated diagnostic output
- `.pio/approach_builds/`: Three UF2 files (A/B/C) — can delete

### Recommendation for next session
1. Revert haptic_layer.cpp to 50fd433 baseline (normal use works)
2. Keep `get_motor_velocity()` API addition
3. Try H3 (rate limiter) as simplest next attempt
4. Consider H5 (coarser detents) as pragmatic fix
