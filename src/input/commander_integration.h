/**
 * commander_integration.h — SimpleFOC Commander Interface
 *
 * Commands: M(motor PID) T(target°) A(profile) W(haptic)
 */

#ifndef COMMANDER_INTEGRATION_H
#define COMMANDER_INTEGRATION_H

#include <Arduino.h>
#include <SimpleFOC.h>

// ============================================================================
// COMMANDER FUNCTIONS
// ============================================================================

/**
 * Initialize SimpleFOC Commander
 * Registers motor + profile + haptic commands
 */
void init_commander();

/**
 * Process commander input
 * Call frequently in loop()
 */
void update_commander();

#endif // COMMANDER_INTEGRATION_H
