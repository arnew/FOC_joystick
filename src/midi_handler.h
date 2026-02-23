/**
 * midi_handler.h - USB MIDI Input Handler
 * 
 * Handles MIDI CC messages for motor control:
 * - 3-byte MIDI message parsing
 * - State machine for message assembly
 * - CC to motor angle mapping
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
 * Process complete MIDI CC message
 * Maps CC# to motor target angle
 * @param status MIDI status byte (0xBn)
 * @param cc_number CC number (0-127)
 * @param cc_value CC value (0-127)
 */
void process_midi_message(uint8_t status, 
                          uint8_t cc_number, 
                          uint8_t cc_value);

#endif // MIDI_HANDLER_H
