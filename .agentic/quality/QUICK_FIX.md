# Quick Tuning Fix Guide

## Your Motor Problem

**Reported Issue:** "Motor is quite noisy and won't hold position if disturbed"

**Confirmed by Quality Evaluation:**
- Quality Score: **28.4/100 (POOR)** ❌
- Position Noise: **13.53°** (target <0.5°) 
- Position Drift: **24.64°** (target <0.2°)
- Stability: **52.1%** (target >90%)

---

## Why It's Happening

The PID gains are **over-aggressive**:

```
Current Gains (POOR tuning):
├─ Velocity Loop:  Kp=5.440,  Ki=31.561, Kd=0.234  ← Ki too high, Kd too low
└─ Angle Loop:     Kp=8.257,  Ki=31.197, Kd=0.546  ← Kp too high, Kd too low

Effect:
├─ High Ki amplifies power to hold position
│  └─ But causes oscillation → NOISE
├─ Low Kd can't damp the oscillations
│  └─ Motor keeps overshooting → MORE NOISE
└─ Result: Jittery, unstable position
```

---

## Quick Fix (5 minutes)

### Step 1: Edit `include/pid_config.h`

Replace the MOTOR0 gains with conservative values:

```cpp
// FILE: include/pid_config.h

// Velocity Controller (Inner Loop - Force generation)
#define MOTOR0_VELOCITY_KP 3.0      // Was 5.440  ← Reduce proportional
#define MOTOR0_VELOCITY_KI 10.0     // Was 31.561 ← Reduce integral
#define MOTOR0_VELOCITY_KD 1.5      // Was 0.234  ← Increase damping

// Angle Controller (Outer Loop - Position control)
#define MOTOR0_PID_KP 4.0           // Was 8.257  ← Reduce proportional
#define MOTOR0_PID_KI 15.0          // Was 31.197 ← Reduce integral
#define MOTOR0_PID_KD 2.5           // Was 0.546  ← Increase damping
```

### Step 2: Rebuild & Upload

```bash
cd /home/arnew/Notebooks.st.rasentrimmer.org/FOC/rp2040_mini_as5600

# Build for your motor configuration
platformio run -e pico_1motor_limited

# Upload to RP2040
platformio run -e pico_1motor_limited --target upload

# Wait 5 seconds for motor to settle
sleep 5
```

### Step 3: Test Quality

```bash
python3 test/calibrate_pid.py --motor 0 --step-only
```

Expected improvement:
- Quality Score: 28 → **~50+** ✅
- Noise: 13.53° → **<2°** ✅
- Drift: 24.64° → **<1°** ✅

### Step 4: Manual Verification

Physically test the motor:
1. **Will it hold position?** (no drift when released)
2. **Is it quiet?** (minimal buzzing/oscillation)
3. **Does it resist push?** (hand pressure doesn't immediately budge it)

---

## If Still Noisy After Step 1

Try **increasing Kd further** (more damping):

```cpp
#define MOTOR0_VELOCITY_KD 2.5      // Increase from 1.5
#define MOTOR0_PID_KD 3.5           // Increase from 2.5
```

Then rebuild, upload, and re-test.

**Pattern:** Increase Kd until noise goes away, then adjust Kp/Ki if needed.

---

## If Settling is Too Slow

If Quality Score improves but Settling Time is still >3s:

```cpp
#define MOTOR0_PID_KP 5.0           // Increase from 4.0 (slightly faster response)
```

Only increase this **after** noise is under control!

---

## If Position Drift Returns

If motor starts drifting away from setpoint:

```cpp
#define MOTOR0_PID_KI 20.0          // Increase from 15.0 (more position holding force)
```

---

## Full Auto-Tuning (More Complete)

If manual tuning doesn't reach Quality >60, re-run full calibration:

```bash
# Full calibration with conservative safety margin
python3 test/calibrate_pid.py --motor 0 --safety-factor 0.4

# This tests both loops and auto-tunes for stability
```

---

## Tuning Trade-offs Cheat Sheet

```
Action                      Effect on Quality
─────────────────────────────────────────────────
Increase Kp                 Response faster, but more noise ↔
Decrease Kp                 Response slower, less noise ↔
Increase Kd                 Damping improves, noise ↓
Decrease Kd                 Cost: Slower response, overshoot ↑
Increase Ki                 Better position holding, but oscillation ↔
Decrease Ki                 Less oscillation, but position drifts ↔
```

**Key Insight:** You need **balance**. Don't just increase/decrease one value; tune the ratio.

---

## Monitoring Progress

Each time you change gains:

```bash
# Rebuild and upload
platformio run -e pico_1motor_limited --target upload && sleep 5

# Test and record score
python3 test/calibrate_pid.py --motor 0 --step-only
```

Track the Quality Score trend:
```
Iteration 1: Score 28.4 (POOR) ← Starting point
Iteration 2: Score 52.1 (FAIR)  ← After first conservative fix
Iteration 3: Score 68.5 (GOOD)  ← After Kd tune
Iteration 4: Score 75.8 (GOOD)  ← After Kp fine-tune
Target:      Score >80 (EXCELLENT)
```

---

## Success Criteria

Your motor is properly tuned when:

✅ **Quality Score >70**  
✅ **Position Noise <1°** (practically silent)  
✅ **Position Drift <0.1°** (stays where you put it)  
✅ **Stability >85%** (holds during hand disturbance)  
✅ **Settling Time <2.5s** (responds quickly)  

---

## Hardware Checks (If Tuning Doesn't Help)

If Quality Score won't improve past 50 despite tuning adjustments:

### 1. **Encoder Problem?**
```bash
python3 test/debug_joystick.py --monitor
# Manually rotate motor by hand
# Position should change smoothly without jumps >0.1°
```

Look for:
- ❌ Position jumps at certain angles (bad encoder calibration)
- ❌ I2C timeout errors in output (loose connection)
- ❌ Periodic noise at specific speeds (encoder noise)

### 2. **Power Supply Problem?**
- Check PSU voltage: Should be stable 12V ± 0.5V under load
- Motor needs ~2-3A at full torque
- **Noisy power = noisy motor!**

### 3. **Mechanical Problem?**
- Manually rotate motor shaft by hand
- Feel for discontinuities or play in gearbox/coupling
- Backlash or grinding = mechanical issue (not tuning)

---

## Reference: Current vs. Recommended

| Parameter | Current | Recommended | Fix |
|-----------|---------|-------------|-----|
| Velocity Kp | 5.440 | 3.0 | -45% ↓ |
| Velocity Ki | 31.561 | 10.0 | -68% ↓ |
| Velocity Kd | 0.234 | 1.5 | +540% ↑ |
| Angle Kp | 8.257 | 4.0 | -52% ↓ |
| Angle Ki | 31.197 | 15.0 | -52% ↓ |
| Angle Kd | 0.546 | 2.5 | +358% ↑ |

**Summary:** Reduce aggressive integral action, increase damping responsiveness.

---

**Next Steps:**
1. Edit `include/pid_config.h` with recommended gains above
2. Run: `platformio run -e pico_1motor_limited --target upload`
3. Run: `python3 test/calibrate_pid.py --motor 0 --step-only`
4. Report new Quality Score and manual test results
5. Iterate if needed using the tuning trade-offs guide

**Questions?** Check [QUALITY_EVALUATION.md](QUALITY_EVALUATION.md) for detailed diagnostics.
