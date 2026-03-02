/**
 * commander_integration.cpp — SimpleFOC Commander Interface
 *
 * Commands:
 *   M    — Motor PID tuning (MAP/MAI/MAD/MVP/MVI/MAL/MAF/MLU/ME)
 *   T45  — Set target to 45° (routes through haptic when enabled)
 *   A    — List control profiles
 *   A3   — Switch to profile 3 (persists + reboots for USB identity)
 *   W    — Haptic config (WE/WR/WC/WN/WS/WM for live tweaking)
 */

#include "commander_integration.h"
#include "motor_control.h"
#include "profile_manager.h"
#include "haptic_layer.h"

// SimpleFOC Commander instance
Commander commander = Commander(Serial, '\n', ' ');

// Custom command: Set target directly (bypasses SimpleFOC motor.target)
// Format: T45 (degrees, auto-converted to radians internally)
static void cmd_set_target(char* cmd) {
  // Commander passes payload after command letter, so cmd is like "45"
  // (it may be empty when query/help is used)
  if (!cmd || !cmd[0]) {
    // Query current target and convert radians → degrees for display
    float target_rad = get_motor_target();
    float target_deg = target_rad * 180.0f / PI;
    Serial.print("[CMD] T target=");
    Serial.print(target_deg);
    Serial.println("°");
    return;
  }

  // Parse input as degrees, convert to radians
  float angle_deg = atof(cmd);
  float angle_rad = angle_deg * PI / 180.0f;

  // If haptic layer is active, route through it (snaps to nearest detent)
  if (haptic_get_config().enabled) {
    haptic_set_position(angle_deg);
  } else {
    set_motor_target(angle_rad);
  }
  
  Serial.print("[CMD] Set target_angle = ");
  Serial.print(angle_deg);
  Serial.println("°");
  Serial.print("[CMD] Verify: target_angle = ");
  float verify_rad = get_motor_target();
  float verify_deg = verify_rad * 180.0f / PI;
  Serial.print(verify_deg);
  Serial.println("°");
}



// Motor command passthrough for runtime PID tuning.
// Registered as 'M' → user sends MAP10.0 for angle P, etc.
static void cmd_motor(char* cmd) {
  commander.motor(get_motor_object(), cmd);
}

// Custom command: Profile switching
// Format: A (list all), A3 (switch to profile 3)
static void cmd_switch_profile(char* cmd) {
  if (!cmd || !cmd[0]) {
    print_active_profile();
    print_available_profiles();
    return;
  }

  uint8_t profile_id = atoi(cmd);
  if (!switch_to_profile(profile_id)) {
    Serial.print("[PROFILE] Invalid ID: ");
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
  commander.add('A', cmd_switch_profile, (const char*)"control profile (A=list, A0..A9=switch)");
  commander.add('W', haptic_cmd, (const char*)"haptic layer (W=show, WE/WR/WC/WN/WS/WM)");
  
  Serial.println("[COMMANDER] Commands: M(motor) T(target) A(profile) W(haptic)");
}

void update_commander() {
  // Process serial commands (non-blocking)
  commander.run();
}
