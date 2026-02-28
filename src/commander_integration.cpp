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
#include "statistics.h"

// SimpleFOC Commander instance
Commander commander = Commander(Serial, '\n', ' ');

// Custom command: Set target directly (bypasses SimpleFOC motor.target)
// Format: T45 (degrees, auto-converted to radians internally)
static void cmd_set_target(char* cmd) {
  // Commander passes payload after command letter, so cmd is like "45"
  // (it may be empty when query/help is used)
  if (!cmd || !cmd[0]) {
    // Query current target and convert radians → degrees for display
    float target_rad = get_motor_target(0);
    float target_deg = target_rad * 180.0f / PI;
    Serial.print("[CMD] T target=");
    Serial.print(target_deg);
    Serial.println("°");
    return;
  }

  // Parse input as degrees, convert to radians
  float angle_deg = atof(cmd);
  float angle_rad = angle_deg * PI / 180.0f;
  set_motor_target(0, angle_rad);
  
  Serial.print("[CMD] Set target_angle[0] = ");
  Serial.print(angle_deg);
  Serial.println("°");
  Serial.print("[CMD] Verify: target_angle[0] = ");
  float verify_rad = get_motor_target(0);
  float verify_deg = verify_rad * 180.0f / PI;
  Serial.print(verify_deg);
  Serial.println("°");
}



// Custom command: Statistics display
// Format: S (show stats), S0 (reset counters)
static void cmd_statistics(char* cmd) {
  if (!cmd || !cmd[0]) {
    // No argument: show statistics
    print_statistics();
    return;
  }

  uint8_t action = atoi(cmd);
  if (action == 0) {
    reset_statistics();
  }
}

// Motor command passthrough for runtime PID tuning.
// Registered as 'M' → user sends MAP10.0 for angle P, etc.
static void cmd_motor(char* cmd) {
  commander.motor(&motor0, cmd);
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
  // Register motor 0 for runtime PID tuning via SimpleFOC Commander.
  // Send 'M' prefix followed by motor sub-commands:
  //   MAP  / MAP10.0   - angle PID P (query / set)
  //   MAI  / MAI0.3    - angle PID I
  //   MAD  / MAD2.0    - angle PID D
  //   MAL  / MAL4.0    - angle PID output limit (velocity setpoint limit)
  //   MAF  / MAF0.01   - angle LPF Tf
  //   MVP  / MVP0.2    - velocity PID P
  //   MVI  / MVI0.5    - velocity PID I
  //   MLU  / MLU2.0    - voltage limit
  //   ME   / ME1       - enable/disable
  commander.add('M', cmd_motor, (const char*)"motor PID (MAP/MAI/MAD/MVP/MVI/MAL/MAF)");

  // Register custom commands
  commander.add('T', cmd_set_target, (const char*)"set target directly");
  commander.add('A', cmd_switch_profile, (const char*)"aircraft profile (0=A320, 1=Cessna, 2=Glider)");
  commander.add('S', cmd_statistics, (const char*)"statistics (S=show, S0=reset)");
  
  Serial.println("[COMMANDER] Initialized - SimpleFOC standard interface");
  Serial.println("[COMMANDER] Commands available:");
  Serial.println("  MAP/MAI/MAD - Angle PID (query/set, e.g. MAP10.0)");
  Serial.println("  MVP/MVI     - Velocity PID");
  Serial.println("  MAL/MAF     - Angle limit / LPF Tf");
  Serial.println("  T<angle>    - Set target directly");
  Serial.println("  A           - Show profile options");
  Serial.println("  A<0-2>      - Switch profile (0=A320, 1=Cessna, 2=Glider)");
  Serial.println("  S           - Show device statistics");
  Serial.println("  S0          - Reset statistics counters");
}

void update_commander() {
  // Process serial commands (non-blocking)
  if (Serial.available()) {
    record_commander_cmd();
  }
  commander.run();
}
