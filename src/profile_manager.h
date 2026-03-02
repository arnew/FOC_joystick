/**
 * profile_manager.h — Runtime Control Profile Management
 *
 * Persists the selected ControlProfile index to EEPROM.
 * USB identity (product name / PID) is set from the profile at boot.
 * Profile switch applies haptic config and reboots for USB re-enumeration.
 */

#ifndef PROFILE_MANAGER_H
#define PROFILE_MANAGER_H

#include "config.h"

// ============================================================================
// RUNTIME STATE — profile index + accessors
// ============================================================================

extern volatile uint8_t g_active_profile;

void set_active_profile(uint8_t profile);
uint8_t get_active_profile();

/**
 * Get active control profile (read-only).
 */
static inline const ControlProfile* get_active_control_profile() {
    if (g_active_profile < NUM_PROFILES)
        return &ALL_PROFILES[g_active_profile];
    return &ALL_PROFILES[0];
}

// ============================================================================
// PROFILE MANAGEMENT API
// ============================================================================

void init_profile_manager();
void configure_usb_identity_from_profile();

void print_available_profiles();
void print_active_profile();

bool switch_to_profile(uint8_t profile_id);
bool save_active_profile();

#endif // PROFILE_MANAGER_H
