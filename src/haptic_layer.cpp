/**
 * haptic_layer.cpp — Configurable haptic overlay for motor control
 *
 * Detent detection uses a stateless, position-based algorithm:
 *   1. Read motor angle, clamp to configured range
 *   2. Compare clamped position to current detent via hysteresis threshold
 *   3. Transition one detent when user pushes past 60% of detent spacing
 *   4. After each transition, resync until motor reaches new target
 *
 * Endstop behaviour is implicit: constrain() before the detent check
 * makes motor overshoot past the range boundary invisible to the
 * detent logic.  No accumulator → no drift → no walkaway.
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
// STATE
// ============================================================================

static HapticConfig config;
static float raw_angle_deg = 0.0f;     // Unclamped motor angle (diagnostic)
static float snapped_deg = 0.0f;       // Current detent-snapped target
static int16_t current_detent = 0;
static bool first_tick = true;
static bool resync_pending = false;     // Wait for motor to reach target
static unsigned long resync_start_ms = 0;  // Timeout guard

static constexpr float DEG2RAD = PI / 180.0f;
static constexpr float RAD2DEG = 180.0f / PI;
static constexpr unsigned long RESYNC_TIMEOUT_MS = 1000;

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

/** Shortest angular delta (handles wrapping). */
static float angular_delta_rad(float from_rad, float to_rad) {
    float d = to_rad - from_rad;
    while (d > PI) d -= 2.0f * PI;
    while (d < -PI) d += 2.0f * PI;
    return d;
}

// ============================================================================
// PUBLIC API
// ============================================================================

void haptic_init() {
    // Sensible defaults for a trim wheel demo:
    // 180° throw, 18 detents (10° each), centred at 90°
    config.range_deg = 180.0f;
    config.center_deg = 90.0f;
    config.detent_count = 18;
    config.detent_strength = 1.0f;
    config.endstop_margin = 2.0f;
    config.enabled = true;

    first_tick = true;
    resync_pending = false;
    resync_start_ms = 0;
}

void haptic_update() {
    if (!config.enabled) return;

    float motor_rad = get_motor_angle(0);
    float motor_deg = motor_rad * RAD2DEG;
    float lo = min_angle_deg();
    float hi = max_angle_deg();

    raw_angle_deg = motor_deg;  // diagnostic: unclamped motor position

    // ---- First tick: snap to nearest detent from current position ----
    if (first_tick) {
        // Clamp to range even on first tick for sane initialization
        float effective = constrain(motor_deg, lo, hi);
        current_detent = snap_to_detent(effective, snapped_deg);
        set_motor_target(0, snapped_deg * DEG2RAD);
        first_tick = false;
        resync_pending = true;
        resync_start_ms = millis();
        return;
    }

    // ---- Guard: extreme overshoot past endstop (wrap protection) ----
    // On an endless motor, pushing a full revolution past the endstop
    // can cause sensor-wrap tracking glitches in the AS5600.  If the
    // motor reads more than guard_deg past the range boundary, freeze
    // haptic state until the motor returns to near-range.
    {
        float guard_deg = fmaxf(
            config.detent_count > 0 ? detent_step_deg() * 2.0f : 30.0f,
            30.0f);
        if (motor_deg > hi + guard_deg || motor_deg < lo - guard_deg) {
            return;  // hold current target, don't touch detent state
        }
    }

    // ---- Resync: wait for motor to approach target before monitoring ----
    if (resync_pending) {
        float effective = constrain(motor_deg, lo, hi);
        float err = fabsf(effective - snapped_deg);
        float threshold = (config.detent_count > 0)
                        ? detent_step_deg() * 0.3f  // 30% of step
                        : 2.0f;                      // 2° for free rotation
        if (err < threshold || (millis() - resync_start_ms) > RESYNC_TIMEOUT_MS) {
            resync_pending = false;
            resync_start_ms = 0;
        }
        return;
    }

    // ---- Clamp motor position to valid range ----
    // Endstop behaviour is implicit: motor overshoot past the range
    // boundary is invisible to the detent logic after constrain().
    float effective = constrain(motor_deg, lo, hi);

    // ---- Detent transition via hysteresis ----
    if (config.detent_count > 0) {
        float step = detent_step_deg();
        float threshold = step * 0.6f;  // 60% of step spacing
        float deviation = effective - snapped_deg;

        if (deviation > threshold && current_detent < (int16_t)config.detent_count) {
            current_detent++;
            snapped_deg = lo + (float)current_detent * step;
            set_motor_target(0, snapped_deg * DEG2RAD);
            resync_pending = true;
            resync_start_ms = millis();
        } else if (deviation < -threshold && current_detent > 0) {
            current_detent--;
            snapped_deg = lo + (float)current_detent * step;
            set_motor_target(0, snapped_deg * DEG2RAD);
            resync_pending = true;
            resync_start_ms = millis();
        } else if (config.detent_strength < 1.0f) {
            // Partial strength: blend target between detent and user position
            float target_deg;
            if (config.detent_strength <= 0.0f) {
                target_deg = effective;
            } else {
                target_deg = effective
                           + config.detent_strength * (snapped_deg - effective);
            }
            float current_target_deg = get_motor_target(0) * RAD2DEG;
            if (fabsf(target_deg - current_target_deg) > 0.05f) {
                set_motor_target(0, target_deg * DEG2RAD);
            }
        }
    } else {
        // Free rotation (no detents): follow clamped motor position
        snapped_deg = effective;
        float current_target_deg = get_motor_target(0) * RAD2DEG;
        if (fabsf(effective - current_target_deg) > 0.05f) {
            set_motor_target(0, effective * DEG2RAD);
        }
    }
}

const HapticConfig& haptic_get_config() {
    return config;
}

void haptic_set_config(const HapticConfig& cfg) {
    config = cfg;
    first_tick = true;
    resync_pending = false;
    resync_start_ms = 0;
}

int16_t haptic_get_detent_index() {
    if (!config.enabled || config.detent_count == 0) return -1;
    return current_detent;
}

float haptic_get_target_deg() {
    return snapped_deg;
}

float haptic_get_raw_deg() {
    return raw_angle_deg;
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
    angle_deg = constrain(angle_deg, lo, hi);
    current_detent = snap_to_detent(angle_deg, snapped_deg);
    set_motor_target(0, snapped_deg * DEG2RAD);
    resync_pending = true;
    resync_start_ms = millis();
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
    Serial.print("  target="); Serial.print(snapped_deg);
    Serial.print("°  raw="); Serial.print(raw_angle_deg); Serial.println("°");
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
            first_tick = true;
            Serial.print("[HAPTIC] enabled=");
            Serial.println(config.enabled ? "YES" : "NO");
            break;

        case 'R':  // Range
            config.range_deg = atof(arg);
            first_tick = true;
            Serial.print("[HAPTIC] range=");
            Serial.print(config.range_deg);
            Serial.println("°");
            break;

        case 'C':  // Center
            config.center_deg = atof(arg);
            first_tick = true;
            Serial.print("[HAPTIC] center=");
            Serial.print(config.center_deg);
            Serial.println("°");
            break;

        case 'N':  // Detent count
            config.detent_count = (uint16_t)atoi(arg);
            first_tick = true;
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
