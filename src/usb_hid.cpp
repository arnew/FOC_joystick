/**
 * usb_hid.cpp - USB HID Joystick Implementation
 */

#include "usb_hid.h"
#include "motor_control.h"
#include "config.h"
#include "statistics.h"

// ============================================================================
// USB DEVICE INTERFACES
// ============================================================================

Adafruit_USBD_HID usb_hid;
Adafruit_USBD_MIDI usb_midi;

// ============================================================================
// HID JOYSTICK STATE
// ============================================================================

uint16_t axis_values[2] = {512, 512};

// HID report structure
typedef struct {
  uint8_t buttons;
  uint16_t x;
  uint16_t y;
} __attribute__((packed)) 
hid_joystick_report_t;

static hid_joystick_report_t 
  current_report = {0, 512, 512};

// ============================================================================
// USB HID SETUP
// ============================================================================

void setup_usb_hid() {
  // HID report descriptor
  static const uint8_t 
    hid_report_descriptor[] = {
    0x05, 0x01,       // Usage Page (Desktop)
    0x09, 0x05,       // Usage (Game Pad)
    0xA1, 0x01,       // Collection (Application)
    0x85, 0x01,       //   Report ID (1)
    // Buttons (8)
    0x05, 0x09,       //   Usage Page (Button)
    0x19, 0x01,       //   Usage Minimum (1)
    0x29, 0x08,       //   Usage Maximum (8)
    0x15, 0x00,       //   Logical Min (0)
    0x25, 0x01,       //   Logical Max (1)
    0x95, 0x08,       //   Report Count (8)
    0x75, 0x01,       //   Report Size (1)
    0x81, 0x02,       //   Input (Data,Var)
    // Axes (X, Y) 16-bit, 0-1023
    0x05, 0x01,       //   Usage Page (Desktop)
    0x09, 0x30,       //   Usage (X)
    0x09, 0x31,       //   Usage (Y)
    0x16, 0x00, 0x00, //   Logical Min (0)
    0x26, 0xFF, 0x03, //   Logical Max (1023)
    0x75, 0x10,       //   Report Size (16)
    0x95, 0x02,       //   Report Count (2)
    0x81, 0x02,       //   Input (Data,Var)
    0xC0              // End Collection
  };

  usb_hid.setReportDescriptor(
    hid_report_descriptor, 
    sizeof(hid_report_descriptor));
  usb_hid.begin();
}

// ============================================================================
// HID REPORT SENDING
// ============================================================================

void send_hid_report() {
  // Check if values changed
  if (axis_values[0] != current_report.x || 
      axis_values[1] != current_report.y) {
    
    current_report.x = axis_values[0];
    current_report.y = axis_values[1];

    if (usb_hid.ready()) {
      usb_hid.sendReport(
        1, 
        &current_report, 
        sizeof(current_report));
      record_hid_report();
    }
  }
}

// ============================================================================
// ANGLE CONVERSION
// ============================================================================

uint16_t angle_to_joystick_value(
  uint8_t motor_id) {
  
  if (motor_id >= 2) {
    return 512;  // Center
  }
  
  const MotorProfile* profile = 
    get_motor_profile(motor_id);
  if (!profile) {
    return 512;
  }
  
  float angle = get_motor_angle(motor_id);
  float normalized = 0.5f;
  
  // Normalize to 0.0-1.0
  if (profile->max_angle > 
      profile->min_angle) {
    normalized = 
      (angle - profile->min_angle) / 
      (profile->max_angle - 
       profile->min_angle);
  }
  
  // Apply axis reversal
  for (uint8_t i = 0; 
       i < NUM_ACTIVE_AXES; i++) {
    if (ACTIVE_CONFIG[i].motor_id == 
        motor_id) {
      if (ACTIVE_CONFIG[i].reversed) {
        normalized = 1.0f - normalized;
      }
      break;
    }
  }
  
  // Clamp and convert
  normalized = constrain(
    normalized, 0.0f, 1.0f);
  
  return (uint16_t)(normalized * 1023.0f);
}
