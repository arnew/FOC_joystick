/**
 * motor_control.cpp - SimpleFOC Motor Control Implementation
 */

#include "motor_control.h"
#include "pid_config.h"
#include "statistics.h"

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

    // Velocity setpoint limit from angle PID (caps approach speed)
    motor->P_angle.limit = MOTOR0_VELOCITY_LIMIT;
    // Velocity PID output limit (matches voltage limit)
    motor->PID_velocity.limit = MOTOR0_VOLTAGE_LIMIT;
    
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
  
  // Run homing sequence to establish known reference
  if (home_motor(motor_id)) {
    Serial.println("[MOTOR] Homing successful - motor ready");
  } else {
    Serial.println("[MOTOR] WARNING: Homing failed - proceeding anyway");
  }
}

// Motor idle/rest tracking - stop applying current when at rest
static unsigned long last_movement_time[1] = {0};
static const uint16_t MOTOR_IDLE_TIMEOUT_MS = 2000;  // Cut power after 2s truly at rest
static const float IDLE_ERROR_THRESHOLD = 0.017f;     // ~1° — only idle when PID has settled

bool home_motor(uint8_t motor_id) {
  if (motor_id >= 1 || !motors[motor_id]) return false;
  
  BLDCMotor* motor = motors[motor_id];
  Serial.println("[MOTOR] Starting homing sequence...");
  
  // Rotate slowly to find sensor reference (low voltage test move)
  motor->voltage_limit = 0.5f;  // Very low voltage for gentle rotation
  set_motor_target(motor_id, PI);  // Try rotating to opposite side
  
  // Wait for movement to stabilize
  for (int i = 0; i < 200; i++) {  // ~2 seconds at 100ms loop
    motor->loopFOC();
    motor->move(PI);
    delay(10);
  }
  
  // Return to 0°
  set_motor_target(motor_id, 0.0f);
  for (int i = 0; i < 100; i++) {  // ~1 second
    motor->loopFOC();
    motor->move(0.0f);
    delay(10);
  }
  
  // Restore full voltage limit
  motor->voltage_limit = MOTOR0_VOLTAGE_LIMIT;
  
  // Verify position is near 0
  if (abs(current_angle[motor_id]) < 0.2f) {
    Serial.println("[MOTOR] Homing complete - at 0° reference");
    return true;
  }
  
  Serial.print("[MOTOR] Homing result: ");
  Serial.println(current_angle[motor_id]);
  return true;  // Accept even if not exactly at 0
}

// ============================================================================
// MOTOR CONTROL LOOP
// ============================================================================

void update_motor(uint8_t motor_id) {
  if (motor_id >= 2 || !motors[motor_id]) {
    return;
  }
  
  BLDCMotor* motor = motors[motor_id];
  unsigned long now = millis();
  
  // Execute FOC control loop
  motor->loopFOC();
  
  // Read actual motor position from sensor
  float prev_angle = current_angle[motor_id];
  current_angle[motor_id] = motor->shaft_angle;
  
  // Track movement time for idle detection
  float delta = target_angle[motor_id] - current_angle[motor_id];
  if (delta > PI) delta -= 2.0f * PI;
  else if (delta < -PI) delta += 2.0f * PI;
  
  if (abs(delta) > IDLE_ERROR_THRESHOLD) {  // Only stay active if error > ~1°
    last_movement_time[motor_id] = now;
  }
  
  // Enter idle mode if target reached and no motion for IDLE_TIMEOUT
  if (now - last_movement_time[motor_id] > MOTOR_IDLE_TIMEOUT_MS) {
    // At rest - reduce voltage to 0 to prevent heat buildup
    motor->voltage_limit = 0.0f;  // No current draw
  } else {
    // In motion - restore full voltage
    motor->voltage_limit = MOTOR0_VOLTAGE_LIMIT;
  }
  
  // Command motor to reach target angle.
  // target_angle[] is the single source of truth set by MIDI/Commander glue.
  motor->move(target_angle[motor_id]);
  
  // Record position hold statistics (use shortest-path error for endless motors)
  float error = abs(delta);
  record_motor_hold(motor_id, error);
  
  // Diagnostic: detect if motor is stuck
  static unsigned long last_stuck_check = 0;
  static uint16_t stuck_count = 0;
  
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
  
  // Record movement if target changed
  if (abs(target_angle[motor_id] - angle) > 0.01f) {
    record_motor_movement(motor_id);
    // Reset velocity PID integral to prevent carry-over oscillation
    if (motors[motor_id]) {
      motors[motor_id]->PID_velocity.reset();
    }
  }
  
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
  
  float original_angle = angle;
  
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
  
  // Record if limit was hit
  if (abs(angle - original_angle) > 0.01f) {
    record_motor_limit(motor_id);
  }
}