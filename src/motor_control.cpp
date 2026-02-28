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

static void setup_motor_driver(uint8_t motor_id, BLDCDriver3PWM* driver) {
  Serial.print("[MOTOR "); Serial.print(motor_id); Serial.println("] Initializing driver...");
  driver->voltage_power_supply = 12.0f;
  driver->pwm_frequency = 30000;
  driver->init();
  Serial.println("[MOTOR] Driver OK");
}

static void setup_motor_sensor(MagneticSensorI2C* sensor) {
  Serial.println("[MOTOR] Initializing sensor...");
  sensor->init();
  Serial.println("[MOTOR] Sensor init complete");
}

static void configure_motor_pid(uint8_t motor_id, BLDCMotor* motor) {
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
}

void init_motor(uint8_t motor_id) {
  if (motor_id >= 2 || !motors[motor_id]) {
    Serial.print("[MOTOR] Invalid motor_id: ");
    Serial.println(motor_id);
    return;
  }
  
  BLDCMotor* motor = motors[motor_id];
  BLDCDriver3PWM* driver = drivers[motor_id];
  MagneticSensorI2C* sensor = sensors[motor_id];
  
  setup_motor_driver(motor_id, driver);
  motor->linkDriver(driver);
  
  setup_motor_sensor(sensor);
  motor->linkSensor(sensor);
  
  motor->controller = MotionControlType::angle;
  motor->voltage_limit = MOTOR0_VOLTAGE_LIMIT;
  Serial.print("[MOTOR] Angle voltage limit: ");
  Serial.println(motor->voltage_limit);
  
  configure_motor_pid(motor_id, motor);
  
  Serial.println("[MOTOR] Running motor->init()...");
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
  
  // Sync target: SimpleFOC Commander updates motor.target directly,
  // MIDI/USB updates target_angle[]. Bi-directional sync needed.
  if (motor->target != target_angle[motor_id]) {
    // Commander changed it -> update our state
    target_angle[motor_id] = motor->target;
  } else {
    // We changed it (MIDI/USB) -> update motor
    motor->target = target_angle[motor_id];
  }
  
  // Command motor to reach target angle (uses motor.target internally)
  motor->move();
  
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

float get_motor_target(uint8_t motor_id) {
  if (motor_id >= 2) return 0.0f;
  return target_angle[motor_id];
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