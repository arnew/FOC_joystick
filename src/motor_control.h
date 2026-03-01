/**
 * motor_control.h — SimpleFOC Motor Control (single motor)
 *
 * One BLDC motor (7pp) + AS5600 I2C sensor, angle mode.
 * Motor angle is unbounded (-∞ to +∞).
 */

#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include <Arduino.h>
#include <SimpleFOC.h>
#include "config.h"

// ============================================================================
// MOTOR HARDWARE
// ============================================================================

extern MagneticSensorI2C sensor0;
extern BLDCMotor motor0;
extern BLDCDriver3PWM driver0;

// ============================================================================
// MOTOR STATE
// ============================================================================

extern float target_angle;
extern float current_angle;

// ============================================================================
// API
// ============================================================================

void  init_motor();
void  update_motor();
void  set_motor_target(float angle);
float get_motor_angle();
float get_motor_target();
float get_motor_velocity();

#endif // MOTOR_CONTROL_H
