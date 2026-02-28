/**
 * commander_integration.cpp - SimpleFOC Commander Interface
 * 
 * Standard SimpleFOC Commander for:
 * - Real-time PID tuning
 * - Motor parameter adjustment
 * - Hardware test verification (CI)
 * - SimpleFOC Studio integration
 * 
 * Usage:
 *   M0         - Access motor 0 (shows available commands)
 *   M0T3.14    - Set target to 3.14 radians (via SimpleFOC)
 *   M0C        - Run motion test
 *   M0?        - Get motor status
 *   T3.14      - Set target directly (test command)
 */

#include "commander_integration.h"
#include "motor_control.h"

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
  
  // Register custom test command
  commander.add('T', cmd_set_target, "set target directly");
  
  Serial.println("[COMMANDER] Initialized - SimpleFOC standard interface");
  Serial.println("[COMMANDER] Commands: M0 (motor 0 controls), T<angle> (set target directly)");
  Serial.println("[COMMANDER] Example: M0 T3.14 (SimpleFOC), T3.14 (direct), M0? (status)");
}

void update_commander() {
  // Process serial commands (non-blocking)
  commander.run();
}
