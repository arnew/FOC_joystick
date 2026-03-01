/**
 * haptic_layer.cpp — Configurable haptic overlay for motor control
 *
 * Architecture (v2 — observe/snap/set):
 *   Motor control owns a target angle and reports the actual angle.
 *   Haptic layer observes actual → clamps to range → snaps to nearest
 *   detent → sets the motor target.  No delta accumulation, no tracking.
 *   The motor IS the state.
 *
 * Commander 'W' sub-commands:
 *   W        — Show current config
 *   WE0/WE1  — Disable/enable haptic layer
 *   WR180.0  — Set range (degrees)
 *   WC90.0   — Set center position (degrees)
 *   WN18     — Set detent count
 *   WS0.5    — Set detent strength (0.0–1.0)
 *   WM5.0    — Set endstop margin (degrees)
 */

#include "haptic_layer.h"
#include "motor_control.h"
#include <math.h>

// ============================================================================
// STATE   (minimal — the motor is the real state)
// ============================================================================

static HapticConfig config;
static float snapped_deg = 0.0f;       // Current detent-snapped target
static int16_t current_detent = 0;

static constexpr float DEG2RAD = PI / 180.0f;
static constexpr float RAD2DEG = 180.0f / PI;

// Diagnostic telemetry (print every DIAG_INTERVAL_MS)
static constexpr unsigned long DIAG_INTERVAL_MS = 100;
static unsigned long last_diag_ms = 0;

// ============================================================================
// HELPERS
// ============================================================================

static float min_angle_deg() {
    return config.center_deg - config.range_deg / 2.0f;
}

static float max_angle_deg() {
    return config.center_deg + config.range_deg / 2.0f;
}

static float detent_step_deg() {
    if (config.detent_count == 0) return 0.0f;
    return config.range_deg / (float)config.detent_count;
}

/** Snap an angle to the nearest detent. Returns the detent index. */
static int16_t snap_to_detent(float angle_deg, float& snapped_out) {
    if (config.detent_count == 0) {
        snapped_out = angle_deg;
        return -1;
    }
    float lo = min_angle_deg();
    float step = detent_step_deg();
    float idx_f = (angle_deg - lo) / step;
    int16_t idx = (int16_t)roundf(idx_f);
    if (idx < 0) idx = 0;
    if (idx > (int16_t)config.detent_count) idx = config.detent_count;
    snapped_out = lo + (float)idx * step;
    return idx;
}

// ============================================================================
// PUBLIC API
// ============================================================================

void haptic_init() {
    config.range_deg = 180.0f;
    config.center_deg = 90.0f;
    config.detent_count = 18;
    config.detent_strength = 1.0f;
    config.endstop_margin = 2.0f;
    config.enabled = true;
}

void haptic_update() {
    if (!config.enabled) return;

    // 1. Observe actual motor position
    float actual_rad = get_motor_angle(0);
    float actual_deg = actual_rad * RAD2DEG;
    
    // 3. Snap to nearest detent 
    float new_snap = 0.0f;
    int16_t new_detent = snap_to_detent(actual_deg, new_snap);

    target_deg = new_snap;


    // 5. Diagnostic telemetry
    unsigned long now = millis();
    if ((now - last_diag_ms) >= DIAG_INTERVAL_MS) {
        last_diag_ms = now;
        float vel = get_motor_velocity(0) * RAD2DEG;
        Serial.print("HAPTIC_DIAG motor=");
        Serial.print(actual_deg, 1);
        Serial.print(" clamped=");
        Serial.print(clamped_deg, 1);
        Serial.print(" snap=");
        Serial.print(new_snap, 1);
        Serial.print(" det=");
        Serial.print(new_detent);
        Serial.print(" vel=");
        Serial.println(vel, 1);
    }

        set_motor_target(0, target_deg * DEG2RAD);
}

    snapped_deg = new_snap;
    current_detent = new_detent;
}

const HapticConfig& haptic_get_config() {
    return config;
}

void haptic_set_config(const HapticConfig& cfg) {
    config = cfg;
}

int16_t haptic_get_detent_index() {
    if (!config.enabled || config.detent_count == 0) return -1;
    return current_detent;
}

float haptic_get_target_deg() {
    return snapped_deg;
}

float haptic_get_raw_deg() {
    return snapped_deg;  // No separate "raw" in v2 — motor is the state
}

uint16_t haptic_get_hid_value() {
    if (config.detent_count == 0) {
        // Continuous: map range linearly to 0–1023
        float lo = min_angle_deg();
        float hi = max_angle_deg();
        float frac = (snapped_deg - lo) / (hi - lo);
        frac = constrain(frac, 0.0f, 1.0f);
        return (uint16_t)(frac * 1023.0f);
    }
    // Discrete: map detent index
    float frac = (float)current_detent / (float)config.detent_count;
    return (uint16_t)(frac * 1023.0f);
}

void haptic_set_position(float angle_deg) {
    if (!config.enabled) return;
    float lo = min_angle_deg();
    float hi = max_angle_deg();
    float clamped = constrain(angle_deg, lo, hi);
    current_detent = snap_to_detent(clamped, snapped_deg);
    set_motor_target(0, snapped_deg * DEG2RAD);
}

// ============================================================================
// COMMANDER INTERFACE
// ============================================================================

static void print_config() {
    Serial.println("[HAPTIC] Current config:");
    Serial.print("  enabled:    "); Serial.println(config.enabled ? "YES" : "NO");
    Serial.print("  range_deg:  "); Serial.println(config.range_deg);
    Serial.print("  center_deg: "); Serial.println(config.center_deg);
    Serial.print("  detents:    "); Serial.println(config.detent_count);
    Serial.print("  strength:   "); Serial.println(config.detent_strength, 2);
    Serial.print("  endstop_margin: "); Serial.println(config.endstop_margin);
    Serial.print("  detent_step: "); Serial.print(detent_step_deg()); Serial.println("°");
    Serial.print("  range:      "); Serial.print(min_angle_deg());
    Serial.print("° .. "); Serial.print(max_angle_deg()); Serial.println("°");
    Serial.print("  current:    detent="); Serial.print(current_detent);
    Serial.print("  snap="); Serial.print(snapped_deg); Serial.println("°");
    Serial.print("  hid_value:  "); Serial.println(haptic_get_hid_value());
}

void haptic_cmd(char* cmd) {
    // Commander may pass whitespace / newline remnants for bare "W"
    if (!cmd || !cmd[0] || cmd[0] == ' ' || cmd[0] == '\r' || cmd[0] == '\n') {
        print_config();
        return;
    }

    char sub = cmd[0];
    const char* arg = cmd + 1;

    switch (sub) {
        case 'E':  // Enable/disable
            config.enabled = (atoi(arg) != 0);
            Serial.print("[HAPTIC] enabled=");
            Serial.println(config.enabled ? "YES" : "NO");
            break;

        case 'R':  // Range
            config.range_deg = atof(arg);
            Serial.print("[HAPTIC] range=");
            Serial.print(config.range_deg);
            Serial.println("°");
            break;

        case 'C':  // Center
            config.center_deg = atof(arg);
            Serial.print("[HAPTIC] center=");
            Serial.print(config.center_deg);
            Serial.println("°");
            break;

        case 'N':  // Detent count
            config.detent_count = (uint16_t)atoi(arg);
            Serial.print("[HAPTIC] detents=");
            Serial.println(config.detent_count);
            break;

        case 'S':  // Strength
            config.detent_strength = atof(arg);
            config.detent_strength = constrain(config.detent_strength, 0.0f, 1.0f);
            Serial.print("[HAPTIC] strength=");
            Serial.println(config.detent_strength, 2);
            break;

        case 'M':  // Margin
            config.endstop_margin = atof(arg);
            Serial.print("[HAPTIC] endstop_margin=");
            Serial.print(config.endstop_margin);
            Serial.println("°");
            break;

        default:
            Serial.println("[HAPTIC] Unknown sub-command. Use:");
            Serial.println("  W       — show config");
            Serial.println("  WE0/WE1 — disable/enable");
            Serial.println("  WR180   — range (degrees)");
            Serial.println("  WC90    — center position");
            Serial.println("  WN18    — detent count");
            Serial.println("  WS0.5   — detent strength");
            Serial.println("  WM5.0   — endstop margin");
            break;
    }
}
