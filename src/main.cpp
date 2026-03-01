/**
 * main.cpp — USB HID Trim Wheel Controller
 *
 * Single BLDC motor (7pp) + AS5600 sensor, SimpleFOC angle mode.
 * Haptic overlay provides configurable detents and endstops.
 *
 * Input:  USB MIDI CC, Serial Commander
 * Output: USB HID joystick (TinyUSB)
 * Tuning: SimpleFOC Commander (SimpleFOC Studio)
 */

#include <Arduino.h>
#include <SimpleFOC.h>
#include <stdio.h>
#include "config.h"
#include "motor_control.h"
#include "input/midi_handler.h"
#include "output/usb_hid.h"
#include "input/commander_integration.h"
#include "output/telemetry.h"
#include "profile_manager.h"
#include "haptic_layer.h"

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

  if (haptic_get_config().enabled) {
    axis_values[0] = haptic_get_hid_value();
  } else {
    axis_values[0] = angle_to_joystick_value();
  }
  // Apply axis reversal from active profile
  if (get_active_control_profile()->reversed) {
    axis_values[0] = 1023 - axis_values[0];
  }
  axis_values[1] = 512;  // Y-axis placeholder (single-motor system)
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
  const ControlProfile* p = get_active_control_profile();
  Serial.println("\n=== Loaded Configuration ===");
  Serial.print("Profile #");
  Serial.print(get_active_profile());
  Serial.print(": ");
  Serial.println(p->name);
  Serial.print("  MIDI CC#");
  Serial.print(p->midi_cc);
  Serial.print(", ");
  Serial.print(p->detent_count);
  Serial.print(" detents, ");
  Serial.print(p->range_deg);
  Serial.println("° range");
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
  
  Serial.println("\n=== USB HID Trim Wheel Controller ===");
  Serial.println("USB: CDC /dev/ttyACM0 (115200)");
  Serial.println("     Native MIDI port");
  Serial.println("     HID Joystick (8btn + 2axis)");
  
  // NOW initialize motor (after USB is fully ready)
  Serial.println("Initializing motor...");
  init_motor();
  Serial.println("Motor ready");
  
  // Initialize MIDI handler
  init_midi_handler();
  
  // Initialize Commander (for CI testing and tuning)
  init_commander();
  
  init_telemetry();

  // Initialize haptic layer (runtime enable/disable via WE0/WE1)
  haptic_init();
  
  // Print configuration
  print_configuration();
}

// ============================================================================
// MAIN LOOP
// ============================================================================

void loop() {
  
  // 1. FOC control (~1kHz)
  update_motor();

  // 2. Feed telemetry ring buffer (every FOC tick)
  telemetry_update(target_angle, current_angle);

  // 3. Haptic: observe actual → snap to detent → set target
  haptic_update();

  // 4. MIDI input (bounded burst handling)
  service_midi_input();

  // 5. Commander input (CI testing, tuning)
  update_commander();

  // 6. USB outputs (scheduled)
  unsigned long now_ms = millis();
  service_hid_output(now_ms);
  telemetry_output(now_ms);
}
