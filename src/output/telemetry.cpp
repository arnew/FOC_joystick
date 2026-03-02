/**
 * telemetry.cpp — Rolling Statistics & Structured Telemetry Output
 *
 * Two error trackers fed at FOC rate (~1kHz):
 *   1. Ring buffer (0.5s) — variance + settle detection.
 *   2. EMA on squared error (α ≈ 0.005, τ ≈ 200ms) — RMS on query.
 *
 * Output: @T <ms>,<target>,<actual>,<error>,<rms>,<variance>,<settled>
 */

#include "telemetry.h"
#include <math.h>

// ============================================================================
// CONFIGURATION
// ============================================================================

static constexpr uint16_t RING_SIZE       = 500;    // 0.5s at ~1kHz
static constexpr uint16_t OUTPUT_INTERVAL = 100;    // ms → 10Hz
static constexpr uint16_t MIN_CDC_BYTES   = 48;     // skip output if CDC full

// Settle detection thresholds (generous — host applies stricter criteria)
static constexpr float  SETTLE_ERROR_RAD  = 0.087f; // ~5°
static constexpr float  SETTLE_VAR_RAD2   = 0.003f; // ~(3°)²
static constexpr uint16_t SETTLE_TICKS    = 200;    // 0.2s at 1kHz

// Recompute sums from scratch every N ticks to fight float drift
static constexpr uint32_t RECOMPUTE_INTERVAL = 10000; // ~10s

// ============================================================================
// STATE
// ============================================================================

static float    err_ring[RING_SIZE];
static uint16_t ring_head  = 0;
static uint16_t ring_count = 0;
static float    ring_sum   = 0.0f;
static float    ring_sum_sq = 0.0f;

static uint16_t consec_settled = 0;
static uint32_t ticks_since_recompute = 0;

static float last_target = 0.0f;
static float last_actual = 0.0f;
static float last_error  = 0.0f;

// EMA filter on squared error → RMS on query
// α = 1/200 ≈ 0.005 → τ ≈ 200 ticks ≈ 200ms at 1kHz FOC rate
static constexpr float EMA_ALPHA = 1.0f / 200.0f;
static float ema_sq_error = 0.0f;
static bool  ema_primed   = false;   // first sample seeds, no smoothing

// ============================================================================
// INTERNAL HELPERS
// ============================================================================

static void recompute_sums() {
  ring_sum = 0.0f;
  ring_sum_sq = 0.0f;
  for (uint16_t i = 0; i < ring_count; i++) {
    ring_sum    += err_ring[i];
    ring_sum_sq += err_ring[i] * err_ring[i];
  }
}

// ============================================================================
// PUBLIC API
// ============================================================================

void init_telemetry() {
  memset(err_ring, 0, sizeof(err_ring));
  ring_head  = 0;
  ring_count = 0;
  ring_sum   = 0.0f;
  ring_sum_sq = 0.0f;
  consec_settled = 0;
  ticks_since_recompute = 0;

  ema_sq_error = 0.0f;
  ema_primed = false;

  Serial.println("[TELEM] Format: @T ms,target,actual,error,rms,variance,settled");
}

void telemetry_update(float target_rad, float actual_rad) {
  // Signed error (unbounded motor: no wrap, actual − target is true error)
  float error = actual_rad - target_rad;

  // Remove oldest sample when buffer full (before overwrite)
  if (ring_count >= RING_SIZE) {
    float old = err_ring[ring_head];
    ring_sum    -= old;
    ring_sum_sq -= old * old;
  } else {
    ring_count++;
  }

  // Write new sample
  err_ring[ring_head] = error;
  ring_sum    += error;
  ring_sum_sq += error * error;
  ring_head = (ring_head + 1) % RING_SIZE;

  // EMA on squared error (cheap rolling RMS)
  float sq = error * error;
  if (!ema_primed) {
    ema_sq_error = sq;
    ema_primed = true;
  } else {
    ema_sq_error += EMA_ALPHA * (sq - ema_sq_error);
  }

  // Cache for output
  last_target = target_rad;
  last_actual = actual_rad;
  last_error  = error;

  // Periodic recompute to prevent float drift
  if (++ticks_since_recompute >= RECOMPUTE_INTERVAL) {
    recompute_sums();
    ticks_since_recompute = 0;
  }

  // Settle detection
  float var = telemetry_get_variance();
  if (fabsf(error) < SETTLE_ERROR_RAD && var < SETTLE_VAR_RAD2) {
    if (consec_settled < UINT16_MAX) consec_settled++;
  } else {
    consec_settled = 0;
  }
}

float telemetry_get_rms_error() {
  return sqrtf(ema_sq_error);
}

float telemetry_get_variance() {
  if (ring_count < 2) return 999.0f;
  float mean = ring_sum / ring_count;
  float var  = (ring_sum_sq / ring_count) - (mean * mean);
  return fmaxf(0.0f, var);
}

bool telemetry_is_settled() {
  return consec_settled >= SETTLE_TICKS;
}

void telemetry_output(unsigned long now_ms) {
  static unsigned long last_ms = 0;
  if (now_ms - last_ms < OUTPUT_INTERVAL) return;
  last_ms = now_ms;

  // Never block the FOC loop on a full CDC buffer
  if (!Serial || Serial.availableForWrite() < MIN_CDC_BYTES) return;

  float var = telemetry_get_variance();
  uint8_t settled = telemetry_is_settled() ? 1 : 0;

  float rms = telemetry_get_rms_error();

  char line[96];
  snprintf(line, sizeof(line), "@T %lu,%.4f,%.4f,%.4f,%.4f,%.6f,%u",
           now_ms, last_target, last_actual, last_error, rms, var, settled);
  Serial.println(line);
}
