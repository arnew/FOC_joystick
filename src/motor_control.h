/**
 * motor_control.h — SimpleFOC Motor Control (single motor)
 *
 * One BLDC motor (7pp) + AS5600 I2C sensor, angle mode.
 * Motor angle is unbounded (-∞ to +∞).
 *
 * All motor state is private to motor_control.cpp.
 * Access only through the functions below.
 */

#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include <Arduino.h>
#include <SimpleFOC.h>

// ============================================================================
// API
// ============================================================================

void  init_motor();
void  update_motor();
void  set_motor_target(float angle);
float get_motor_angle();
float get_motor_target();
float get_motor_velocity();
void  reset_motor_pid_integral();  // zero I-term accumulators
void  center_motor_to(float desired_rad);  // offset sensor so current pos = desired

/** Direct access to BLDCMotor for Commander PID tuning passthrough. */
BLDCMotor* get_motor_object();

#endif // MOTOR_CONTROL_H
