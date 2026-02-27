/*
 * Minimal TinyUSB HID-only (no MIDI yet)
 * Testing bootloader reentry mechanism
 */

#include <Arduino.h>
#include <Adafruit_TinyUSB.h>

// HID report descriptor: single gamepad
uint8_t const desc_hid_report[] = {
    TUD_HID_REPORT_DESC_GAMEPAD()
};

// USB HID object for gamepad
Adafruit_USBD_HID usb_hid;

// Current joystick state
hid_gamepad_report_t gamepad_state = {};

void setup() {
  // Manual begin() required on RP2040
  if (!TinyUSBDevice.isInitialized()) {
    TinyUSBDevice.begin(0);
  }

  Serial.begin(115200);
  delay(100); // Wait for Serial to stabilize

  Serial.println("\n=== Minimal TinyUSB HID-Only ===");

  // Setup HID gamepad
  usb_hid.setPollInterval(2);
  usb_hid.setReportDescriptor(desc_hid_report, sizeof(desc_hid_report));
  usb_hid.begin();

  // Re-enumerate if already mounted
  if (TinyUSBDevice.mounted()) {
    Serial.println("Device already mounted, re-enumerating...");
    TinyUSBDevice.detach();
    delay(10);
    TinyUSBDevice.attach();
  }

  // Initialize gamepad state
  gamepad_state.x = 0;
  gamepad_state.y = 0;
  gamepad_state.z = 0;
  gamepad_state.rz = 0;
  gamepad_state.rx = 0;
  gamepad_state.ry = 0;
  gamepad_state.hat = 0;
  gamepad_state.buttons = 0;

  Serial.println("Setup complete. Waiting for USB mount...");
}

void loop() {
  // Manual USB task (required on RP2040)
  #ifdef TINYUSB_NEED_POLLING_TASK
  TinyUSBDevice.task();
  #endif

  // Not mounted yet
  if (!TinyUSBDevice.mounted()) {
    return;
  }

  // Test pattern: oscillate axes
  static uint32_t test_counter = 0;
  test_counter++;
  
  // Sine wave on X axis (X = 127 * sin(2π * counter / 256))
  gamepad_state.x = (int16_t)(127 * sin(2 * 3.14159 * (test_counter % 256) / 256));
  gamepad_state.y = (int16_t)(127 * cos(2 * 3.14159 * (test_counter % 256) / 256));
  gamepad_state.buttons = (test_counter / 512) & 0xFF;  // Cycle through button states

  // Send gamepad report at ~50Hz
  static uint32_t last_report_ms = 0;
  if (millis() - last_report_ms >= 20) {
    last_report_ms = millis();

    if (usb_hid.ready()) {
      usb_hid.sendReport(0, &gamepad_state, sizeof(gamepad_state));
    }
  }

  // Status indicator every 2 seconds
  static uint32_t last_status_ms = 0;
  if (millis() - last_status_ms >= 2000) {
    last_status_ms = millis();
    Serial.print("Status: X=");
    Serial.print(gamepad_state.x);
    Serial.print(" Y=");
    Serial.print(gamepad_state.y);
    Serial.print(" Buttons=");
    Serial.println(gamepad_state.buttons, HEX);
  }
}
