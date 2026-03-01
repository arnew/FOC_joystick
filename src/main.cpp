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
#include <stdio.h>
#include "config.h"
#include "motor_control.h"
#include "midi_handler.h"
#include "usb_hid.h"
#include "commander_integration.h"
#include "statistics.h"
#include "telemetry.h"
#include "profile_manager.h"
#include "haptic_layer.h"
#ifdef TRIM_WHEEL_PREVIEW
#include "trim_wheel_preview.h"
#endif

// ============================================================================
// I/O RATE SCHEDULING (USB CDC + MIDI + HID)
// ============================================================================

static constexpr uint16_t HID_UPDATE_INTERVAL_MS = 20;      // 50 Hz
// Debug output replaced by telemetry module (10Hz @T lines)
static constexpr uint16_t MIDI_MAX_BYTES_PER_LOOP = 24;     // 8 CC messages max
static constexpr uint32_t MIDI_BUDGET_US = 500;             // max MIDI time slice


static void service_midi_input() {
  uint32_t start_us = micros();
  uint16_t bytes_processed = 0;

  while (usb_midi.available()) {
    handle_midi_byte(usb_midi.read());
    bytes_processed++;

    if (bytes_processed >= MIDI_MAX_BYTES_PER_LOOP) {
      break;
    }
    if ((micros() - start_us) >= MIDI_BUDGET_US) {
      break;
    }
  }
}

static void service_hid_output(unsigned long now_ms) {
  static unsigned long last_hid_ms = 0;

  if ((now_ms - last_hid_ms) < HID_UPDATE_INTERVAL_MS) {
    return;
  }

  #ifdef TRIM_WHEEL_PREVIEW
  axis_values[0] = get_trim_wheel_hid_value();
  #else
  if (haptic_get_config().enabled) {
    axis_values[0] = haptic_get_hid_value();
  } else {
    axis_values[0] = angle_to_joystick_value(0);
  }
  #endif
  axis_values[1] = angle_to_joystick_value(1);
  send_hid_report();
  last_hid_ms = now_ms;
}

// Debug output replaced by telemetry_output() — see telemetry.h

// Magic bootloader reentry address for RP2040
// When the host does a 1200bps reset (DTR toggle), this code detects it
// and reboots to the bootloader without requiring manual BOOTSEL press

// ============================================================================
// SETUP HELPERS
// ============================================================================

static void print_configuration() {
  const ProfileMetadata* meta = get_profile_metadata();

  Serial.println("\n=== Loaded Configuration ===");
  Serial.print("Profile: ");
  Serial.println(meta->name);
  Serial.print("Axes: ");
  Serial.println(meta->num_axes);
  
  for (uint8_t i = 0; i < meta->num_axes; i++) {
    Serial.print("  ");
    Serial.print(i);
    Serial.print(": ");
    Serial.print(meta->config[i].label);
    Serial.print(" (M");
    Serial.print(meta->config[i].motor_id);
    Serial.print(", CC#");
    Serial.print(meta->config[i].midi_cc);
    Serial.println(")");
  }
  
  Serial.println("\n=== Ready ===");
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
  // Load persistent software-selected profile first.
  init_profile_manager();
  configure_usb_identity_from_profile();

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
  #ifdef TRIM_WHEEL_PREVIEW
  Serial.println("Mode: Cessna trim preview (click detents + end stops)");
  #endif
  
  // NOW initialize motor (after USB is fully ready)
  Serial.println("Initializing Motor 0...");
  init_motor(0);
  Serial.println("Motor 0 ready");
  
  // Initialize MIDI handler
  init_midi_handler();
  
  // Initialize Commander (for CI testing and tuning)
  init_commander();
  
  // Initialize statistics collection
  init_statistics();
  init_telemetry();

  #ifdef TRIM_WHEEL_PREVIEW
  init_trim_wheel_preview();
  #endif

  // Initialize haptic layer (runtime enable/disable via WE0/WE1)
  haptic_init();
  
  // Print configuration
  print_configuration();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  uint32_t loop_start = micros();
  
  // 1. FOC control (~1kHz)
  update_motor(0);

  // 2. Feed telemetry ring buffer (every FOC tick)
  telemetry_update(target_angle[0], current_angle[0]);

  #ifdef TRIM_WHEEL_PREVIEW
  update_trim_wheel_preview();
  #else
  haptic_update();
  #endif

  // 2. MIDI input (bounded burst handling)
  service_midi_input();
  
  // 3. Commander input (CI testing, tuning)
  update_commander();

  // 4. USB outputs (scheduled)
  unsigned long now_ms = millis();
  service_hid_output(now_ms);
  telemetry_output(now_ms);
  
  // 5. Update statistics
  update_statistics_uptime();
  record_loop_timing(micros() - loop_start);
}
