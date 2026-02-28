/**
 * profile_manager.h - Runtime Aircraft Profile Management
 * 
 * Allows switching between aircraft profiles (A320, Cessna, Glider) without recompiling
 * Via Commander interface: P<num> command
 */

#ifndef PROFILE_MANAGER_H
#define PROFILE_MANAGER_H

#include "config.h"

/**
 * Print all available profiles
 */
void print_available_profiles() {
  Serial.println("\n[PROFILES] Available aircraft profiles:");
  for (uint8_t i = 0; i < NUM_PROFILES; i++) {
    Serial.print("  ");
    Serial.print(i);
    Serial.print(": ");
    Serial.println(ALL_PROFILES[i].name);
  }
}

/**
 * Switch to a specific profile
 * @param profile_id Profile index (0=A320, 1=Cessna, 2=Glider)
 * @return true if successful, false if invalid index
 */
bool switch_to_profile(uint8_t profile_id) {
  if (profile_id >= NUM_PROFILES) {
    return false;
  }
  
  set_active_profile((ProfileType)profile_id);
  
  Serial.print("[PROFILES] Switched to: ");
  Serial.println(ALL_PROFILES[profile_id].name);
  
  Serial.print("  Axes: ");
  Serial.println(ALL_PROFILES[profile_id].num_axes);
  
  return true;
}

/**
 * Print current active profile
 */
void print_active_profile() {
  ProfileType active = get_active_profile();
  Serial.print("[PROFILES] Current: ");
  Serial.println(ALL_PROFILES[active].name);
}

#endif // PROFILE_MANAGER_H
