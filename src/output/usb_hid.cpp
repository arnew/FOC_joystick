/**
 * usb_hid.cpp - USB HID Joystick Implementation
 */

#include "usb_hid.h"
#include "motor_control.h"
#include "config.h"
#include "profile_manager.h"

// ============================================================================
// USB DEVICE INTERFACES
// ============================================================================

Adafruit_USBD_HID usb_hid;
Adafruit_USBD_MIDI usb_midi;

// ============================================================================
// HID JOYSTICK STATE
// ============================================================================

uint16_t axis_values[2] = {32768, 32768};

// HID report structure
typedef struct {
  uint8_t buttons;
  uint16_t x;
  uint16_t y;
} __attribute__((packed)) 
hid_joystick_report_t;

static hid_joystick_report_t 
  current_report = {0, UINT16_MAX, UINT16_MAX};

// ============================================================================
// USB HID SETUP
// ============================================================================

void setup_usb_hid() {
  // HID report descriptor
  //
  // Joystick (0x04) instead of Game Pad (0x05): Linux kernel sets
  // flat=range/16 for gamepads but flat=0 for joysticks in many
  // versions.  Physical Min/Max matching Logical eliminates the
  // kernel's auto-calculated fuzz/flat entirely (signals a
  // precision device, not a noisy analog stick).
  static const uint8_t 
    hid_report_descriptor[] = {
    0x05, 0x01,       // Usage Page (Desktop)
    0x09, 0x04,       // Usage (Joystick)
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
    // Axes (X, Y) 16-bit, 0-65535
    // Physical Min/Max = Logical: tells kernel this is a
    // precision device — sets fuzz=0: flat=0 (no dead zone).
    0x05, 0x01,       //   Usage Page (Desktop)
    0x09, 0x30,       //   Usage (X)
    0x09, 0x31,       //   Usage (Y)
    0x16, 0x00, 0x00, //   Logical Min (0)
    0x26, 0xFF, 0xFF, //   Logical Max (65535)
    0x36, 0x00, 0x00, //   Physical Min (0)
    0x46, 0xFF, 0xFF, //   Physical Max (65535)
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
    }
  }
}

// ============================================================================
// ANGLE CONVERSION (fallback when haptic disabled)
// ============================================================================

uint16_t angle_to_joystick_value() {
  const ControlProfile* p = get_active_control_profile();
  float lo_deg = p->center_deg - p->range_deg / 2.0f;
  float hi_deg = p->center_deg + p->range_deg / 2.0f;
  static constexpr float DEG2RAD = 3.14159265f / 180.0f;
  float lo_rad = lo_deg * DEG2RAD;
  float hi_rad = hi_deg * DEG2RAD;

  float angle = get_motor_angle();
  float norm = (angle - lo_rad) / (hi_rad - lo_rad);
  norm = constrain(norm, 0.0f, 1.0f);
  return (uint16_t)(norm * 65535.0f);
}
