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
// CONFIGURATION: Single Endless Motor (Tested & Proven)
// ============================================================================
// Only pico_1motor_endless is tested. Other configs (limited, dual motors)
// were untested and have been removed.
// See .agentic/REMOVED_UNTESTED_CODE.md for details.

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
 * @param motor_id Motor index (always 0 for single-motor config)
 * @return Pointer to MotorProfile if valid, NULL otherwise
 */
static inline const MotorProfile* get_motor_profile(uint8_t motor_id) {
  if (motor_id == 0) return &MOTOR_0;
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

