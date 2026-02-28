/**
 * statistics.cpp - Device Self-Inspection & Statistics Implementation
 */

#include "statistics.h"
#include <limits.h>

// Global statistics storage
static SystemStats stats;

void init_statistics() {
  memset(&stats, 0, sizeof(SystemStats));
  stats.loop.min_us = UINT32_MAX;  // Will be updated to actual minimum
  
  Serial.println("[STATS] Statistics collection initialized");
}

void record_loop_timing(uint32_t duration_us) {
  stats.loop.count++;
  stats.loop.sum_us += duration_us;
  
  if (duration_us < stats.loop.min_us) {
    stats.loop.min_us = duration_us;
  }
  if (duration_us > stats.loop.max_us) {
    stats.loop.max_us = duration_us;
  }
}

void record_motor_movement(uint8_t motor_id) {
  if (motor_id >= 1) return;
  stats.motor[motor_id].movements++;
}

void record_motor_hold(uint8_t motor_id, float error) {
  if (motor_id >= 1) return;
  
  stats.motor[motor_id].holds++;
  
  float abs_error = fabs(error);
  if (abs_error > stats.motor[motor_id].max_error) {
    stats.motor[motor_id].max_error = abs_error;
  }
}

void record_motor_limit(uint8_t motor_id) {
  if (motor_id >= 1) return;
  stats.motor[motor_id].limit_hits++;
}

void record_midi_byte() {
  stats.messages.midi_bytes++;
}

void record_midi_message() {
  stats.messages.midi_messages++;
}

void record_hid_report() {
  stats.messages.hid_reports++;
}

void record_commander_cmd() {
  stats.messages.commander_cmds++;
}

void update_statistics_uptime() {
  stats.uptime_ms = millis();
}

const SystemStats* get_statistics() {
  return &stats;
}

static void print_loop_timing() {
  Serial.println("\n--- Loop Timing ---");
  Serial.print("Iterations: ");
  Serial.println(stats.loop.count);
  
  if (stats.loop.count > 0) {
    uint32_t avg_us = stats.loop.sum_us / stats.loop.count;
    Serial.print("Min: ");
    Serial.print(stats.loop.min_us);
    Serial.println(" µs");
    Serial.print("Max: ");
    Serial.print(stats.loop.max_us);
    Serial.println(" µs");
    Serial.print("Avg: ");
    Serial.print(avg_us);
    Serial.println(" µs");
    Serial.print("Freq: ~");
    Serial.print(1000000.0 / avg_us, 0);
    Serial.println(" Hz");
  }
}

static void print_motor_stats() {
  for (uint8_t i = 0; i < 1; i++) {
    Serial.print("\n--- Motor ");
    Serial.print(i);
    Serial.println(" ---");
    Serial.print("Movements: ");
    Serial.println(stats.motor[i].movements);
    Serial.print("Holds checked: ");
    Serial.println(stats.motor[i].holds);
    Serial.print("Max error: ");
    Serial.print(stats.motor[i].max_error, 4);
    Serial.println(" rad");
    Serial.print("Limit hits: ");
    Serial.println(stats.motor[i].limit_hits);
  }
}

static void print_message_stats() {
  Serial.println("\n--- Messages ---");
  Serial.print("MIDI bytes: ");
  Serial.println(stats.messages.midi_bytes);
  Serial.print("MIDI messages: ");
  Serial.println(stats.messages.midi_messages);
  Serial.print("HID reports: ");
  Serial.println(stats.messages.hid_reports);
  Serial.print("Commander cmds: ");
  Serial.println(stats.messages.commander_cmds);
}

void print_statistics() {
  Serial.println("\n=== DEVICE STATISTICS ===");
  
  // System info
  Serial.print("Uptime: ");
  Serial.print(stats.uptime_ms / 1000.0, 3);
  Serial.println(" sec");
  
  print_loop_timing();
  print_motor_stats();
  print_message_stats();
  
  Serial.println("=========================\n");
}

void reset_statistics() {
  uint32_t uptime = stats.uptime_ms;  // Preserve uptime
  init_statistics();
  stats.uptime_ms = uptime;
  Serial.println("[STATS] Statistics reset");
}
