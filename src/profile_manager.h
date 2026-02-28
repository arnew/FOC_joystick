/**
 * profile_manager.h - Runtime Aircraft Profile Management
 * 
 * Allows switching between aircraft profiles (A320, Cessna, Glider) without recompiling.
 * Selected profile is persisted and restored on boot.
 * USB identity (product name / PID) follows selected profile at startup.
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
