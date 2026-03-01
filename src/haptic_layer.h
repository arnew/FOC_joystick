/**
 * haptic_layer.h — Configurable haptic overlay for motor control
 *
 * Adds detent snapping and end-stop enforcement ON TOP of the existing
 * SimpleFOC angle-mode motor.  All parameters are adjustable at runtime
 * via Commander serial commands (W prefix).
 *
 * Architecture:
 *   Motor reads user force as position deviation → haptic_layer converts
 *   raw motor angle into a snapped detent position with end-stop clamping
 *   → sets motor target to the nearest detent.
 *
 * The layer does NOT touch PID parameters.  It only decides WHAT target
 * the motor should hold.
 */

#ifndef HAPTIC_LAYER_H
#define HAPTIC_LAYER_H

#include <Arduino.h>

// ============================================================================
// HAPTIC CONFIGURATION (all adjustable at runtime via Commander 'W' commands)
// ============================================================================

struct HapticConfig {
    float range_deg;        // Total travel range in degrees (e.g. 180.0)
    float center_deg;       // Center position in degrees (e.g. 90.0)
    uint16_t detent_count;  // Number of detent positions (0 = free rotation)
    float detent_strength;  // 0.0–1.0: how aggressively to snap (0=off, 1=full)
    float endstop_margin;   // degrees past end before hard-stop kicks in
    bool  enabled;          // Master enable
};

// ============================================================================
// PUBLIC API
// ============================================================================

/** Initialize with default config. Call once in setup(). */
void haptic_init();

/** Process one tick. Call every loop iteration AFTER update_motor(). */
void haptic_update();

/** Get current configuration (read-only). */
const HapticConfig& haptic_get_config();

/** Set entire config at once. */
void haptic_set_config(const HapticConfig& cfg);

/** Get the current detent index (0..detent_count). -1 if disabled. */
int16_t haptic_get_detent_index();

/** Get the snapped target angle in degrees. */
float haptic_get_target_deg();

/** Get the raw (user-pushed) angle in degrees. */
float haptic_get_raw_deg();

/** Get the HID axis value (0–1023) mapped from detent position. */
uint16_t haptic_get_hid_value();

/** Set position externally (e.g. from T command). Snaps to nearest detent. */
void haptic_set_position(float angle_deg);

// ============================================================================
// COMMANDER INTEGRATION
// ============================================================================

/** Commander callback — register with: commander.add('W', haptic_cmd, ...) */
void haptic_cmd(char* cmd);

#endif // HAPTIC_LAYER_H
