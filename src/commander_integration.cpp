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
 *   M0T3.14    - Set target to 3.14 radians
 *   M0C        - Run motion test
 *   M0?        - Get motor status
 */

#include "commander_integration.h"
#include "motor_control.h"

// SimpleFOC Commander instance
Commander commander = Commander(Serial, '\n', ' ');

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
  
  Serial.println("[COMMANDER] Initialized - SimpleFOC standard interface");
  Serial.println("[COMMANDER] Commands: M0 (motor 0 controls)");
  Serial.println("[COMMANDER] Example: M0T3.14 (set target), M0? (status), M0C (test)");
}

void update_commander() {
  // Process serial commands (non-blocking)
  commander.run();
}
