/**
 * usb_hid.h - USB HID Joystick Interface
 * 
 * Handles USB HID joystick output:
 * - HID descriptor setup
 * - Joystick report generation
 * - Angle to axis value conversion
 */

#ifndef USB_HID_H
#define USB_HID_H

#include <Arduino.h>
#include "Adafruit_TinyUSB.h"

// ============================================================================
// USB HID DEVICES
// ============================================================================

extern Adafruit_USBD_HID usb_hid;
extern Adafruit_USBD_MIDI usb_midi;

// ============================================================================
// HID JOYSTICK STATE
// ============================================================================

extern uint16_t axis_values[2];

// ============================================================================
// USB HID FUNCTIONS
// ============================================================================

/**
 * Initialize USB HID joystick
 * Sets up HID descriptor and TinyUSB
 */
void setup_usb_hid();

/**
 * Send USB HID joystick report
 * Only sends if values changed
 */
void send_hid_report();

/**
 * Convert motor angle to joystick value
 * @param motor_id Motor index (0 or 1)
 * @return USB joystick value (0-1023)
 */
uint16_t angle_to_joystick_value(
  uint8_t motor_id);

#endif // USB_HID_H
