/**
 * profile_manager.cpp - Runtime Aircraft Profile Management
 */

#include "profile_manager.h"
#include <EEPROM.h>
#include "Adafruit_TinyUSB.h"

volatile ProfileType g_active_profile = PROFILE_A320;

static constexpr uint8_t PROFILE_STORE_MAGIC = 0xA5;
static constexpr uint8_t PROFILE_STORE_VERSION = 0x01;
static constexpr int EEPROM_SIZE_BYTES = 16;
static constexpr int EEPROM_ADDR_MAGIC = 0;
static constexpr int EEPROM_ADDR_VERSION = 1;
static constexpr int EEPROM_ADDR_PROFILE = 2;

static constexpr uint16_t PROFILE_USB_VID = 0xCAFE;
static constexpr uint16_t PROFILE_USB_PID_A320 = 0x3200;
static constexpr uint16_t PROFILE_USB_PID_CESSNA = 0x1720;
static constexpr uint16_t PROFILE_USB_PID_GLIDER = 0x7000;

struct UsbIdentity {
  uint16_t pid;
  const char* product;
};

static UsbIdentity get_usb_identity(ProfileType profile) {
  switch (profile) {
    case PROFILE_A320:
      return {PROFILE_USB_PID_A320, "FOC Joystick - A320"};
    case PROFILE_CESSNA:
      return {PROFILE_USB_PID_CESSNA, "FOC Joystick - Cessna"};
    case PROFILE_GLIDER:
      return {PROFILE_USB_PID_GLIDER, "FOC Joystick - Glider"};
    default:
      return {PROFILE_USB_PID_A320, "FOC Joystick - A320"};
  }
}

void set_active_profile(ProfileType profile) {
  if (profile < NUM_PROFILES) {
    g_active_profile = profile;
  }
}

ProfileType get_active_profile() {
  return g_active_profile;
}

static void reset_profile_store_defaults() {
  set_active_profile(PROFILE_A320);
  EEPROM.write(EEPROM_ADDR_MAGIC, PROFILE_STORE_MAGIC);
  EEPROM.write(EEPROM_ADDR_VERSION, PROFILE_STORE_VERSION);
  EEPROM.write(EEPROM_ADDR_PROFILE, (uint8_t)PROFILE_A320);
  EEPROM.commit();
}

bool save_active_profile() {
  EEPROM.write(EEPROM_ADDR_MAGIC, PROFILE_STORE_MAGIC);
  EEPROM.write(EEPROM_ADDR_VERSION, PROFILE_STORE_VERSION);
  EEPROM.write(EEPROM_ADDR_PROFILE, (uint8_t)get_active_profile());
  return EEPROM.commit();
}

void init_profile_manager() {
  EEPROM.begin(EEPROM_SIZE_BYTES);

  uint8_t magic = EEPROM.read(EEPROM_ADDR_MAGIC);
  uint8_t version = EEPROM.read(EEPROM_ADDR_VERSION);
  uint8_t stored_profile = EEPROM.read(EEPROM_ADDR_PROFILE);

  if (magic != PROFILE_STORE_MAGIC || version != PROFILE_STORE_VERSION ||
      stored_profile >= NUM_PROFILES) {
    reset_profile_store_defaults();
  } else {
    set_active_profile((ProfileType)stored_profile);
  }
}

void configure_usb_identity_from_profile() {
  UsbIdentity identity = get_usb_identity(get_active_profile());

  TinyUSBDevice.setID(PROFILE_USB_VID, identity.pid);
  TinyUSBDevice.setManufacturerDescriptor("FOC Joystick");
  TinyUSBDevice.setProductDescriptor(identity.product);
  TinyUSBDevice.setSerialDescriptor("FOC-TRIM-01");
}

void print_available_profiles() {
  Serial.println("\n[PROFILES] Available aircraft profiles:");
  for (uint8_t i = 0; i < NUM_PROFILES; i++) {
    Serial.print("  ");
    Serial.print(i);
    Serial.print(": ");
    Serial.println(ALL_PROFILES[i].name);
  }
}

void print_active_profile() {
  ProfileType active = get_active_profile();
  Serial.print("[PROFILES] Current: ");
  Serial.println(ALL_PROFILES[active].name);
}

bool switch_to_profile(uint8_t profile_id) {
  if (profile_id >= NUM_PROFILES) {
    return false;
  }

  ProfileType previous_profile = get_active_profile();
  if ((uint8_t)previous_profile == profile_id) {
    Serial.print("[PROFILES] Already active: ");
    Serial.println(ALL_PROFILES[profile_id].name);
    return true;
  }

  set_active_profile((ProfileType)profile_id);
  bool persisted = save_active_profile();

  Serial.print("[PROFILES] Switched to: ");
  Serial.println(ALL_PROFILES[profile_id].name);

  Serial.print("  Axes: ");
  Serial.println(ALL_PROFILES[profile_id].num_axes);

  if (persisted) {
    Serial.println("[PROFILES] Saved");
    Serial.println("[PROFILES] Rebooting now to apply USB identity...");
    Serial.flush();
    delay(100);
    rp2040.reboot();
  } else {
    Serial.println("[PROFILES] WARNING: save failed");
  }

  return true;
}
