/**
 * midi_handler.h — USB MIDI Input
 *
 * CC matching:
 *   Active profile's midi_cc → position (0-127 → 0-100% of haptic range)
 *   CC#121               → profile select (value = profile index 0..9)
 */

#ifndef MIDI_HANDLER_H
#define MIDI_HANDLER_H

#include <Arduino.h>

// ============================================================================
// MIDI MESSAGE PARSER
// ============================================================================

/**
 * Initialize MIDI handler
 */
void init_midi_handler();

/**
 * Process single MIDI byte
 * State machine assembles 3-byte CC messages
 * @param byte MIDI byte from USB MIDI
 */
void handle_midi_byte(uint8_t byte);

/**
 * Process complete MIDI CC message.
 * Routes to haptic_set_position_normalized or switch_to_profile.
 */
void process_midi_message(uint8_t status, 
                          uint8_t cc_number, 
                          uint8_t cc_value);

#endif // MIDI_HANDLER_H
