#include <Arduino.h>
#if defined(USE_TINYUSB)
#include "Adafruit_TinyUSB.h"

// ============================================================================
// USB DEVICE INTERFACES
// ============================================================================
// HID device (USB joystick)
Adafruit_USBD_HID usb_hid;
// Native USB MIDI device
Adafruit_USBD_MIDI usb_midi;
#endif
void setup() {
  Serial.begin(115200);
}

void loop() {
}