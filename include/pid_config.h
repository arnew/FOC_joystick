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
// Initial values tuned for RP2040 mini + AS5600 + 7-pole motor
#define MOTOR0_PID_P  2.5f   // Proportional gain (was unlabeled, ~default SimpleFOC)
#define MOTOR0_PID_I  0.0f   // Integral gain (angular position, usually minimal)
#define MOTOR0_PID_D  0.5f   // Derivative gain (damping, reduces oscillation)

// Motor 0 Velocity Controller PID (for smooth transitions)
#define MOTOR0_VELOCITY_P  0.02f  // Lower P for velocity loop
#define MOTOR0_VELOCITY_I  0.0f
#define MOTOR0_VELOCITY_D  0.0f

// Motor 0 Voltage & Current Limits
#define MOTOR0_VOLTAGE_LIMIT  2.0f     // Maximum voltage applied (0-12V)
#define MOTOR0_CURRENT_LIMIT  2.0f     // Maximum current from sensor (optional)
#define MOTOR0_ACCELERATION   10.0f    // Max rad/s² (optional soft-start)

// Low-Pass Filter for angle measurement
// Tf = time constant (larger = smoother but slower response)
#define MOTOR0_LPF_ANGLE_TF  0.01f    // 10ms filter

// Motor 1 PID Gains (if enabled)
#if NUM_MOTORS > 1
  #define MOTOR1_PID_P  2.5f
  #define MOTOR1_PID_I  0.0f
  #define MOTOR1_PID_D  0.5f
  
  #define MOTOR1_VOLTAGE_LIMIT  2.0f
  #define MOTOR1_LPF_ANGLE_TF  0.01f
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
