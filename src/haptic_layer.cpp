/**
 * haptic_layer.cpp — Configurable haptic overlay for motor control
 *
 * Reads motor angle, applies detent snapping + end-stop clamping,
 * updates motor target to produce "clicky" haptic feedback.
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
static float raw_angle_deg = 0.0f;     // Accumulated user-pushed angle
static float snapped_deg = 0.0f;       // Current detent-snapped target
static int16_t current_detent = 0;
static float last_motor_rad = 0.0f;
static bool first_tick = true;
static bool resync_pending = false;  // After external set_position, skip one delta

static constexpr float DEG2RAD = PI / 180.0f;
static constexpr float RAD2DEG = 180.0f / PI;

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
}

void haptic_update() {
    if (!config.enabled) return;

    float motor_rad = get_motor_angle(0);

    if (first_tick || resync_pending) {
        last_motor_rad = motor_rad;
        if (first_tick) {
            // Cold start: read current motor position
            raw_angle_deg = motor_rad * RAD2DEG;
            float lo = min_angle_deg();
            float hi = max_angle_deg();
            raw_angle_deg = constrain(raw_angle_deg, lo, hi);
            current_detent = snap_to_detent(raw_angle_deg, snapped_deg);
            set_motor_target(0, snapped_deg * DEG2RAD);
            first_tick = false;
        }
        // Stay in resync until motor arrives at commanded target.
        // This prevents the motor's approach motion from being picked
        // up as user input by the delta tracker.
        float err_rad = fabsf(motor_rad - snapped_deg * DEG2RAD);
        if (err_rad < 0.02f) {  // ~1.1° — tight enough to avoid overshoot leaking
            resync_pending = false;
        }
        return;
    }

    // Accumulate user push — only when motor deviates significantly from
    // the held detent position.  Small PID settling oscillations (motor
    // wobbling ±1° around the target) should NOT be interpreted as the
    // user pushing the knob.
    float delta_rad = angular_delta_rad(last_motor_rad, motor_rad);
    last_motor_rad = motor_rad;

    float holding_error_rad = fabsf(motor_rad - snapped_deg * DEG2RAD);
    if (holding_error_rad > 0.05f) {  // ~3° deadband — user is pushing
        raw_angle_deg += delta_rad * RAD2DEG;
    }

    // End-stop clamping — absorb excess into last_motor_rad so that
    // motor recovery after user releases doesn't cause a phantom jump.
    float lo = min_angle_deg();
    float hi = max_angle_deg();
    float unclamped = raw_angle_deg;
    raw_angle_deg = constrain(raw_angle_deg, lo - config.endstop_margin,
                                             hi + config.endstop_margin);
    float clamped_away_deg = unclamped - raw_angle_deg;
    if (clamped_away_deg != 0.0f) {
        // The motor physically moved past the limit.  Shift our tracking
        // baseline so the return swing won't be double-counted.
        last_motor_rad += clamped_away_deg * DEG2RAD;
    }

    // Clamp effective position to the valid range
    float effective_deg = constrain(raw_angle_deg, lo, hi);

    // Snap to detent
    float new_snap = 0.0f;
    int16_t new_detent = snap_to_detent(effective_deg, new_snap);

    // Apply detent strength: blend between free position and snapped
    float target_deg;
    if (config.detent_strength >= 1.0f || config.detent_count == 0) {
        target_deg = new_snap;
    } else if (config.detent_strength <= 0.0f) {
        target_deg = effective_deg;
    } else {
        target_deg = effective_deg + config.detent_strength * (new_snap - effective_deg);
    }

    // Only update motor target if it actually changed (avoid PID integral reset churn)
    float current_target_deg = get_motor_target(0) * RAD2DEG;
    if (fabsf(target_deg - current_target_deg) > 0.05f) {
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
    first_tick = true;  // Re-initialize positions
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
    raw_angle_deg = constrain(angle_deg, lo, hi);
    current_detent = snap_to_detent(raw_angle_deg, snapped_deg);
    set_motor_target(0, snapped_deg * DEG2RAD);
    // Don't set last_motor_rad here — motor hasn't moved yet.
    // Instead, flag resync so next update just resets the baseline.
    resync_pending = true;
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
