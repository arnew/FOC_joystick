/**
 * commander_integration.h — SimpleFOC Commander Interface
 * 
 * Standard SimpleFOC Commander for:
 * - Real-time PID tuning (M prefix)
 * - Target setting (T)
 * - Aircraft profile switching (A)
 * - Haptic layer config (W)
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
 * Registers motor commands (M0, M1)
 */
void init_commander();

/**
 * Process commander input
 * Call frequently in loop()
 */
void update_commander();

#endif // COMMANDER_INTEGRATION_H
