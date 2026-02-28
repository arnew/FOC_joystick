/**
 * trim_wheel_preview.h - Cessna-style Trim Wheel Preview Mode
 *
 * Provides a local haptic trim wheel behavior for joystick testing:
 * - Click detents
 * - Top and bottom end stops
 * - HID axis value generation without external MIDI input
 */

#ifndef TRIM_WHEEL_PREVIEW_H
#define TRIM_WHEEL_PREVIEW_H

#include <Arduino.h>

void init_trim_wheel_preview();
void update_trim_wheel_preview();
uint16_t get_trim_wheel_hid_value();

#endif // TRIM_WHEEL_PREVIEW_H
