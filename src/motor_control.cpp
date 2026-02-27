/**
 * motor_control.cpp - SimpleFOC Motor Control Implementation
 */

#include "motor_control.h"
#include "pid_config.h"

// ============================================================================
// MOTOR HARDWARE DEFINITIONS
// ============================================================================

MagneticSensorI2C sensor0 = MagneticSensorI2C(AS5600_I2C);
BLDCMotor motor0(7);  // 7 pole pairs
BLDCDriver3PWM driver0(13, 12, 11, 10);

BLDCMotor* motors[1] = {
  &motor0
};

BLDCDriver3PWM* drivers[1] = {
  &driver0
};

MagneticSensorI2C* sensors[1] = {
  &sensor0
};

// ============================================================================
// MOTOR STATE VARIABLES
// ============================================================================

float target_angle[1] = {0.0f};
float current_angle[1] = {0.0f};
uint8_t active_motor = 0;

// ============================================================================
// MOTOR INITIALIZATION
// ============================================================================

void init_motor(uint8_t motor_id) {
  if (motor_id >= 2 || !motors[motor_id]) {
    return;
  }
  
  BLDCMotor* motor = motors[motor_id];
  BLDCDriver3PWM* driver = drivers[motor_id];
  MagneticSensorI2C* sensor = sensors[motor_id];
  
  // Driver setup
  driver->voltage_power_supply = 12.0f;
  driver->pwm_frequency = 30000;
  driver->init();
  motor->linkDriver(driver);
  
  // Sensor setup
  sensor->init();
  motor->linkSensor(sensor);
  
  // Angle control mode
  motor->controller = MotionControlType::angle;
  motor->voltage_limit = (motor_id == 0) ? 
    MOTOR0_VOLTAGE_LIMIT : MOTOR0_VOLTAGE_LIMIT;
  
  // PID gains
  if (motor_id == 0) {
    motor->P_angle.P = MOTOR0_PID_P;
    motor->P_angle.I = MOTOR0_PID_I;
    motor->P_angle.D = MOTOR0_PID_D;
    
    motor->PID_velocity.P = MOTOR0_VELOCITY_P;
    motor->PID_velocity.I = MOTOR0_VELOCITY_I;
    motor->PID_velocity.D = MOTOR0_VELOCITY_D;
    
    motor->LPF_angle.Tf = MOTOR0_LPF_ANGLE_TF;
  }
  
  // Initialize FOC
  motor->init();
  motor->initFOC();
}

// ============================================================================
// MOTOR CONTROL LOOP
// ============================================================================

void update_motor(uint8_t motor_id) {
  if (motor_id >= 2 || !motors[motor_id]) {
    return;
  }
  
  BLDCMotor* motor = motors[motor_id];
  
  motor->loopFOC();
  current_angle[motor_id] = motor->shaft_angle;
  motor->move(target_angle[motor_id]);
}

// ============================================================================
// MOTOR CONTROL FUNCTIONS
// ============================================================================

void set_motor_target(uint8_t motor_id, 
                      float angle) {
  if (motor_id >= 2) return;
  
  const MotorProfile* profile = 
    get_motor_profile(motor_id);
  if (!profile) return;
  
  handle_motor_limits(motor_id, angle);
  
  target_angle[motor_id] = angle;
  active_motor = motor_id;
}

float get_motor_angle(uint8_t motor_id) {
  if (motor_id >= 2) return 0.0f;
  return current_angle[motor_id];
}

void handle_motor_limits(uint8_t motor_id, 
                         float& angle) {
  if (motor_id >= 2) return;
  
  const MotorProfile* profile = 
    get_motor_profile(motor_id);
  if (!profile) return;
  
  if (profile->is_endless) {
    // Endless: wrap 0-2π
    while (angle < 0.0f) {
      angle += 6.28318f;
    }
    while (angle > 6.28318f) {
      angle -= 6.28318f;
    }
  } else {
    // Limited: clamp to range
    angle = constrain(angle, 
                      profile->min_angle, 
                      profile->max_angle);
  }
}
