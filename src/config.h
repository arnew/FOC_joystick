#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

/**
 * Motor Profile Definition
 * Defines physical and operational parameters for a single motor
 */
struct MotorProfile {
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
  uint8_t midi_cc;         // MIDI CC number (0-127)
  const char* label;       // Human-readable name (Throttle, Flaps, etc.)
  bool reversed;           // Reverse joystick output (100% → 0%)
  float scaling_factor;    // Scaling multiplier for angle calculation
  MotorProfile motor;      // Motor configuration for this axis
};

// ============================================================================
// MOTOR PROFILES
// ============================================================================
// Hardware-dependent configurations for different motor types

static const MotorProfile MOTOR_0_ENDLESS = {
  .min_angle = 0.0f,
  .max_angle = 6.28318f,  // 360 degrees in radians (endless)
  .is_endless = true,
  .voltage_limit = 2.0f,
  .label = "Motor (Endless Trim)"
};

static const MotorProfile MOTOR_0_LIMITED = {
  .min_angle = 0.0f,
  .max_angle = 3.14159f,  // 180 degrees in radians (limited range)
  .is_endless = false,
  .voltage_limit = 2.0f,
  .label = "Motor (Limited 0-180°)"
};

// ============================================================================
// AIRBUS A320 CONFIGURATION
// ============================================================================
// MIDI CC mappings for Airbus A320 flight controls
// Note: With single-motor hardware, only ONE axis is active at a time.
// Set MIDI CC sender to control the desired axis.
//
// Aircraft Controls (with typical MIDI CC assignments):
// - CC#7  → Throttle (0-100%, limited 0-180°)
// - CC#11 → Flaps (discrete: 0,1,2,3,Full - represented as 0-180°)
// - CC#64 → Trim (endless -100% to +100%)
// - CC#2  → Spoilers (0-100%, limited 0-180°)
// - CC#32 → Landing Gear (0-100%, limited 0-180°, with detents)

// FIXME: DETENTS are not implmented!
// FIXME: the description and implementation does not respect README.md

static const AxisProfile A320_CONFIG[] = {
  {
    .midi_cc = 7,           // Throttle
    .label = "A320 Throttle",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0_LIMITED
  },
  {
    .midi_cc = 11,          // Flaps
    .label = "A320 Flaps",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0_LIMITED
  },
  {
    .midi_cc = 64,          // Trim (Sustain pedal)
    .label = "A320 Trim",
    .reversed = false,
    .scaling_factor = 2.0f,
    .motor = MOTOR_0_ENDLESS
  },
  {
    .midi_cc = 2,           // Spoilers
    .label = "A320 Spoilers",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0_LIMITED
  },
  {
    .midi_cc = 32,          // Landing Gear
    .label = "A320 Landing Gear",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0_LIMITED
  }
};

#define NUM_A320_AXES (sizeof(A320_CONFIG) / sizeof(AxisProfile))

// ============================================================================
// CESSNA 172 CONFIGURATION
// ============================================================================
// MIDI CC mappings for Cessna 172 flight controls
// With single-motor hardware: Set sender to control one axis at a time
//
// Aircraft Controls (with standard Flight Sim MIDI assignments):
// - CC#7  → Throttle (0-100%, limited 0-180°)
// - CC#5  → Flaps (typically 5 positions, represented as 0-180°)
// - CC#64 → Trim (endless -100% to +100%)
// - CC#35 → Landing Gear (0-100%, limited 0-180°)

// FIXME: DETENTS are not implmented!
// FIXME: the description and implementation does not respect README.md

static const AxisProfile CESSNA_CONFIG[] = {
  {
    .midi_cc = 7,           // Throttle
    .label = "Cessna Throttle",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0_LIMITED
  },
  {
    .midi_cc = 5,           // Flaps
    .label = "Cessna Flaps",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0_LIMITED
  },
  {
    .midi_cc = 64,          // Trim
    .label = "Cessna Trim",
    .reversed = false,
    .scaling_factor = 2.0f,
    .motor = MOTOR_0_ENDLESS
  },
  {
    .midi_cc = 35,          // Landing Gear
    .label = "Cessna Landing Gear",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0_LIMITED
  }
};

#define NUM_CESSNA_AXES (sizeof(CESSNA_CONFIG) / sizeof(AxisProfile))

// ============================================================================
// GLIDER CONFIGURATION
// ============================================================================
// MIDI CC mappings for Glider flight controls
// With single-motor hardware: Set sender to control one axis at a time
//
// Aircraft Controls:
// - CC#2  → Spoilers/Airbrakes (0-100%, limited 0-180°)
// - CC#64 → Trim (endless -100% to +100%)

// FIXME: DETENTS are not implmented!
// FIXME: the description and implementation does not respect README.md

static const AxisProfile GLIDER_CONFIG[] = {
  {
    .midi_cc = 2,           // Spoilers/Airbrakes
    .label = "Glider Spoilers",
    .reversed = false,
    .scaling_factor = 1.0f,
    .motor = MOTOR_0_LIMITED
  },
  {
    .midi_cc = 64,          // Trim
    .label = "Glider Trim",
    .reversed = false,
    .scaling_factor = 2.0f,
    .motor = MOTOR_0_ENDLESS
  }
};

#define NUM_GLIDER_AXES (sizeof(GLIDER_CONFIG) / sizeof(AxisProfile))

// ============================================================================
// PROFILE ENUMERATIONS
// ============================================================================

enum ProfileType {
  PROFILE_A320 = 0,
  PROFILE_CESSNA = 1,
  PROFILE_GLIDER = 2,
  NUM_PROFILES = 3
};

// Profile metadata for runtime switching
struct ProfileMetadata {
  const char* name;
  const AxisProfile* config;
  uint8_t num_axes;
};

// All available profiles
static const ProfileMetadata ALL_PROFILES[NUM_PROFILES] = {
  {
    .name = "A320",
    .config = A320_CONFIG,
    .num_axes = NUM_A320_AXES
  },
  {
    .name = "Cessna",
    .config = CESSNA_CONFIG,
    .num_axes = NUM_CESSNA_AXES
  },
  {
    .name = "Glider",
    .config = GLIDER_CONFIG,
    .num_axes = NUM_GLIDER_AXES
  }
};

// ============================================================================
// ACTIVE CONFIGURATION (RUNTIME STATE)
// ============================================================================

extern volatile ProfileType g_active_profile;

void set_active_profile(ProfileType profile);
ProfileType get_active_profile();

/**
 * Get active profile metadata
 * @return Pointer to active profile metadata
 */
static inline const ProfileMetadata* get_profile_metadata() {
  return &ALL_PROFILES[g_active_profile];
}

/**
 * Find axis by CC in current active profile
 * @param midi_cc MIDI control change number
 * @return Pointer to AxisProfile if found, NULL otherwise
 */
static inline const AxisProfile* find_axis_by_cc_runtime(uint8_t midi_cc) {
  const ProfileMetadata* meta = get_profile_metadata();
  for (uint8_t i = 0; i < meta->num_axes; i++) {
    if (meta->config[i].midi_cc == midi_cc) {
      return &meta->config[i];
    }
  }
  return NULL;
}

#define NUM_MOTORS 1

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Find axis profile by MIDI CC number (uses runtime profile)
 */
static inline const AxisProfile* find_axis_by_cc(uint8_t midi_cc) {
  return find_axis_by_cc_runtime(midi_cc);
}

/**
 * Get the active motor profile (endless or limited, compile-time selected)
 */
static inline const MotorProfile* get_motor_profile(uint8_t /*unused*/ = 0) {
  #ifdef MOTOR_LIMITED
  return &MOTOR_0_LIMITED;
  #else
  return &MOTOR_0_ENDLESS;
  #endif
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

