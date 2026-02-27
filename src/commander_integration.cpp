/**
 * commander_integration.cpp - SimpleFOC Commander
 */

#include "commander_integration.h"
#include "motor_control.h"

// ============================================================================
// COMMANDER SETUP
// ============================================================================

void init_commander() {
  // Enable motor monitoring on Serial
  // This allows reading motor status
  motor0.useMonitoring(Serial);
  motor0.monitor_start_char = '~';
  motor0.monitor_end_char = '\n';
  
  #if NUM_MOTORS > 1
  motor1.useMonitoring(Serial);
  motor1.monitor_start_char = '~';
  motor1.monitor_end_char = '\n';
  #endif
  
  Serial.println(
    "SimpleFOC monitoring enabled");
  Serial.println(
    "Send '~' to toggle motor monitor");
}

// ============================================================================
// COMMANDER UPDATE
// ============================================================================

void update_commander() {
  // Process motor monitoring
  motor0.monitor();
  
  #if NUM_MOTORS > 1
  motor1.monitor();
  #endif
}
