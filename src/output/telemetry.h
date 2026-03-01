/**
 * telemetry.h — Device-Side Rolling Statistics & Structured Output
 *
 * Two complementary error trackers, both fed at FOC rate (~1kHz):
 *
 *   1. Ring buffer (0.5s) — variance + settle detection for host tests.
 *   2. EMA filter (α ≈ 0.005, τ ≈ 200ms) on squared error → RMS on query.
 *      Cheap, O(1), no buffer.  Use for on-device quality gating.
 *
 * Output at 10Hz:
 *   @T <ms>,<target>,<actual>,<error>,<rms>,<variance>,<settled>
 */

#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <Arduino.h>

/**
 * Initialize telemetry ring buffer and print format legend.
 */
void init_telemetry();

/**
 * Feed one FOC sample into the ring buffer.
 * Call every FOC loop iteration (~1kHz).
 * @param target_rad Current target angle (radians)
 * @param actual_rad Current sensor angle (radians)
 */
void telemetry_update(float target_rad, float actual_rad);

/**
 * Emit one @T line if the output interval has elapsed.
 * Skips silently when the CDC buffer is full (never blocks FOC).
 * @param now_ms Current millis() value
 */
void telemetry_output(unsigned long now_ms);

/**
 * Rolling RMS error (EMA, τ ≈ 200ms).
 * @return sqrt(ema_of_squared_error) in radians
 */
float telemetry_get_rms_error();

/**
 * Rolling variance of error over the 0.5s window.
 * @return Variance in rad² (999.0 if < 2 samples)
 */
float telemetry_get_variance();

/**
 * Device-side settled flag.
 * True when |error| < threshold AND variance < threshold
 * for at least 0.2s consecutive.
 */
bool telemetry_is_settled();

#endif // TELEMETRY_H
