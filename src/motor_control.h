/**
 * motor_control.h - SimpleFOC Motor Control Module
 * 
 * Handles single BLDC motor control with SimpleFOC:
 * - Motor initialization
 * - FOC loop execution
 * - Angle control and limits
 * - Motor state management
 */

#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include <Arduino.h>
#include <SimpleFOC.h>
#include "config.h"

// ============================================================================
// MOTOR DEFINITIONS
// ============================================================================

extern MagneticSensorI2C sensor0;
extern BLDCMotor motor0;
extern BLDCDriver3PWM driver0;

extern BLDCMotor* motors[1];
extern BLDCDriver3PWM* drivers[1];
extern MagneticSensorI2C* sensors[1];

// ============================================================================
// MOTOR STATE
// ============================================================================

extern float target_angle[1];
extern float current_angle[1];
extern uint8_t active_motor;

// ============================================================================
// MOTOR CONTROL FUNCTIONS
// ============================================================================

/**
 * Initialize motor hardware and FOC
 * @param motor_id Motor index (0 or 1)
 */
void init_motor(uint8_t motor_id);

/**
 * Execute FOC control loop for motor
 * Must be called frequently (~1kHz)
 * @param motor_id Motor index (0 or 1)
 */
void update_motor(uint8_t motor_id);

/**
 * Set target angle for motor
 * @param motor_id Motor index (0 or 1)
 * @param angle Target angle in radians
 */
void set_motor_target(uint8_t motor_id, 
                      float angle);

/**
 * Get current motor angle
 * @param motor_id Motor index (0 or 1)
 * @return Current angle in radians
 */
float get_motor_angle(uint8_t motor_id);

/**
 * Apply motor limits (clamp or wrap)
 * @param motor_id Motor index (0 or 1)
 * @param angle Angle to limit (modified in place)
 */
void handle_motor_limits(uint8_t motor_id, 
                         float& angle);

#endif // MOTOR_CONTROL_H
