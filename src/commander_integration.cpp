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

// Custom command: Reboot to BOOTSEL mode
// Format: RB
static void cmd_reboot_bootloader(char* cmd) {
  Serial.println("[BOOTLOADER] Rebooting to BOOTSEL mode...");
  Serial.flush();
  delay(200);
  
  // RP2040 magic: write signature to RAM and reset to trigger bootloader
  uint32_t *magic = (uint32_t *)0x20042000;
  *magic = 0x73717856;  // "vxsq" - bootloader magic
  
  // Reset via ARM AIRCR register
  __asm("dsb");
  SCB->AIRCR = 0x05FA0004;  // AIRCR reset vector
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
  commander.motor(&motor0, (const char*)"M0");
  
  // Register custom commands
  commander.add('T', cmd_set_target, (const char*)"set target directly");
  commander.add('A', cmd_switch_profile, (const char*)"aircraft profile (0=A320, 1=Cessna, 2=Glider)");
  commander.add('S', cmd_statistics, (const char*)"statistics (S=show, S0=reset)");
  commander.add('R', cmd_reboot_bootloader, (const char*)"reboot to BOOTSEL (RB)");
  
  Serial.println("[COMMANDER] Initialized - SimpleFOC standard interface");
  Serial.println("[COMMANDER] Commands available:");
  Serial.println("  M0          - Motor 0 access (T, P, I, D, L, C, ?)");
  Serial.println("  T<angle>    - Set target directly");
  Serial.println("  A           - Show profile options");
  Serial.println("  A<0-2>      - Switch profile (0=A320, 1=Cessna, 2=Glider)");
  Serial.println("  S           - Show device statistics");
  Serial.println("  S0          - Reset statistics counters");
  Serial.println("  RB          - Reboot to BOOTSEL (for firmware upload)");
}

void update_commander() {
  // Process serial commands (non-blocking)
  if (Serial.available()) {
    record_commander_cmd();
  }
  commander.run();
}
