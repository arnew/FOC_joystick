/**
 * USB HID Joystick Controller with MIDI Profiles
 * 
 * Dual-motor SimpleFOC controller for Flight Simulator
 * - Motor 0: Throttle, Flaps, Spoilers (0-180°)
 * - Motor 1: Landing Gear, Trim (0-180°, endless trim)
 * 
 * Input: USB MIDI CC messages
 * Output: USB HID joystick (TinyUSB)
 * Tuning: SimpleFOC Commander (SimpleFOC Studio)
 * 
 * Modular Architecture:
 * - motor_control: SimpleFOC integration & FOC loops
 * - midi_handler: USB MIDI CC parsing
 * - usb_hid: HID joystick output
 * - commander_integration: SimpleFOC Studio tuning
 */

#include <Arduino.h>
#include <SimpleFOC.h>
#include "config.h"
#include "motor_control.h"
#include "midi_handler.h"
#include "usb_hid.h"

// Magic bootloader reentry address for RP2040
// When the host does a 1200bps reset (DTR toggle), this code detects it
// and reboots to the bootloader without requiring manual BOOTSEL press

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Initialize USB/Serial FIRST (before motor init) for bootloader reentry
  setup_usb_hid();
  Serial.begin(115200);
  usb_midi.begin();
  
  // Wait for CDC interface to register (enables DTR callback)
  delay(500);
  
  Serial.println("\n=== USB HID Joystick Controller ===");
  Serial.println("USB: CDC /dev/ttyACM0 (115200)");
  Serial.println("     Native MIDI port");
  Serial.println("     HID Joystick (8btn + 2axis)");
  
  // NOW initialize motor (after USB is fully ready)
  Serial.println("Initializing Motor 0...");
  init_motor(0);
  Serial.println("Motor 0 ready");
  
  // Initialize MIDI handler
  init_midi_handler();
  
  // Print configuration
  Serial.println("\n=== Loaded Configuration ===");
  Serial.print("Axes: ");
  Serial.println(NUM_A320_AXES);
  
  for (uint8_t i = 0; i < NUM_A320_AXES; i++) {
    Serial.print("  ");
    Serial.print(i);
    Serial.print(": ");
    Serial.print(A320_CONFIG[i].label);
    Serial.print(" (M");
    Serial.print(A320_CONFIG[i].motor_id);
    Serial.print(", CC#");
    Serial.print(A320_CONFIG[i].midi_cc);
    Serial.println(")");
  }
  
  Serial.println("\n=== Ready ===");
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  // 1. FOC control (~1kHz)
  update_motor(0);
  
  // 2. MIDI input (async USB)
  while (usb_midi.available()) {
    handle_midi_byte(usb_midi.read());
  }
  
  // 4. USB HID output (~100Hz)
  static unsigned long last_hid = 0;
  unsigned long now = millis();
  
  if (now - last_hid >= 10) {
    axis_values[0] = angle_to_joystick_value(0);
    axis_values[1] = angle_to_joystick_value(1);
    
    send_hid_report();
    last_hid = now;
  }
  
  // 5. Debug output (~100Hz)
  static unsigned long last_debug = 0;
  
  if (now - last_debug >= 10) {
    Serial.print("A=");
    Serial.print(get_motor_angle(0), 2);
    Serial.print(" T=");
    Serial.println(target_angle[0], 2);
    
    last_debug = now;
  }
}
