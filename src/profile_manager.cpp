/**
 * profile_manager.cpp — Runtime Control Profile Management
 */

#include "profile_manager.h"
#include "haptic_layer.h"
#include <EEPROM.h>
#include "Adafruit_TinyUSB.h"

volatile uint8_t g_active_profile = PROFILE_CESSNA_TRIM;

static constexpr uint8_t PROFILE_STORE_MAGIC   = 0xA5;
static constexpr uint8_t PROFILE_STORE_VERSION = 0x02;   // bumped — enum changed
static constexpr int EEPROM_SIZE_BYTES  = 16;
static constexpr int EEPROM_ADDR_MAGIC   = 0;
static constexpr int EEPROM_ADDR_VERSION = 1;
static constexpr int EEPROM_ADDR_PROFILE = 2;

static constexpr uint16_t PROFILE_USB_VID = 0xCAFE;

void set_active_profile(uint8_t profile) {
  if (profile < NUM_PROFILES) {
    g_active_profile = profile;
  }
}

uint8_t get_active_profile() {
  return g_active_profile;
}

static void reset_profile_store_defaults() {
  set_active_profile(PROFILE_CESSNA_TRIM);
  EEPROM.write(EEPROM_ADDR_MAGIC, PROFILE_STORE_MAGIC);
  EEPROM.write(EEPROM_ADDR_VERSION, PROFILE_STORE_VERSION);
  EEPROM.write(EEPROM_ADDR_PROFILE, PROFILE_CESSNA_TRIM);
  EEPROM.commit();
}

bool save_active_profile() {
  EEPROM.write(EEPROM_ADDR_MAGIC, PROFILE_STORE_MAGIC);
  EEPROM.write(EEPROM_ADDR_VERSION, PROFILE_STORE_VERSION);
  EEPROM.write(EEPROM_ADDR_PROFILE, get_active_profile());
  return EEPROM.commit();
}

void init_profile_manager() {
  EEPROM.begin(EEPROM_SIZE_BYTES);

  uint8_t magic   = EEPROM.read(EEPROM_ADDR_MAGIC);
  uint8_t version = EEPROM.read(EEPROM_ADDR_VERSION);
  uint8_t stored  = EEPROM.read(EEPROM_ADDR_PROFILE);

  if (magic != PROFILE_STORE_MAGIC || version != PROFILE_STORE_VERSION ||
      stored >= NUM_PROFILES) {
    reset_profile_store_defaults();
  } else {
    set_active_profile(stored);
  }
}

void configure_usb_identity_from_profile() {
  const ControlProfile* p = get_active_control_profile();
  TinyUSBDevice.setID(PROFILE_USB_VID, p->usb_pid);
  TinyUSBDevice.setManufacturerDescriptor("FOC Joystick");
  TinyUSBDevice.setProductDescriptor(p->usb_product);
  TinyUSBDevice.setSerialDescriptor("FOC-TRIM-01");
}

void print_available_profiles() {
  Serial.println("\n[PROFILE] Available control profiles:");
  for (uint8_t i = 0; i < NUM_PROFILES; i++) {
    Serial.print("  ");
    Serial.print(i);
    Serial.print(": ");
    Serial.print(ALL_PROFILES[i].name);
    Serial.print("  (CC#");
    Serial.print(ALL_PROFILES[i].midi_cc);
    Serial.print(", ");
    Serial.print(ALL_PROFILES[i].detent_count);
    Serial.println(" detents)");
  }
}

void print_active_profile() {
  const ControlProfile* p = get_active_control_profile();
  Serial.print("[PROFILE] Active: ");
  Serial.print(get_active_profile());
  Serial.print(" = ");
  Serial.println(p->name);
}

bool switch_to_profile(uint8_t profile_id) {
  if (profile_id >= NUM_PROFILES) {
    return false;
  }

  uint8_t prev = get_active_profile();
  if (prev == profile_id) {
    Serial.print("[PROFILE] Already active: ");
    Serial.println(ALL_PROFILES[profile_id].name);
    return true;
  }

  set_active_profile(profile_id);

  // Apply haptic config from the new profile immediately
  haptic_load_profile(profile_id);

  bool persisted = save_active_profile();

  Serial.print("[PROFILE] Switched to: ");
  Serial.println(ALL_PROFILES[profile_id].name);

  if (persisted) {
    Serial.println("[PROFILE] Saved. Rebooting for USB identity...");
    Serial.flush();
    delay(100);
    rp2040.reboot();
  } else {
    Serial.println("[PROFILE] WARNING: save failed, running without reboot");
  }

  return true;
}
