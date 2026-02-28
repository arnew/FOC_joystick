/**
 * statistics.h - Device Self-Inspection & Statistics
 * 
 * Tracks runtime statistics for quality monitoring:
 * - System uptime
 * - Loop timing (min/max/avg)
 * - Motor control performance
 * - Message counters (MIDI, HID, Commander)
 * - Error detection
 */

#ifndef STATISTICS_H
#define STATISTICS_H

#include <Arduino.h>

// ============================================================================
// STATISTICS DATA STRUCTURES
// ============================================================================

struct LoopTimingStats {
  uint32_t count;           // Total loop iterations
  uint32_t min_us;          // Minimum loop time (microseconds)
  uint32_t max_us;          // Maximum loop time (microseconds)
  uint64_t sum_us;          // Sum for average calculation
};

struct MotorStats {
  uint32_t movements;       // Number of target changes
  uint32_t holds;           // Number of position holds checked
  float max_error;          // Maximum position error seen (radians)
  uint32_t limit_hits;      // Number of limit clamp/wrap events
};

struct MessageStats {
  uint32_t midi_bytes;      // MIDI bytes processed
  uint32_t midi_messages;   // Complete MIDI messages
  uint32_t hid_reports;     // HID reports sent
  uint32_t commander_cmds;  // Commander commands processed
};

struct SystemStats {
  uint32_t uptime_ms;       // System uptime (milliseconds)
  LoopTimingStats loop;     // Loop timing statistics
  MotorStats motor[1];      // Per-motor statistics
  MessageStats messages;    // Message counters
};

// ============================================================================
// STATISTICS FUNCTIONS
// ============================================================================

/**
 * Initialize statistics collection
 */
void init_statistics();

/**
 * Record loop iteration timing
 * @param duration_us Loop duration in microseconds
 */
void record_loop_timing(uint32_t duration_us);

/**
 * Record motor movement event
 * @param motor_id Motor index
 */
void record_motor_movement(uint8_t motor_id);

/**
 * Record motor position hold check
 * @param motor_id Motor index
 * @param error Position error in radians
 */
void record_motor_hold(uint8_t motor_id, float error);

/**
 * Record motor limit event
 * @param motor_id Motor index
 */
void record_motor_limit(uint8_t motor_id);

/**
 * Record MIDI byte processed
 */
void record_midi_byte();

/**
 * Record complete MIDI message
 */
void record_midi_message();

/**
 * Record HID report sent
 */
void record_hid_report();

/**
 * Record commander command
 */
void record_commander_cmd();

/**
 * Update uptime counter
 * Call once per loop
 */
void update_statistics_uptime();

/**
 * Get current statistics snapshot
 * @return Pointer to statistics structure
 */
const SystemStats* get_statistics();

/**
 * Print statistics report to Serial
 */
void print_statistics();

/**
 * Reset all statistics counters
 */
void reset_statistics();

#endif // STATISTICS_H
