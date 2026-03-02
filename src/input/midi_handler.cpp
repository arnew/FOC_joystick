/**
 * midi_handler.cpp — USB MIDI Input
 *
 * CC matching:
 *   Active profile's midi_cc → position (0-127 → 0-100% of haptic range)
 *   CC#121               → profile select (value = profile index)
 */

#include "midi_handler.h"
#include "config.h"
#include "profile_manager.h"
#include "haptic_layer.h"

// ============================================================================
// MIDI PROFILE CONTROL
// ============================================================================
#define MIDI_CC_PROFILE_SELECT 121

// ============================================================================
// MIDI PARSER STATE
// ============================================================================

#define MIDI_BUFFER_SIZE 3
static uint8_t midi_buffer[MIDI_BUFFER_SIZE];
static uint8_t midi_buffer_index = 0;

// ============================================================================
// INITIALIZATION
// ============================================================================

void init_midi_handler() {
  midi_buffer_index = 0;
  memset(midi_buffer, 0, MIDI_BUFFER_SIZE);
}

// ============================================================================
// MIDI BYTE PARSER (3-byte CC state machine)
// ============================================================================

void handle_midi_byte(uint8_t byte) {
  if (midi_buffer_index == 0) {
    if ((byte & 0xF0) == 0xB0) {   // Control Change
      midi_buffer[0] = byte;
      midi_buffer_index = 1;
    }
    return;
  }
  if (midi_buffer_index == 1) {
    midi_buffer[1] = byte & 0x7F;
    midi_buffer_index = 2;
    return;
  }
  if (midi_buffer_index == 2) {
    midi_buffer[2] = byte & 0x7F;
    midi_buffer_index = 0;
    process_midi_message(midi_buffer[0], midi_buffer[1], midi_buffer[2]);
  }
}

// ============================================================================
// CC MESSAGE DISPATCH
// ============================================================================

void process_midi_message(uint8_t status,
                          uint8_t cc_number,
                          uint8_t cc_value) {
  if ((status & 0xF0) != 0xB0) return;

  // Profile selection: CC#121 value = profile index
  if (cc_number == MIDI_CC_PROFILE_SELECT) {
    if (cc_value < NUM_PROFILES) {
      switch_to_profile(cc_value);
    }
    return;
  }

  // Position control: only respond to active profile's CC
  const ControlProfile* p = get_active_control_profile();
  if (cc_number == p->midi_cc) {
    haptic_set_position_normalized((float)cc_value / 127.0f);
  }
  // All other CCs silently ignored
}