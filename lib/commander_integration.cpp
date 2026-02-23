/**
 * commander_integration.cpp - SimpleFOC Commander
 */

#include "commander_integration.h"
#include "motor_control.h"

// ============================================================================
// COMMANDER INSTANCE
// ============================================================================

Commander commander = Commander(Serial);

// ============================================================================
// COMMANDER SETUP
// ============================================================================

void init_commander() {
  // Add motor0 to commander with ID 'M'
  // Commands: MP20.0 (angle P), MVI10.0 (vel I)
  commander.add('M', &motor0, "motor0");
  
  #if NUM_MOTORS > 1
  // Add motor1 with ID 'N'
  commander.add('N', &motor1, "motor1");
  #endif
  
  Serial.println(
    "SimpleFOC Commander initialized");
  Serial.println(
    "Commands: MP<val>, MI<val>, MD<val>");
  Serial.println(
    "          MVP<val>, MVI<val>, MVD<val>");
}

// ============================================================================
// COMMANDER UPDATE
// ============================================================================

void update_commander() {
  // Process serial commands
  commander.run();
}
