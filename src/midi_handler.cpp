/**
 * midi_handler.cpp - USB MIDI Input Implementation
 */

#include "midi_handler.h"
#include "motor_control.h"
#include "haptic_layer.h"
#include "config.h"
#include "profile_manager.h"
#include "statistics.h"

// ============================================================================
// MIDI PROFILE CONTROL
// ============================================================================
// CC#121 = Profile Select (0=A320, 1=Cessna, 2=Glider)
#define MIDI_CC_PROFILE_SELECT 121

// ============================================================================
// MIDI PARSER STATE
// ============================================================================

#define MIDI_BUFFER_SIZE 3
static uint8_t midi_buffer[MIDI_BUFFER_SIZE];
static uint8_t midi_buffer_index = 0;

// ============================================================================
// MIDI INITIALIZATION
// ============================================================================

void init_midi_handler() {
  midi_buffer_index = 0;
  memset(midi_buffer, 0, MIDI_BUFFER_SIZE);
}

// ============================================================================
// MIDI MESSAGE PARSING
// ============================================================================

void handle_midi_byte(uint8_t byte) {
  record_midi_byte();
  
  if (midi_buffer_index == 0) {
    // First byte: channel message
    // 0xB0-0xBF = Control Change
    if ((byte & 0xF0) == 0xB0) {
      midi_buffer[0] = byte;
      midi_buffer_index = 1;
    }
    return;
  }
  
  if (midi_buffer_index == 1) {
    // Second byte: CC number
    midi_buffer[1] = byte & 0x7F;
    midi_buffer_index = 2;
    return;
  }
  
  if (midi_buffer_index == 2) {
    // Third byte: CC value
    midi_buffer[2] = byte & 0x7F;
    midi_buffer_index = 0;
    
    // Process complete message
    record_midi_message();
    process_midi_message(
      midi_buffer[0], 
      midi_buffer[1], 
      midi_buffer[2]
    );
  }
}

void process_midi_message(uint8_t status, 
                          uint8_t cc_number, 
                          uint8_t cc_value) {
  // Verify CC message
  if ((status & 0xF0) != 0xB0) {
    return;
  }
  
  // Handle profile selection (MIDI CC#121)
  if (cc_number == MIDI_CC_PROFILE_SELECT) {
    uint8_t profile_id = cc_value % NUM_PROFILES;
    if (switch_to_profile(profile_id)) {
      Serial.print("[MIDI] Profile switched to: ");
      Serial.println(ALL_PROFILES[profile_id].name);
    }
    return;
  }
  
  // Find axis for this CC
  const AxisProfile* axis = 
    find_axis_by_cc(cc_number);
  if (!axis) {
    // Silently ignore unknown CC (not an error)
    return;
  }
  
  // Calculate target angle
  float target = cc_to_angle(axis, cc_value);
  
  // Route through haptic layer when enabled (snaps to nearest detent),
  // otherwise set motor target directly.
  if (haptic_get_config().enabled) {
    float target_deg = target * 180.0f / PI;
    haptic_set_position(target_deg);
  } else {
    set_motor_target(axis->motor_id, target);
  }
  
  // Debug output (commented to prevent USB CDC spam)
  // Rapid MIDI messages (e.g., trim wheel) can flood USB with 10-20 msgs/sec
  // Each message = 12 Serial.print() calls = 120-240 USB transactions/sec
  // Uncomment for debugging, but expect USB instability with continuous input
  /*
  Serial.print("MIDI: CC#");
  Serial.print(cc_number);
  Serial.print(" = ");
  Serial.print(cc_value);
  Serial.print(" → ");
  Serial.print(axis->label);
  Serial.print(" Motor");
  Serial.print(axis->motor_id);
  Serial.print(" angle: ");
  Serial.println(target, 4);
  */}