#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

/**
 * Motor Profile Definition
 * Defines physical and operational parameters for a single motor
 */
struct MotorProfile {
  uint8_t id;              // Motor index (0-1)
  float min_angle;         // Minimum angle (degrees)
  float max_angle;         // Maximum angle (degrees)
  bool is_endless;         // True = trim/endless rotation; False = limited range
  float voltage_limit;     // Max voltage to motor (V)
  const char* label;       // Human-readable name
};

/**
 * Axis Profile Definition
 * Maps a control axis to motor and MIDI input
 */
struct AxisProfile {
  uint8_t motor_id;        // Motor index this axis controls (0-1)
  uint8_t midi_cc;         // MIDI CC number (0-127)
  const char* label;       // Human-readable name (Throttle, Flaps, etc.)
  bool reversed;           // Reverse joystick output (100% → 0%)
  float scaling_factor;    // Scaling multiplier for angle calculation
  MotorProfile motor;      // Motor configuration for this axis
};

// ============================================================================
// HARDWARE CONFIGURATION SELECTOR
// ============================================================================
// Build with: platformio run -e pico_1motor_endless
//             platformio run -e pico_1motor_limited
//             platformio run -e pico_2motor_limited

#if !defined(HW_CONFIG)
  #define HW_CONFIG HW_1MOTOR_ENDLESS
#endif

#define HW_1MOTOR_ENDLESS    0
#define HW_1MOTOR_LIMITED    1
#define HW_2MOTOR_LIMITED    2

// ============================================================================
// CONFIGURATION 1: Single Endless Motor (Current Hardware - Trim-like)
// ============================================================================
#if HW_CONFIG == HW_1MOTOR_ENDLESS

static const MotorProfile MOTOR_0 = {
  .id = 0,
  .min_angle = 0.0f,
  .max_angle = 6.28318f,  // 360 degrees in radians (endless)
  .is_endless = true,
  .voltage_limit = 2.0f,
  .label = "Motor 0 (Endless Trim)"
};

static const AxisProfile A320_CONFIG[] = {
  {
    .motor_id = 0,
    .midi_cc = 64,          // Sustain pedal CC (trim-like control)
    .label = "Trim",
    .reversed = false,
    .scaling_factor = 2.0f,
    .motor = MOTOR_0
  }
};

#define NUM_A320_AXES (sizeof(A320_CONFIG) / sizeof(AxisProfile))
#define NUM_MOTORS 1

// ============================================================================
// CONFIGURATION 2: Single Limited Motor (0-180° like throttle/flaps)
// ============================================================================
#elif HW_CONFIG == HW_1MOTOR_LIMITED

static const MotorProfile MOTOR_0 = {
  .id = 0,
  .min_angle = 0.0f,
  .max_angle = 3.14159f,  // 180 degrees in radians
  .is_endless = false,
  .voltage_limit = 2.0f,
  .label = "Motor 0 (Limited Range)"
};

static const AxisProfile A320_CONFIG[] = {
  {
    .motor_id = 0,
    .midi_cc = 7,           // Standard MIDI volume
    .label = "Throttle",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0
  },
  {
    .motor_id = 0,
    .midi_cc = 11,          // Expression
    .label = "Flaps",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0
  }
};

#define NUM_A320_AXES (sizeof(A320_CONFIG) / sizeof(AxisProfile))
#define NUM_MOTORS 1

// ============================================================================
// CONFIGURATION 3: Dual Motors (Throttle + Trim, both limited & endless)
// ============================================================================
#elif HW_CONFIG == HW_2MOTOR_LIMITED

static const MotorProfile MOTOR_0 = {
  .id = 0,
  .min_angle = 0.0f,
  .max_angle = 3.14159f,  // 180 degrees
  .is_endless = false,
  .voltage_limit = 2.0f,
  .label = "Motor 0 (Throttle/Flaps)"
};

static const MotorProfile MOTOR_1 = {
  .id = 1,
  .min_angle = 0.0f,
  .max_angle = 6.28318f,  // 360 degrees (endless trim)
  .is_endless = true,
  .voltage_limit = 2.0f,
  .label = "Motor 1 (Trim)"
};

static const AxisProfile A320_CONFIG[] = {
  {
    .motor_id = 0,
    .midi_cc = 7,
    .label = "Throttle",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0
  },
  {
    .motor_id = 0,
    .midi_cc = 5,
    .label = "Flaps",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0
  },
  {
    .motor_id = 0,
    .midi_cc = 65,
    .label = "Spoilers",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0
  },
  {
    .motor_id = 1,
    .midi_cc = 10,
    .label = "Trim",
    .reversed = false,
    .scaling_factor = 2.0f,
    .motor = MOTOR_1
  },
  {
    .motor_id = 1,
    .midi_cc = 11,
    .label = "Gear",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_1
  }
};

#define NUM_A320_AXES (sizeof(A320_CONFIG) / sizeof(AxisProfile))
#define NUM_MOTORS 2

#endif  // HW_CONFIG selection

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Find axis profile by MIDI CC number
 * @param midi_cc MIDI control change number
 * @return Pointer to AxisProfile if found, NULL otherwise
 */
static inline const AxisProfile* find_axis_by_cc(uint8_t midi_cc) {
  for (uint8_t i = 0; i < NUM_A320_AXES; i++) {
    if (A320_CONFIG[i].midi_cc == midi_cc) {
      return &A320_CONFIG[i];
    }
  }
  return NULL;
}

/**
 * Get motor profile by index
 * @param motor_id Motor index (0-1)
 * @return Pointer to MotorProfile if valid, NULL otherwise
 */
static inline const MotorProfile* get_motor_profile(uint8_t motor_id) {
  if (motor_id == 0) return &MOTOR_0;
  #if NUM_MOTORS > 1
  if (motor_id == 1) return &MOTOR_1;
  #endif
  return NULL;
}

/**
 * Find first axis profile by motor ID
 * @param motor_id Motor index (0-1)
 * @return Pointer to first AxisProfile for motor, NULL if none found
 */
static inline const AxisProfile* find_axis_by_motor(uint8_t motor_id) {
  for (uint8_t i = 0; i < NUM_A320_AXES; i++) {
    if (A320_CONFIG[i].motor_id == motor_id) {
      return &A320_CONFIG[i];
    }
  }
  return NULL;
}

/**
 * Count number of axes controlled by a motor
 * @param motor_id Motor index (0-1)
 * @return Number of axes assigned to motor
 */
static inline uint8_t count_axes_for_motor(uint8_t motor_id) {
  uint8_t count = 0;
  for (uint8_t i = 0; i < NUM_A320_AXES; i++) {
    if (A320_CONFIG[i].motor_id == motor_id) {
      count++;
    }
  }
  return count;
}

/**
 * Convert MIDI CC value (0-127) to motor angle (min-max degrees)
 * @param axis Axis profile
 * @param cc_value MIDI CC value (0-127)
 * @return Target angle in radians
 */
static inline float cc_to_angle(const AxisProfile* axis, uint8_t cc_value) {
  if (!axis) return 0.0f;
  
  float normalized = (float)cc_value / 127.0f;  // 0.0 to 1.0
  const MotorProfile* motor = &(axis->motor);
  
  // For limited axes: map to min-max range
  if (!motor->is_endless) {
    return motor->min_angle + (normalized * (motor->max_angle - motor->min_angle));
  }
  
  // For endless axes: scale full range
  return normalized * 6.28318f;  // 360 degrees
}

#endif  // CONFIG_H

