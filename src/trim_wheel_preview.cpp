/**
 * trim_wheel_preview.cpp - Cessna-style Trim Wheel Preview Mode
 */

#include "trim_wheel_preview.h"
#include "motor_control.h"
#include <math.h>

static constexpr float FULL_TURN_RAD = 6.28318530718f;

// Single-turn preview range with hard stops at both ends.
static constexpr float TRIM_MIN_ANGLE = 0.0f;
static constexpr float TRIM_MAX_ANGLE = FULL_TURN_RAD;

// Cessna-like "clicky" feel: fixed number of detents over the usable travel.
static constexpr uint16_t DETENT_COUNT = 48;
static constexpr float DETENT_STEP =
  (TRIM_MAX_ANGLE - TRIM_MIN_ANGLE) / (float)DETENT_COUNT;

static constexpr float TARGET_UPDATE_EPSILON = 0.0005f;

static float last_measured_angle = 0.0f;
static float commanded_angle = TRIM_MIN_ANGLE;
static float snapped_target = TRIM_MIN_ANGLE;
static uint16_t hid_value = 0;
static bool initialized = false;

static float wrap_to_0_2pi(float angle) {
  while (angle < 0.0f) {
    angle += FULL_TURN_RAD;
  }
  while (angle >= FULL_TURN_RAD) {
    angle -= FULL_TURN_RAD;
  }
  return angle;
}

static float shortest_angular_delta(float from, float to) {
  float delta = to - from;
  if (delta > 3.14159265359f) {
    delta -= FULL_TURN_RAD;
  } else if (delta < -3.14159265359f) {
    delta += FULL_TURN_RAD;
  }
  return delta;
}

void init_trim_wheel_preview() {
  float angle = wrap_to_0_2pi(get_motor_angle(0));
  last_measured_angle = angle;
  commanded_angle = constrain(angle, TRIM_MIN_ANGLE, TRIM_MAX_ANGLE);

  uint16_t detent_index =
    (uint16_t)roundf((commanded_angle - TRIM_MIN_ANGLE) / DETENT_STEP);
  if (detent_index > DETENT_COUNT) {
    detent_index = DETENT_COUNT;
  }

  snapped_target = TRIM_MIN_ANGLE + ((float)detent_index * DETENT_STEP);
  set_motor_target(0, snapped_target);

  hid_value = (uint16_t)((((float)detent_index) / (float)DETENT_COUNT) * 1023.0f);
  initialized = true;
}

void update_trim_wheel_preview() {
  if (!initialized) {
    init_trim_wheel_preview();
  }

  float measured = wrap_to_0_2pi(get_motor_angle(0));
  float delta = shortest_angular_delta(last_measured_angle, measured);
  last_measured_angle = measured;

  commanded_angle += delta;
  commanded_angle = constrain(commanded_angle, TRIM_MIN_ANGLE, TRIM_MAX_ANGLE);

  uint16_t detent_index =
    (uint16_t)roundf((commanded_angle - TRIM_MIN_ANGLE) / DETENT_STEP);
  if (detent_index > DETENT_COUNT) {
    detent_index = DETENT_COUNT;
  }

  float target = TRIM_MIN_ANGLE + ((float)detent_index * DETENT_STEP);
  if (fabsf(target - snapped_target) > TARGET_UPDATE_EPSILON) {
    snapped_target = target;
    set_motor_target(0, snapped_target);
  }

  hid_value = (uint16_t)((((float)detent_index) / (float)DETENT_COUNT) * 1023.0f);
}

uint16_t get_trim_wheel_hid_value() {
  return hid_value;
}
