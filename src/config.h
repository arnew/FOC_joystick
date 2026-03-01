#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ============================================================================
// DETENT POINT — one stop in a custom detent map
// ============================================================================
//
// position_pct: 0–100 within travel range.
// strength:     0.0 = waypoint (no snap), 1.0 = hard gate.

struct DetentPoint {
    float position_pct;
    float strength;
};

// ============================================================================
// CONTROL PROFILE
// ============================================================================
//
// Each profile defines one selectable control mode for the single-motor
// hardware.  Select at runtime via Commander 'A' or MIDI CC#121.
// Tweak haptic params live via Commander 'W' sub-commands.
//
// Detent modes (choose one):
//   Uniform clicks — detent_map==nullptr, detent_count>0
//     Evenly spaced, same strength.  Trim wheels.
//   Custom map     — detent_map!=nullptr
//     Arbitrary positions and per-detent strengths.
//   Smooth         — both null/zero.  Free rotation.
//
// Gate vs Click:
//   gate_mode false (default) — always snap to nearest detent.
//   gate_mode true            — snap only within gate_capture_deg of a
//                                detent; free proportional movement between
//                                gates.  A320 throttle IDLE→CLB zone.

struct ControlProfile {
    const char* name;
    uint8_t     midi_cc;
    bool        reversed;

    // Travel geometry
    float       range_deg;
    float       center_deg;
    float       endstop_margin;

    // Haptic detents (see modes above)
    uint16_t    detent_count;       // uniform click count (0 = smooth)
    float       detent_strength;    // uniform strength 0–1
    const DetentPoint* detent_map;  // custom array (nullptr = uniform)
    uint8_t     detent_map_size;
    bool        gate_mode;          // true = capture-zone gates
    float       gate_capture_deg;   // half-width of capture zone (degrees)

    // USB identity (applied on boot — profile change reboots)
    uint16_t    usb_pid;
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
// CUSTOM DETENT MAPS
// ============================================================================

// Cessna 172 flap lever: 5 positions (0°, 10°, 20°, 30°, 40°)
static const DetentPoint CESSNA_FLAPS_DETENTS[] = {
    {   0.0f, 1.0f },   // 0° retracted
    {  25.0f, 1.0f },   // 10°
    {  50.0f, 1.0f },   // 20°
    {  75.0f, 1.0f },   // 30°
    { 100.0f, 1.0f },   // 40° full
};

// Cessna gear: strong click at DOWN and UP
static const DetentPoint CESSNA_GEAR_DETENTS[] = {
    {   0.0f, 1.0f },   // DOWN
    { 100.0f, 1.0f },   // UP
};

// A320 thrust lever gates (gate_mode = true):
//   REV FULL → REV IDLE → IDLE → [autothrust zone] → CLB → FLX → TOGA
//   Between IDLE and CLB: free proportional movement (autothrust).
//   Between REV IDLE and REV FULL: free proportional reverse.
//   Positions approximate real A320 quadrant detent spacing.
//   ref: forums.flightsimulator.com/t/377566
static const DetentPoint A320_THROTTLE_DETENTS[] = {
    {   0.0f, 1.0f },   // REV FULL
    {  14.0f, 0.8f },   // REV IDLE
    {  28.0f, 1.0f },   // IDLE
    {  64.0f, 1.0f },   // CLB
    {  82.0f, 0.8f },   // FLX/MCT
    { 100.0f, 1.0f },   // TOGA
};

// A320 flap lever: 5 discrete positions
static const DetentPoint A320_FLAPS_DETENTS[] = {
    {   0.0f, 1.0f },   // 0 (UP)
    {  25.0f, 1.0f },   // 1
    {  50.0f, 1.0f },   // 2
    {  75.0f, 1.0f },   // 3
    { 100.0f, 1.0f },   // FULL
};

// A320 spoiler: major stops at 0/Half/Full, minor clicks between
static const DetentPoint A320_SPOILER_DETENTS[] = {
    {   0.0f, 1.0f },   // Retracted (major)
    {  25.0f, 0.3f },   // 1/4 (minor click)
    {  50.0f, 1.0f },   // 1/2 (major)
    {  75.0f, 0.3f },   // 3/4 (minor click)
    { 100.0f, 1.0f },   // Full (major)
};

// Glider spoiler: major stops at 0/Half/Full, minor clicks between
static const DetentPoint GLIDER_SPOILER_DETENTS[] = {
    {   0.0f, 1.0f },   // Retracted (major)
    {  25.0f, 0.3f },   // 1/4 (minor)
    {  50.0f, 1.0f },   // 1/2 (major)
    {  75.0f, 0.3f },   // 3/4 (minor)
    { 100.0f, 1.0f },   // Full (major)
};

// ============================================================================
// PROFILE TABLE
// ============================================================================
//
// Fields: name, cc, rev, range, center, margin,
//         det_count, det_str, det_map, map_sz, gate, gate_cap,
//         usb_pid, usb_product

static const ControlProfile ALL_PROFILES[NUM_PROFILES] = {
    // --- Cessna 172 ---
    { "Cessna Trim",       64, false, 180.0f, 90.0f, 2.0f,
      18, 1.0f, nullptr, 0, false, 0.0f,
      0x1701, "FOC - Cessna Trim" },

    { "Cessna Throttle",    7, false, 180.0f, 90.0f, 2.0f,
      0, 0.0f, nullptr, 0, false, 0.0f,
      0x1702, "FOC - Cessna Throttle" },

    { "Cessna Flaps",       5, false, 120.0f, 60.0f, 2.0f,
      0, 0.0f, CESSNA_FLAPS_DETENTS, 5, false, 0.0f,
      0x1703, "FOC - Cessna Flaps" },

    { "Cessna Gear",       35, false,  90.0f, 45.0f, 5.0f,
      0, 0.0f, CESSNA_GEAR_DETENTS, 2, false, 0.0f,
      0x1704, "FOC - Cessna Gear" },

    // --- Airbus A320 ---
    { "A320 Trim",         64, false, 180.0f, 90.0f, 2.0f,
      18, 1.0f, nullptr, 0, false, 0.0f,
      0x3201, "FOC - A320 Trim" },

    { "A320 Throttle",      7, false, 120.0f, 60.0f, 2.0f,
      0, 0.0f, A320_THROTTLE_DETENTS, 6, true, 5.0f,
      0x3202, "FOC - A320 Throttle" },

    { "A320 Flaps",        11, false, 100.0f, 50.0f, 2.0f,
      0, 0.0f, A320_FLAPS_DETENTS, 5, false, 0.0f,
      0x3203, "FOC - A320 Flaps" },

    { "A320 Spoilers",      2, false,  90.0f, 45.0f, 2.0f,
      0, 0.0f, A320_SPOILER_DETENTS, 5, false, 0.0f,
      0x3204, "FOC - A320 Spoilers" },

    // --- Glider ---
    { "Glider Trim",       64, false, 180.0f, 90.0f, 2.0f,
      18, 1.0f, nullptr, 0, false, 0.0f,
      0x7001, "FOC - Glider Trim" },

    { "Glider Spoiler",     2, false,  90.0f, 45.0f, 2.0f,
      0, 0.0f, GLIDER_SPOILER_DETENTS, 5, false, 0.0f,
      0x7002, "FOC - Glider Spoiler" },
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

