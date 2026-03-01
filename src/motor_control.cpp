/**
 * motor_control.cpp — SimpleFOC Motor Control (single motor)
 */

#include "motor_control.h"
#include "pid_config.h"

// ============================================================================
// MOTOR HARDWARE
// ============================================================================

MagneticSensorI2C sensor0 = MagneticSensorI2C(AS5600_I2C);
BLDCMotor motor0(7);  // 7 pole pairs
BLDCDriver3PWM driver0(13, 12, 11, 10);

// ============================================================================
// MOTOR STATE
// ============================================================================

float target_angle  = 0.0f;
float current_angle = 0.0f;

// ============================================================================
// INITIALIZATION
// ============================================================================

void init_motor() {
  Serial.println("[MOTOR] Initializing driver...");
  driver0.voltage_power_supply = 12.0f;
  driver0.pwm_frequency = 30000;
  driver0.init();
  Serial.println("[MOTOR] Driver OK");

  Serial.println("[MOTOR] Initializing sensor...");
  sensor0.init();
  Serial.println("[MOTOR] Sensor OK");

  motor0.linkDriver(&driver0);
  motor0.linkSensor(&sensor0);

  motor0.controller = MotionControlType::angle;
  motor0.voltage_limit = MOTOR0_VOLTAGE_LIMIT;
  Serial.print("[MOTOR] Voltage limit: ");
  Serial.println(motor0.voltage_limit);

  Serial.println("[MOTOR] motor0.init()...");
  motor0.init();
  Serial.println("[MOTOR] init complete");

  // PID config AFTER init() — init() resets PID limits to defaults
  motor0.P_angle.P = MOTOR0_PID_P;
  motor0.P_angle.I = MOTOR0_PID_I;
  motor0.P_angle.D = MOTOR0_PID_D;
  motor0.PID_velocity.P = MOTOR0_VELOCITY_P;
  motor0.PID_velocity.I = MOTOR0_VELOCITY_I;
  motor0.PID_velocity.D = MOTOR0_VELOCITY_D;
  motor0.LPF_angle.Tf   = MOTOR0_LPF_ANGLE_TF;
  motor0.P_angle.limit   = MOTOR0_VELOCITY_LIMIT;
  motor0.PID_velocity.limit = MOTOR0_VOLTAGE_LIMIT;

  Serial.print("[MOTOR] PID P="); Serial.print(MOTOR0_PID_P);
  Serial.print(" I="); Serial.print(MOTOR0_PID_I);
  Serial.print(" D="); Serial.println(MOTOR0_PID_D);

  Serial.println("[MOTOR] initFOC() — sensor calibration...");
  motor0.initFOC();
  Serial.print("[MOTOR] shaft_angle after initFOC: ");
  Serial.println(motor0.shaft_angle);
  Serial.println("[MOTOR] Ready");
}

// ============================================================================
// FOC LOOP
// ============================================================================

void update_motor() {
  motor0.loopFOC();
  current_angle = motor0.shaft_angle;
  motor0.move(target_angle);
}

// ============================================================================
// ACCESSORS
// ============================================================================

void set_motor_target(float angle) {
  target_angle = angle;
}

float get_motor_angle() {
  return current_angle;
}

float get_motor_target() {
  return target_angle;
}

float get_motor_velocity() {
  return motor0.shaft_velocity;
}
