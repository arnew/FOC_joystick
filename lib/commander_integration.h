/**
 * commander_integration.h - SimpleFOC Commander
 * 
 * SimpleFOC Commander integration for GUI tuning:
 * - Text-based command protocol (MAP20.0, etc)
 * - SimpleFOC Studio compatible
 * - Real-time PID parameter adjustment
 */

#ifndef COMMANDER_INTEGRATION_H
#define COMMANDER_INTEGRATION_H

#include <Arduino.h>
#include <SimpleFOC.h>

// ============================================================================
// COMMANDER INSTANCE
// ============================================================================

extern Commander commander;

// ============================================================================
// COMMANDER FUNCTIONS
// ============================================================================

/**
 * Initialize SimpleFOC Commander
 * Registers motor commands (M0, M1)
 */
void init_commander();

/**
 * Process commander input
 * Call frequently in loop()
 */
void update_commander();

#endif // COMMANDER_INTEGRATION_H
