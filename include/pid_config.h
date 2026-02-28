#ifndef PID_CONFIG_H
#define PID_CONFIG_H

/**
 * SimpleFOC PID Tuning Configuration
 * 
 * Use calibrate_pid.py to auto-tune these values via Ziegler-Nichols method
 * Or manually adjust based on system behavior:
 * 
 * Symptoms & Fixes:
 * - Oscillating in idle: Reduce Kp, increase Kd
 * - No response: Increase Kp, check sensor connection
 * - Slow response: Increase Kp
 * - Overshoot: Reduce Kp, increase Kd
 * - Steady-state error: Increase Ki
 */

// Motor 0 PID Gains (Angle Controller)
// Tuned 2026-02-28: Conservative integral action to avoid overshoot & heat
// Iteration 1: P=12.0, I=0.2, D=0.8 (0% settled, 3.81° avg error, 6° overshoot, oscillating)
// Iteration 2: P=12.0, I=1.0, D=0.8 (UNSTABLE - motor overheating, timeouts)
// Iteration 3: P=12.0, I=0.4, D=0.8 (balanced: error elimination without instability)
// Iteration 4: P=12.0, I=0.4, D=0.8 — oscillating ±4° around target, never settles
// Iteration 5: P=6.0, I=0.4, D=1.5 — too weak, 10-15° steady-state error
// Iteration 6: P=10.0, I=0.3, D=1.2 — marginal: sometimes settles, sometimes not
// Iteration 7: P=12.0, I=0.2, D=1.5 — keep authority, more damping, less integral
// Iteration 8: fix velocity wind-up (vel I 2→0.5), more angle damping, faster LPF
// Iteration 9: reset vel integral on target change, add vel limit, angle P.limit
// Iteration 10: bump I 0.15→0.2 for steady-state pull (safe with integral reset)
// Iteration 11: D 2.0→3.0 — D-kick worse at 180° (9.49° vs 4.97°), revert
// Iteration 12: D=2.0 (sweet spot), settle tolerance 8° handles B
// Iteration 13: V=2.0 thermal cap → scale P 12→8, vel_limit 10→6, vel_I 1.0→0.5
//   Result: 180° still 8.44°, but D fixed (overshoot 0°). vel_limit=4 works.
// Iteration 15: D=2.5 + vel_limit=3 + LPF=0.02 → D-kick back (15.4°), revert
// Iteration 16: back to 14 PID, widen unloaded limits to match 2V physics
//   180° limit cycle is physical: 2V can't damp 7pp motor from 90° approach
#define MOTOR0_PID_P  10.0f   // Solid authority at 2V
#define MOTOR0_PID_I  0.3f    // Steady-state pull
#define MOTOR0_PID_D  2.0f    // Sweet spot (D=2.5 caused D-kick at 2V too)

// Motor 0 Velocity Controller PID (for smooth transitions)
#define MOTOR0_VELOCITY_P  0.2f    // Gentle velocity tracking (2V budget)
#define MOTOR0_VELOCITY_I  0.5f    // Moderate integral with reset
#define MOTOR0_VELOCITY_D  0.0f    // D for velocity loop

// Motor 0 Limits
#define MOTOR0_VOLTAGE_LIMIT  2.0f     // Thermal-safe limit
#define MOTOR0_VELOCITY_LIMIT 4.0f     // Caps approach speed → reduces overshoot
#define MOTOR0_CURRENT_LIMIT  2.0f     // Maximum current from sensor (optional, SimpleFOC DEF_CURRENT_LIM=2.0f)
#define MOTOR0_ACCELERATION   10.0f    // Max rad/s² (optional soft-start)

// Low-Pass Filter for angle measurement
// SimpleFOC DEF_VEL_FILTER_Tf = 0.005f (5ms velocity filter)
// Tf = time constant (larger = smoother but slower response)
#define MOTOR0_LPF_ANGLE_TF  0.01f     // 10ms filter (0.02 too slow for settle)

// Motor 1 PID Gains (if enabled)
#if NUM_MOTORS > 1
  #define MOTOR1_PID_P  20.0f   // SimpleFOC default
  #define MOTOR1_PID_I  0.0f
  #define MOTOR1_PID_D  0.5f
  
  #define MOTOR1_VELOCITY_P  0.5f
  #define MOTOR1_VELOCITY_I  10.0f
  #define MOTOR1_VELOCITY_D  0.0f
  
  #define MOTOR1_VOLTAGE_LIMIT  2.0f
  #define MOTOR1_CURRENT_LIMIT  2.0f
  #define MOTOR1_LPF_ANGLE_TF  0.005f
#endif

// ============================================================================
// TUNING REFERENCE: Ziegler-Nichols Method
// ============================================================================
// 
// 1. RELAY TEST (use calibrate_pid.py):
//    - Send 45° square wave @ 1-2 Hz
//    - Measure oscillation frequency (Pu = period)
//    - Estimate ultimate gain Ku from amplitude ratio
//
// 2. ZIEGLER-NICHOLS RULES (conservative, ~20-30% safety factor):
//    Kp = 0.6 * Ku * 0.65
//    Ki = 1.2 * Ku / Pu * 0.65
//    Kd = 3.0 * Ku * Pu / 40.0 * 0.65
//
// 3. MANUAL FINE-TUNING:
//    - If oscillating: increase Kd, decrease Kp
//    - If sluggish: increase Kp
//    - If overshoots: decrease Kp, increase Kd
//    - If unstable: use smaller gains overall

#endif // PID_CONFIG_H
