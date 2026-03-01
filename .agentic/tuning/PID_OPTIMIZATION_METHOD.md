# PID Optimization Method

Automated coordinate-descent PID tuning for SimpleFOC angle-mode motor control.

## Problem

A 7-pole-pair BLDC motor with AS5600 I2C magnetic encoder, running SimpleFOC in
angle mode under a 2V thermal budget.  Seven interdependent parameters control
behaviour: angle P/I/D, velocity P/I, angle PID output limit (velocity cap),
and angle LPF time constant.  Manual iteration through 16 rounds had stalled
around "mostly works" — 225° never settled, D was zeroed out defensively.

## Method: Coordinate Descent with Adaptive Steps

### Why coordinate descent over alternatives

| Approach | Pros | Cons for this system |
|----------|------|---------------------|
| Grid search | Exhaustive | 7 params × even 5 levels = 78125 evals × ~10s = 9 days |
| Bayesian (GP) | Sample-efficient | Complex to implement; surrogate model overhead; overkill for 7 params |
| Genetic/evolutionary | Avoids local minima | Needs population (50+), too many evals |
| Nelder-Mead | No gradients needed | Simplex in 7D is fragile with noisy cost |
| **Coordinate descent** | **Simple, 2 evals/param/round** | May miss interactions — good enough here |

Coordinate descent: sweep one parameter at a time, try ±step, keep the better.
~14 evaluations per round (7 params × 2 directions), each ~10s.  One round ≈ 2.5 min.
Converges in 5–8 rounds ≈ 15–20 min.

### Algorithm

```
params = best_known_starting_point
best_cost = evaluate(params)

for round in 1..max_rounds:
    improved = False
    for each param p in params:
        if p.step < p.min_step: skip  # converged
        
        # Try +step
        up = clamp(p.value + p.step, p.lo, p.hi)
        cost_up = evaluate(params with p=up)
        
        # Try -step
        dn = clamp(p.value - p.step, p.lo, p.hi)
        cost_dn = evaluate(params with p=dn)
        
        # Pick best of {current, +step, -step}
        winner = argmin(best_cost, cost_up, cost_dn)
        if winner < best_cost:
            p.value = winner_value
            best_cost = winner
            improved = True
        else:
            revert p to original
    
    if not improved:
        halve all step sizes
        no_improve_count++
        if no_improve_count >= patience: STOP
    else:
        no_improve_count = 0
```

### Evaluation Protocol

Each evaluation runs 4 cardinal positions (0°, 90°, 180°, 270°):

1. **Home to 0°** and wait for settle (max 3s) — prevents transient contamination
   from parameter changes bleeding into the first measured position.
2. For each target position:
   - Send `T<deg>` command via serial
   - Observe @T telemetry at 10 Hz (device-side: 500-sample ring buffer, rolling
     variance, settled flag = |error|<5° AND variance<(3°)² for 0.2s)
   - Early exit after 5 consecutive settled readings AND ≥0.3s elapsed
   - Hard timeout at 5s
3. Collect metrics from last 10 observations per position (continuous gradient signal
   whether settled or not).

### Cost Function

Weighted sum, tuned to prioritise "actually settles" over small numerical improvements:

```
cost = 50 × unsettled_fraction      # 0/4 settled = +50, 4/4 = +0
     + 15 × mean_error_deg          # steady-state accuracy
     +  3 × settle_time_s           # response speed
     + 30 × variance_deg²           # stability (converted from rad²)
     +  2 × overshoot_deg           # peak error after first approach
```

The `unsettled_fraction` dominates: a config where 3/4 positions settle always beats
one where 2/4 settle, regardless of other metrics.  This prevents the optimiser from
chasing low-error configs that oscillate.

### Parameter Bounds and Steps

| Parameter | Commander | Start | Step | Min Step | Bounds | Rationale |
|-----------|-----------|-------|------|----------|--------|-----------|
| angle_P | MAP | 10.0 | 2.0 | 0.3 | [2, 25] | Authority vs. oscillation |
| angle_I | MAI | 0.2 | 0.05 | 0.01 | [0, 1] | Steady-state pull |
| angle_D | MAD | 2.0 | 0.5 | 0.1 | [0, 5] | Damping vs. D-kick |
| vel_P | MVP | 0.2 | 0.05 | 0.01 | [0.02, 1] | Velocity loop gain |
| vel_I | MVI | 0.5 | 0.1 | 0.02 | [0, 2] | Velocity integral |
| angle_lim | MAL | 4.0 | 1.0 | 0.3 | [1, 15] | Max velocity setpoint |
| lpf_Tf | MAF | 0.01 | 0.005 | 0.001 | [0.001, 0.05] | Angle filter time const |

Voltage limit (2.0V) is **never touched** — thermal hard-cap.

### Convergence

- Steps halve when a full round produces no improvement.
- Patience = 3 rounds without improvement → stop.
- Typical: converges in 5–8 rounds (best round 5, no further improvement rounds 6–8).

## Key Findings

### LPF was the bottleneck

The angle low-pass filter time constant (`LPF_Tf`) dropped from 0.01 (10ms) to 0.001
(1ms) — the **single biggest cost reduction** (round 2: cost 502 → 197).  At 0.01, the
filter introduced enough phase lag that the PID loop couldn't close fast enough to
settle.  The AS5600 at I2C 400kHz provides clean enough angle data that heavy filtering
is counterproductive.

### D term needs to exist but be moderate

Manual iteration had zeroed D (2.0×0) to avoid "D-kick" at 2V.  The optimizer found
D=1.0 works — enough damping to prevent overshoot without the voltage-saturating kicks
that D=2.0+ caused.

### Lower velocity P helps

vel_P dropped from 0.2 to 0.1.  The velocity loop was over-reacting to the angle
loop's velocity setpoint, causing the cascade to fight itself.

### Cost trajectory

```
Round 0 (baseline):  689  — 0/4 settled, 9.7° error
Round 1:             502  — 0/4 settled (P=8, vel_I=0.4, lpf=0.005)
Round 2:             197  — 1/4 settled (lpf=0.001 was the breakthrough)
Round 3:             171  — 2/4 settled (P=10)
Round 4:             147  — 2/4 settled (D=1.0)
Round 5:             115  — 3/4 settled (vel_P=0.1, lim=4.0)
Rounds 6–8:          115  — converged (patience exhausted)
```

### Final parameters (iteration 17)

```
angle_P  = 12.0    (was 10.0)
angle_I  = 0.2     (was 0.09 = 0.3×0.3)
angle_D  = 1.0     (was 0.0 = 2.0×0)
vel_P    = 0.1     (was 0.2)
vel_I    = 0.5     (was 0.15 = 0.5×0.3)
vel_lim  = 4.0     (unchanged)
lpf_Tf   = 0.001   (was 0.01)
```

## Bugs Found During Optimization

1. **Commander motor not registered**: `commander.motor(&motor0, "M0")` is a one-shot
   handler call, not a registration.  Fixed with `commander.add('M', cmd_motor, ...)`.
2. **PID init order**: `configure_motor_pid()` was called before `motor->init()`, which
   resets `P_angle.limit` to the default 20.0.  Moved PID config after init.
3. **Degraded starting values**: Manual tuning used multiplier hacks (`0.3*0.3`,
   `2.0*0`) that compiled to near-zero values.  Cleaned up to explicit constants.

## Files

- `test/tools/pid_optimizer.py` — The optimizer script
- `pid_optimization_result.json` — Full run results with cost history
- `include/pid_config.h` — Baked-in values (iteration 17)
