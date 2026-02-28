/**
 * commander_integration.cpp - SimpleFOC Commander Interface
 * 
 * Standard SimpleFOC Commander for:
 * - Real-time PID tuning
 * - Motor parameter adjustment
 * - Hardware test verification (CI)
 * - SimpleFOC Studio integration
 * - Runtime aircraft profile switching
 * 
 * Usage:
 *   M0         - Access motor 0 (shows available commands)
 *   M0T3.14    - Set target to 3.14 radians (via SimpleFOC)
 *   M0C        - Run motion test
 *   M0?        - Get motor status
 *   T3.14      - Set target directly (test command)
 *   P          - Show available profiles
 *   P0         - Switch to A320 profile
 *   P1         - Switch to Cessna profile
 *   P2         - Switch to Glider profile
 */

#include "commander_integration.h"
#include "motor_control.h"
#include "profile_manager.h"

// SimpleFOC Commander instance
Commander commander = Commander(Serial, '\n', ' ');

// Custom command: Set target directly (bypasses SimpleFOC motor.target)
// Format: T3.14
static void cmd_set_target(char* cmd) {
  // Commander passes payload after command letter, so cmd is like "3.14"
  // (it may be empty when query/help is used)
  if (!cmd || !cmd[0]) {
    Serial.print("[CMD] T target=");
    Serial.println(get_motor_target(0));
    return;
  }

  float angle = atof(cmd);
  set_motor_target(0, angle);
  
  Serial.print("[CMD] Set target_angle[0] = ");
  Serial.println(angle);
  Serial.print("[CMD] Verify: target_angle[0] = ");
  Serial.println(get_motor_target(0));
}

// Custom command: Profile switching
// Format: P (show available), P0 (switch to A320), P1 (Cessna), P2 (Glider)
static void cmd_switch_profile(char* cmd) {
  if (!cmd || !cmd[0]) {
    // No argument: show current profile and available options
    print_active_profile();
    print_available_profiles();
    return;
  }

  uint8_t profile_id = atoi(cmd);
  if (switch_to_profile(profile_id)) {
    Serial.println("[PROFILES] ✓ Profile switched successfully");
  } else {
    Serial.print("[PROFILES] ✗ Invalid profile ID: ");
    Serial.println(profile_id);
    print_available_profiles();
  }
}

void init_commander() {
  // Register motor 0 with commander
  // This gives access to all SimpleFOC motor commands:
  // - T: target angle
  // - P: PID P gain
  // - I: PID I gain  
  // - D: PID D gain
  // - L: voltage limit
  // - C: motion test
  // - ?: status
  commander.motor(&motor0, "M0");
  
  // Register custom commands
  commander.add('T', cmd_set_target, "set target directly");
  commander.add('A', cmd_switch_profile, "aircraft profile (0=A320, 1=Cessna, 2=Glider)");
  
  Serial.println("[COMMANDER] Initialized - SimpleFOC standard interface");
  Serial.println("[COMMANDER] Commands available:");
  Serial.println("  M0          - Motor 0 access (T, P, I, D, L, C, ?)");
  Serial.println("  T<angle>    - Set target directly");
  Serial.println("  A           - Show profile options");
  Serial.println("  A<0-2>      - Switch profile (0=A320, 1=Cessna, 2=Glider)");
}

void update_commander() {
  // Process serial commands (non-blocking)
  commander.run();
}
