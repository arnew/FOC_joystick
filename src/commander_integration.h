/**
 * commander_integration.h - SimpleFOC Commander Interface
 * 
 * Standard SimpleFOC Commander for:
 * - Real-time PID tuning
 * - Motor parameter adjustment  
 * - Hardware test verification (CI)
 * - SimpleFOC Studio integration
 * 
 * Commands:
 *   M0         - Access motor 0 (shows available commands)
 *   M0T3.14    - Set target to 3.14 radians
 *   M0C        - Run motion test
 *   M0?        - Get motor status
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
