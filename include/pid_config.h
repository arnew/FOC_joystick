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
#define MOTOR0_PID_P  12.0f   // Maintains control authority
#define MOTOR0_PID_I  0.4f    // Moderate integral - eliminates drift without instability
#define MOTOR0_PID_D  0.8f    // Good damping

// Motor 0 Velocity Controller PID (for smooth transitions)
// Tuned 2026-02-28: Re-enable velocity I term for smoother movement
#define MOTOR0_VELOCITY_P  0.25f   // P for velocity loop
#define MOTOR0_VELOCITY_I  5.0f    // Re-enabled from 0.0 for smooth transitions
#define MOTOR0_VELOCITY_D  0.0f    // D for velocity loop

// Motor 0 Voltage & Current Limits
// Tuned 2026-02-28: Increased voltage for more control authority
#define MOTOR0_VOLTAGE_LIMIT  3.0f     // Increased from 2.0V for better response (0-12V)
#define MOTOR0_CURRENT_LIMIT  2.0f     // Maximum current from sensor (optional, SimpleFOC DEF_CURRENT_LIM=2.0f)
#define MOTOR0_ACCELERATION   10.0f    // Max rad/s² (optional soft-start)

// Low-Pass Filter for angle measurement
// SimpleFOC DEF_VEL_FILTER_Tf = 0.005f (5ms velocity filter)
// Tf = time constant (larger = smoother but slower response)
#define MOTOR0_LPF_ANGLE_TF  0.005f    // 5ms filter (SimpleFOC default velocity filter)

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
