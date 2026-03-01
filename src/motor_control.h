/**
 * motor_control.h — SimpleFOC Motor Control
 *
 * Single BLDC motor (7pp) + AS5600 I2C sensor.
 * Provides: init, FOC loop, target/angle/velocity access.
 * Motor angle is unbounded (-∞ to +∞).
 */

#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include <Arduino.h>
#include <SimpleFOC.h>
#include "config.h"

// ============================================================================
// MOTOR HARDWARE (single motor)
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
// API
// ============================================================================

void init_motor(uint8_t motor_id);
void update_motor(uint8_t motor_id);
void set_motor_target(uint8_t motor_id, float angle);
float get_motor_angle(uint8_t motor_id);
float get_motor_target(uint8_t motor_id);
float get_motor_velocity(uint8_t motor_id);

#endif // MOTOR_CONTROL_H
