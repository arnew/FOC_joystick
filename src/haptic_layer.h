/**
 * haptic_layer.h — Configurable haptic overlay for motor control
 *
 * Architecture (v2 — observe/snap/set):
 *   Observes actual motor angle → snaps to nearest detent → sets target.
 *   Motor is the state. No delta accumulation.
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

/** Initialize from active profile. Call once in setup(). */
void haptic_init();

/** Load haptic params from a ControlProfile by index. */
void haptic_load_profile(uint8_t profile_id);

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

/** Get the HID axis value (0–1023) mapped from detent position. */
uint16_t haptic_get_hid_value();

/** Set position externally (e.g. from T command). Snaps to nearest detent. */
void haptic_set_position(float angle_deg);

/** Set position as 0.0–1.0 fraction of range. For MIDI CC mapping. */
void haptic_set_position_normalized(float norm_0_1);

// ============================================================================
// COMMANDER INTEGRATION
// ============================================================================

/** Commander callback — register with: commander.add('W', haptic_cmd, ...) */
void haptic_cmd(char* cmd);

#endif // HAPTIC_LAYER_H
