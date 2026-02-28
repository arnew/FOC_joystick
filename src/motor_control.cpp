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

#if NUM_MOTORS > 1
BLDCMotor motor1(7);
BLDCDriver3PWM driver1(13, 12, 11, 10);
#endif

BLDCMotor* motors[2] = {
  &motor0,
#if NUM_MOTORS > 1
  &motor1
#else
  nullptr
#endif
};

BLDCDriver3PWM* drivers[2] = {
  &driver0,
#if NUM_MOTORS > 1
  &driver1
#else
  nullptr
#endif
};

MagneticSensorI2C* sensors[2] = {
  &sensor0,
#if NUM_MOTORS > 1
  &sensor0  // TODO: Add sensor1
#else
  nullptr
#endif
};

// ============================================================================
// MOTOR STATE VARIABLES
// ============================================================================

float target_angle[2] = {0.0f, 0.0f};
float current_angle[2] = {0.0f, 0.0f};
uint8_t active_motor = 0;

// ============================================================================
// MOTOR INITIALIZATION
// ============================================================================

void init_motor(uint8_t motor_id) {
  if (motor_id >= 2 || !motors[motor_id]) {
    Serial.print("[MOTOR] ERROR: Invalid motor_id ");
    Serial.println(motor_id);
    return;
  }
  
  Serial.print("[MOTOR] Initializing motor ");
  Serial.println(motor_id);
  
  BLDCMotor* motor = motors[motor_id];
  BLDCDriver3PWM* driver = drivers[motor_id];
  MagneticSensorI2C* sensor = sensors[motor_id];
  
  // Driver setup
  Serial.println("[MOTOR] - Setting up driver...");
  driver->voltage_power_supply = 12.0f;
  driver->pwm_frequency = 30000;
  driver->init();
  motor->linkDriver(driver);
  Serial.println("[MOTOR] - Driver OK");
  
  // Sensor setup
  Serial.println("[MOTOR] - Setting up sensor...");
  sensor->init();
  motor->linkSensor(sensor);
  Serial.println("[MOTOR] - Sensor OK");
  
  // Angle control mode
  motor->controller = MotionControlType::angle;
  motor->voltage_limit = (motor_id == 0) ? 
    MOTOR0_VOLTAGE_LIMIT : MOTOR0_VOLTAGE_LIMIT;
  
  Serial.print("[MOTOR] - Voltage limit: ");
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
    
    Serial.print("[MOTOR] - PID: P=");
    Serial.print(MOTOR0_PID_P);
    Serial.print(" I=");
    Serial.print(MOTOR0_PID_I);
    Serial.print(" D=");
    Serial.println(MOTOR0_PID_D);
  }
  
  // Initialize FOC
  Serial.println("[MOTOR] - Running motor->init()...");
  motor->init();
  Serial.println("[MOTOR] - Running motor->initFOC() (calibration)...");
  motor->initFOC();
  Serial.print("[MOTOR] - Initial position: ");
  Serial.print(motor->shaft_angle, 4);
  Serial.println(" rad");
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
  
  motor->loopFOC();
  float prev_angle = current_angle[motor_id];
  current_angle[motor_id] = motor->shaft_angle;
  motor->move(target_angle[motor_id]);
  
  // Movement detection diagnostics (USB-safe 1 Hz logging)
  static unsigned long last_log = 0;
  static float last_logged_angle = 0.0f;
  static float last_logged_target = 0.0f;
  static bool movement_detected = false;
  unsigned long now = millis();
  
  // Detect significant movement (>0.05 rad change)
  float angle_delta = abs(current_angle[motor_id] - prev_angle);
  if (angle_delta > 0.05f) {
    movement_detected = true;
  }
  
  // Log once per second if target changed or movement detected
  if (now - last_log >= 1000) {
    bool target_changed = abs(target_angle[motor_id] - last_logged_target) > 0.01f;
    bool angle_changed = abs(current_angle[motor_id] - last_logged_angle) > 0.01f;
    
    if (target_changed || angle_changed || movement_detected) {
      Serial.print("[MOTOR] T=");
      Serial.print(target_angle[motor_id], 2);
      Serial.print(" A=");
      Serial.print(current_angle[motor_id], 2);
      if (movement_detected) {
        Serial.print(" MOVING");
      }
      if (target_changed && !angle_changed) {
        Serial.print(" STUCK?");
      }
      Serial.println();
      
      last_logged_angle = current_angle[motor_id];
      last_logged_target = target_angle[motor_id];
      movement_detected = false;
    }
    last_log = now;
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
