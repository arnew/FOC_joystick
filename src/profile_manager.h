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

void init_profile_manager();
void configure_usb_identity_from_profile();

void print_available_profiles();
void print_active_profile();

bool switch_to_profile(uint8_t profile_id);
bool save_active_profile();

#endif // PROFILE_MANAGER_H
