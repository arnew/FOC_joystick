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
// DUMMY MODE: Passthrough MIDI → HID (no motor control)
// ============================================================================
// When DUMMY_MODE is enabled:
// - MIDI CC values directly map to joystick position
// - No SimpleFOC motor control
// - Useful for testing HID integration without hardware

#ifdef DUMMY_MODE
void init_motor(uint8_t motor_id) {
  // No-op in dummy mode
  (void)motor_id;
  Serial.println("[DUMMY MODE] Motor init skipped");
}

void update_motor(uint8_t motor_id) {
  // No-op in dummy mode
  (void)motor_id;
}

void set_motor_target(uint8_t motor_id, float angle) {
  if (motor_id >= 1) return;
  target_angle[motor_id] = angle;
  current_angle[motor_id] = angle;  // Echo directly (no FOC)
}

float get_motor_angle(uint8_t motor_id) {
  if (motor_id >= 1) return 0.0f;
  return current_angle[motor_id];
}

void handle_motor_limits(uint8_t motor_id, float& angle) {
  if (motor_id >= 1) return;
  const MotorProfile* profile = get_motor_profile(motor_id);
  if (!profile) return;
  
  if (profile->is_endless) {
    while (angle < 0.0f) angle += 6.28318f;
    while (angle > 6.28318f) angle -= 6.28318f;
  } else {
    angle = constrain(angle, profile->min_angle, profile->max_angle);
  }
}

#else
// ============================================================================
// MOTOR INITIALIZATION (FOC MODE)
// ============================================================================

void init_motor(uint8_t motor_id) {
  if (motor_id >= 2 || !motors[motor_id]) {
    Serial.print("[MOTOR] Invalid motor_id: ");
    Serial.println(motor_id);
    return;
  }
  
  BLDCMotor* motor = motors[motor_id];
  BLDCDriver3PWM* driver = drivers[motor_id];
  MagneticSensorI2C* sensor = sensors[motor_id];
  
  Serial.print("[MOTOR "); Serial.print(motor_id); Serial.println("] Initializing driver...");
  // Driver setup
  driver->voltage_power_supply = 12.0f;
  driver->pwm_frequency = 30000;
  driver->init();
  motor->linkDriver(driver);
  Serial.println("[MOTOR] Driver OK");
  
  Serial.println("[MOTOR] Initializing sensor...");
  // Sensor setup - this may fail if I2C bus is broken or device not connected
  sensor->init();
  Serial.println("[MOTOR] Sensor init complete");
  motor->linkSensor(sensor);
  
  // Angle control mode
  motor->controller = MotionControlType::angle;
  motor->voltage_limit = (motor_id == 0) ? 
    MOTOR0_VOLTAGE_LIMIT : MOTOR0_VOLTAGE_LIMIT;
  
  Serial.print("[MOTOR] Angle voltage limit: ");
  Serial.println(motor->voltage_limit);
  
  // PID gains
  if (motor_id == 0) {
    motor->P_angle.P = MOTOR0_PID_P;
    motor->P_angle.I = MOTOR0_PID_I;
    motor->P_angle.D = MOTOR0_PID_D;
    
    motor->PID_velocity.P = MOTOR0_VELOCITY_P;
    motor->PID_velocity.I = MOTOR0_VELOCITY_I;
    motor->PID_velocity.D = MOTOR0_VELOCITY_D;
    
    motor->LPF_angle.Tf = MOTOR0_LPF_ANGLE_TF;
    
    Serial.print("[MOTOR] PID P=");
    Serial.print(MOTOR0_PID_P);
    Serial.print(" I=");
    Serial.print(MOTOR0_PID_I);
    Serial.print(" D=");
    Serial.println(MOTOR0_PID_D);
  }
  
  Serial.println("[MOTOR] Running motor->init()...");
  // Initialize FOC
  motor->init();
  Serial.println("[MOTOR] Motor init complete");
  
  Serial.println("[MOTOR] Running motor->initFOC() - sensor calibration...");
  motor->initFOC();
  Serial.print("[MOTOR] Motor shaft_angle after initFOC: ");
  Serial.println(motor->shaft_angle);
  Serial.println("[MOTOR] Initialization complete");
}

// ============================================================================
// MOTOR CONTROL LOOP
// ============================================================================

void update_motor(uint8_t motor_id) {
  if (motor_id >= 2 || !motors[motor_id]) {
    return;
  }
  
  BLDCMotor* motor = motors[motor_id];
  
  // Execute FOC control loop
  motor->loopFOC();
  
  // Read actual motor position from sensor
  float prev_angle = current_angle[motor_id];
  current_angle[motor_id] = motor->shaft_angle;
  
  // Command motor to reach target angle
  motor->move(target_angle[motor_id]);
  
  // Diagnostic: detect if motor is stuck
  static unsigned long last_stuck_check = 0;
  static uint16_t stuck_count = 0;
  unsigned long now = millis();
  
  // Every 5 seconds, check if motor has ever moved from 0.0
  if (now - last_stuck_check >= 5000) {
    last_stuck_check = now;
    if (abs(current_angle[motor_id] - 0.0f) < 0.01f && target_angle[motor_id] != 0.0f) {
      stuck_count++;
      if (stuck_count <= 3) {  // Warn max 3 times to avoid spam
        Serial.print("[MOTOR] WARNING: Motor angle stuck at 0.0 with target T=");
        Serial.println(target_angle[motor_id]);
      }
    } else {
      stuck_count = 0;  // Reset if motor starts responding
    }
  }
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
#endif  // DUMMY_MODE