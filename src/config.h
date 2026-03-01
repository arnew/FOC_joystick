#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ============================================================================
// CONTROL PROFILE
// ============================================================================
//
// Each profile defines one selectable control mode for the single-motor
// hardware.  Includes haptic behavior, MIDI mapping, and USB identity.
//
// Select at runtime via Commander 'A' command or MIDI CC#121.
// Tweak haptic params live via Commander 'W' sub-commands.
//
// From README.md — representative controls per aircraft:
//   Cessna:  Trim(clicks), Throttle(smooth), Flaps(5 detents), Gear(2 detents)
//   A320:    Trim(clicks), Throttle(6 detents), Flaps(5), Spoilers(~5)
//   Glider:  Trim(clicks), Spoiler(3 detents)

struct ControlProfile {
  const char* name;           // Human-readable label
  uint8_t midi_cc;            // MIDI CC for position input (0-127 → 0-100%)
  bool reversed;              // Reverse HID output direction

  // Haptic parameters (loaded into HapticConfig on profile switch)
  float range_deg;            // Total angular travel (degrees)
  float center_deg;           // Center of travel (degrees)
  uint16_t detent_count;      // Detent stops (0 = smooth/continuous)
  float detent_strength;      // Snap force 0.0–1.0
  float endstop_margin;       // Soft endstop zone (degrees)

  // USB identity (applied on boot — profile change requires reboot)
  uint16_t usb_pid;
  const char* usb_product;
};

// ============================================================================
// PROFILE ENUMERATION
// ============================================================================

enum ProfileId : uint8_t {
  PROFILE_CESSNA_TRIM = 0,
  PROFILE_CESSNA_THROTTLE,
  PROFILE_CESSNA_FLAPS,
  PROFILE_CESSNA_GEAR,
  PROFILE_A320_TRIM,
  PROFILE_A320_THROTTLE,
  PROFILE_A320_FLAPS,
  PROFILE_A320_SPOILERS,
  PROFILE_GLIDER_TRIM,
  PROFILE_GLIDER_SPOILER,
  NUM_PROFILES
};

// ============================================================================
// PROFILE TABLE
// ============================================================================

static const ControlProfile ALL_PROFILES[NUM_PROFILES] = {
  //              name                cc  rev   range  center det  str  margin  pid     usb_product
  // --- Cessna 172 ---
  { "Cessna Trim",       64, false,  180.0f,  90.0f, 18, 1.0f, 2.0f,  0x1701, "FOC - Cessna Trim"     },
  { "Cessna Throttle",    7, false,  180.0f,  90.0f,  0, 0.0f, 2.0f,  0x1702, "FOC - Cessna Throttle" },
  { "Cessna Flaps",       5, false,  120.0f,  60.0f,  4, 1.0f, 2.0f,  0x1703, "FOC - Cessna Flaps"    },
  { "Cessna Gear",       35, false,   90.0f,  45.0f,  1, 1.0f, 5.0f,  0x1704, "FOC - Cessna Gear"     },
  // --- Airbus A320 ---
  { "A320 Trim",         64, false,  180.0f,  90.0f, 18, 1.0f, 2.0f,  0x3201, "FOC - A320 Trim"       },
  { "A320 Throttle",      7, false,  120.0f,  60.0f,  5, 1.0f, 2.0f,  0x3202, "FOC - A320 Throttle"   },
  { "A320 Flaps",        11, false,  100.0f,  50.0f,  4, 1.0f, 2.0f,  0x3203, "FOC - A320 Flaps"      },
  { "A320 Spoilers",      2, false,   90.0f,  45.0f,  5, 1.0f, 2.0f,  0x3204, "FOC - A320 Spoilers"   },
  // --- Glider ---
  { "Glider Trim",       64, false,  180.0f,  90.0f, 18, 1.0f, 2.0f,  0x7001, "FOC - Glider Trim"     },
  { "Glider Spoiler",     2, false,   90.0f,  45.0f,  2, 1.0f, 2.0f,  0x7002, "FOC - Glider Spoiler"  },
};

// ============================================================================
// RUNTIME STATE
// ============================================================================

extern volatile uint8_t g_active_profile;

void set_active_profile(uint8_t profile);
uint8_t get_active_profile();

/**
 * Get active control profile (read-only).
 */
static inline const ControlProfile* get_active_control_profile() {
  if (g_active_profile < NUM_PROFILES)
    return &ALL_PROFILES[g_active_profile];
  return &ALL_PROFILES[0];
}

#endif  // CONFIG_H

