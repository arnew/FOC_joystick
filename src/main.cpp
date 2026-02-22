/**
 * USB HID Joystick Controller with MIDI Profiles
 * 
 * Dual-motor SimpleFOC controller for Microsoft Flight Simulator
 * - Motor 0: Throttle, Flaps, Spoilers (0-180°)
 * - Motor 1: Landing Gear, Trim (0-180°, + endless trim rotation)
 * 
 * Input: MIDI CC messages via Serial1 (31250 baud)
 * Output: USB HID joystick (TinyUSB)
 * 
 * Architecture: 6 phases
 * 1. Configuration System (config.h)
 * 2. Motor Controller Abstraction (motors[] array)
 * 3. MIDI Input Handler (Serial1 parser)
 * 4. Axis Output Scaling (angle → 0-1023)
 * 5. USB HID Joystick (Adafruit_TinyUSB) - TODO
 * 6. Main Loop Integration
 */

#include <Arduino.h>
#include <SimpleFOC.h>
#include "config.h"
#include "pid_config.h"
#include "Adafruit_TinyUSB.h"

// ============================================================================
// USB DEVICE INTERFACES
// ============================================================================
// HID device (USB joystick)
Adafruit_USBD_HID usb_hid;
// Native USB MIDI device
Adafruit_USBD_MIDI usb_midi;

// ============================================================================
// MOTOR DEFINITIONS - Phase 2: Dual Motor Abstraction
// ============================================================================

/**
 * Motor 0: Primary axis
 * Encoder: AS5600 via I2C
 * Driver: 3-phase PWM (pins 13, 12, 11, enable 10)
 */
MagneticSensorI2C sensor0 = MagneticSensorI2C(AS5600_I2C);
BLDCMotor motor0(7);  // 7 pole pairs
BLDCDriver3PWM driver0(13, 12, 11, 10);

/**
 * Motor 1: Secondary axis (gear and trim)
 * Encoder: AS5600 via I2C (separate on RP2040)
 * Driver: 3-phase PWM (pins to be defined for second motor)
 * NOTE: For now, we'll configure Motor 1 on the same encoder (parallel)
 *       In production, use separate I2C addresses or encoders
 * 
 * TODO: Configure separate encoder/PWM pins for Motor 1
 * TODO: Only initialized if NUM_MOTORS > 1
 */
#if NUM_MOTORS > 1
BLDCMotor motor1(7);  // 7 pole pairs
BLDCDriver3PWM driver1(13, 12, 11, 10);  // Placeholder - update pins
#endif

// Motor array for iteration
BLDCMotor* motors[2] = {&motor0, 
  #if NUM_MOTORS > 1
  &motor1
  #else
  nullptr
  #endif
};
BLDCDriver3PWM* drivers[2] = {&driver0, 
  #if NUM_MOTORS > 1
  &driver1
  #else
  nullptr
  #endif
};
MagneticSensorI2C* sensors[2] = {&sensor0, 
  #if NUM_MOTORS > 1
  &sensor0  // TODO: Add sensor1
  #else
  nullptr
  #endif
};

// ============================================================================
// MOTOR STATE VARIABLES
// ============================================================================

float target_angle[2] = {0.0f, 0.0f};      // Target angles (radians)
float current_angle[2] = {0.0f, 0.0f};     // Current angles (radians)
uint16_t axis_values[2] = {512, 512};      // USB joystick values (0-1023)
uint8_t active_motor = 0;                  // Currently active motor (0 or 1)

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================

void process_midi_message(uint8_t status, uint8_t cc_number, uint8_t cc_value);
void set_motor_target(uint8_t motor_id, float angle);
void handle_motor_limits(uint8_t motor_id, float& angle);
uint16_t angle_to_joystick_value(uint8_t motor_id);
void setup_usb_hid();
void send_hid_report();

// ============================================================================
// PHASE 3: MIDI INPUT HANDLER
// ============================================================================

// MIDI message parser state machine
#define MIDI_BUFFER_SIZE 3
uint8_t midi_buffer[MIDI_BUFFER_SIZE];
uint8_t midi_buffer_index = 0;

/**
 * Parse incoming MIDI byte
 * Expects 3-byte messages: [0xBn, CC#, value]
 */
void handle_midi_byte(uint8_t byte) {
  if (midi_buffer_index == 0) {
    // First byte: must be channel message (0xB0-0xBF = CC)
    if ((byte & 0xF0) == 0xB0) {
      midi_buffer[0] = byte;
      midi_buffer_index = 1;
    }
    return;
  }
  
  if (midi_buffer_index == 1) {
    // Second byte: CC number
    midi_buffer[1] = byte & 0x7F;  // 0-127
    midi_buffer_index = 2;
    return;
  }
  
  if (midi_buffer_index == 2) {
    // Third byte: CC value
    midi_buffer[2] = byte & 0x7F;  // 0-127
    midi_buffer_index = 0;          // Reset for next message
    
    // Process complete MIDI message
    process_midi_message(midi_buffer[0], midi_buffer[1], midi_buffer[2]);
  }
}

/**
 * Process a complete 3-byte MIDI CC message
 * Maps CC# to motor target angle
 */
void process_midi_message(uint8_t status, uint8_t cc_number, uint8_t cc_value) {
  // Ignore if not a CC message (status byte 0xB0 = CC on channel 1)
  if ((status & 0xF0) != 0xB0) return;
  
  // Find axis matching this CC number
  const AxisProfile* axis = find_axis_by_cc(cc_number);
  if (!axis) {
    // Unknown CC, ignore
    Serial.print("MIDI: Unknown CC#");
    Serial.println(cc_number);
    return;
  }
  
  // Calculate target angle from MIDI CC value
  float target = cc_to_angle(axis, cc_value);
  
  // Set motor target
  set_motor_target(axis->motor_id, target);
  
  // Debug output
  Serial.print("MIDI: CC#");
  Serial.print(cc_number);
  Serial.print(" = ");
  Serial.print(cc_value);
  Serial.print(" → ");
  Serial.print(axis->label);
  Serial.print(" Motor");
  Serial.print(axis->motor_id);
  Serial.print(" angle: ");
  Serial.println(target, 4);
}

// ============================================================================
// PHASE 2: MOTOR CONTROL FUNCTIONS
// ============================================================================

/**
 * Set target angle for a motor
 * Handles limit checking for limited/endless axes
 */
void set_motor_target(uint8_t motor_id, float angle) {
  if (motor_id >= 2) return;
  
  const MotorProfile* profile = get_motor_profile(motor_id);
  if (!profile) return;
  
  // Apply motor limits
  handle_motor_limits(motor_id, angle);
  
  target_angle[motor_id] = angle;
  active_motor = motor_id;
}

/**
 * Get current angle for a motor
 */
float get_motor_angle(uint8_t motor_id) {
  if (motor_id >= 2) return 0.0f;
  return current_angle[motor_id];
}

/**
 * Apply motor limits: clamp for limited axes, wrap for endless
 */
void handle_motor_limits(uint8_t motor_id, float& angle) {
  if (motor_id >= 2) return;
  
  const MotorProfile* profile = get_motor_profile(motor_id);
  if (!profile) return;
  
  if (profile->is_endless) {
    // Endless axis: wrap to 0-360° (0-2π radians)
    while (angle < 0.0f) angle += 6.28318f;
    while (angle > 6.28318f) angle -= 6.28318f;
  } else {
    // Limited axis: clamp to min-max
    angle = constrain(angle, profile->min_angle, profile->max_angle);
  }
}

// ============================================================================
// PHASE 4: AXIS OUTPUT SCALING
// ============================================================================

/**
 * Convert motor angle to USB joystick value (0-1023)
 * Respects motor limits and reversed flag
 */
uint16_t angle_to_joystick_value(uint8_t motor_id) {
  if (motor_id >= 2) return 512;  // Center
  
  const MotorProfile* profile = get_motor_profile(motor_id);
  if (!profile) return 512;
  
  float angle = current_angle[motor_id];
  float normalized = 0.5f;  // Default: center
  
  // Normalize angle to 0.0-1.0 range based on motor limits
  if (profile->max_angle > profile->min_angle) {
    normalized = (angle - profile->min_angle) / (profile->max_angle - profile->min_angle);
  }
  
  // Find and apply axis profile (for reversed flag)
  for (uint8_t i = 0; i < NUM_A320_AXES; i++) {
    if (A320_CONFIG[i].motor_id == motor_id) {
      if (A320_CONFIG[i].reversed) {
        normalized = 1.0f - normalized;
      }
      break;
    }
  }
  
  // Clamp to valid range
  normalized = constrain(normalized, 0.0f, 1.0f);
  
  // Map to 0-1023
  return (uint16_t)(normalized * 1023.0f);
}

// ============================================================================
// PHASE 5: USB HID JOYSTICK (TODO - To be implemented)
// ============================================================================

// HID Joystick Report Structure
typedef struct {
  uint8_t buttons; // 8 buttons mapped to bits 0..7
  uint16_t x;      // Motor 0 axis (0..1023)
  uint16_t y;      // Motor 1 axis (0..1023)
} __attribute__((packed)) hid_joystick_report_t;

hid_joystick_report_t current_report = {0, 512, 512};

/**
 * Initialize USB HID Joystick
 * TODO: Implement with proper TinyUSB or RP2040 USB library
 */
void setup_usb_hid() {
  // HID report descriptor: Report ID 1, 8 buttons + 2 axes (16-bit, 0..1023)
  // This layout matches common gamepad descriptors that the Linux kernel
  // maps to an /dev/input/event* (evdev) device and /dev/input/js*.
  static const uint8_t hid_report_descriptor[] = {
    0x05, 0x01,       // Usage Page (Generic Desktop)
    0x09, 0x05,       // Usage (Game Pad)
    0xA1, 0x01,       // Collection (Application)
    0x85, 0x01,       //   Report ID (1)
    // Buttons (8)
    0x05, 0x09,       //   Usage Page (Button)
    0x19, 0x01,       //   Usage Minimum (Button 1)
    0x29, 0x08,       //   Usage Maximum (Button 8)
    0x15, 0x00,       //   Logical Minimum (0)
    0x25, 0x01,       //   Logical Maximum (1)
    0x95, 0x08,       //   Report Count (8)
    0x75, 0x01,       //   Report Size (1)
    0x81, 0x02,       //   Input (Data,Var,Abs)
    // Axes (X, Y) 16-bit each, 0..1023
    0x05, 0x01,       //   Usage Page (Generic Desktop)
    0x09, 0x30,       //   Usage (X)
    0x09, 0x31,       //   Usage (Y)
    0x16, 0x00, 0x00, //   Logical Minimum (0)
    0x26, 0xFF, 0x03, //   Logical Maximum (1023)
    0x75, 0x10,       //   Report Size (16)
    0x95, 0x02,       //   Report Count (2)
    0x81, 0x02,       //   Input (Data,Var,Abs)
    0xC0              // End Collection
  };

  // Register descriptor and start HID
  usb_hid.setReportDescriptor(hid_report_descriptor, sizeof(hid_report_descriptor));
  usb_hid.begin();

  Serial.println("USB HID initialized");
}

/**
 * Send USB HID report with current axis values
 * TODO: Implement actual HID report transmission
 */
void send_hid_report() {
  // Only send if values changed
  if (axis_values[0] != current_report.x || axis_values[1] != current_report.y) {
    current_report.x = axis_values[0];
    current_report.y = axis_values[1];

    if (usb_hid.ready()) {
      // report id 1 matches the descriptor's Report ID (0x85, 0x01)
      usb_hid.sendReport(1, &current_report, sizeof(current_report));
    }
  }
}

// ============================================================================
// SETUP
// ============================================================================

void setup() {
    // ===== USB HID Setup =====
  setup_usb_hid();

  // Initialize USB devices
  // Serial (CDC#0): Debug output at 115200 baud (built-in via Arduino)
  Serial.begin(115200);
  // Start native USB MIDI device (host will create a MIDI port)
  usb_midi.begin();
  
  // Wait for USB enumeration
  //delay(2000);
  
  Serial.println("\n=== USB HID Joystick Controller ===");
  Serial.println("USB Interfaces Initialized:");
  Serial.println("  CDC#0 /dev/ttyACM0 (115200) - Debug output");
  Serial.println("  Native USB MIDI port - MIDI input @ 31250 baud");
  Serial.println("  USB HID Joystick (Gamepad) - 8 buttons + 2 axes");
  Serial.println("Initializing Motor 0...");
  
  // ===== Motor 0 Setup =====
  driver0.voltage_power_supply = 12.0f;
  driver0.pwm_frequency = 30000;
  driver0.init();
  motor0.linkDriver(&driver0);
  
  sensor0.init();
  motor0.linkSensor(&sensor0);
  
  // Angle/position control loop
  motor0.controller = MotionControlType::angle;
  motor0.voltage_limit = MOTOR0_VOLTAGE_LIMIT;
  
  // PID gains from pid_config.h (SimpleFOC angle controller)
  // Note: SimpleFOC uses P, I, D directly for angle control via voltage command
  motor0.P_angle.P = MOTOR0_PID_P;
  motor0.P_angle.I = MOTOR0_PID_I;
  motor0.P_angle.D = MOTOR0_PID_D;
  
  // Velocity loop gains (used internally by SimpleFOC for smooth motion)
  motor0.PID_velocity.P = MOTOR0_VELOCITY_P;
  motor0.PID_velocity.I = MOTOR0_VELOCITY_I;
  motor0.PID_velocity.D = MOTOR0_VELOCITY_D;
  
  // Low-pass filter to smooth sensor readings
  motor0.LPF_angle.Tf = MOTOR0_LPF_ANGLE_TF;
  
  motor0.init();
  motor0.initFOC();
  
  Serial.print("Motor 0 initialized with PID: Kp=");
  Serial.print(MOTOR0_PID_P);
  Serial.print(" Ki=");
  Serial.print(MOTOR0_PID_I);
  Serial.print(" Kd=");
  Serial.println(MOTOR0_PID_D);
  
  // ===== Motor 0 Setup (continued) =====
  
  // ===== Motor 1 Setup =====
  // TODO: Configure separate driver/encoder pins
  Serial.println("Motor 1 disabled (placeholder)");
  

  
  // ===== Configuration Output =====
  Serial.println("\n=== Loaded Configuration ===");
  Serial.print("Number of axes: ");
  Serial.println(NUM_A320_AXES);
  
  for (uint8_t i = 0; i < NUM_A320_AXES; i++) {
    Serial.print("  ");
    Serial.print(i);
    Serial.print(": ");
    Serial.print(A320_CONFIG[i].label);
    Serial.print(" (Motor");
    Serial.print(A320_CONFIG[i].motor_id);
    Serial.print(", CC#");
    Serial.print(A320_CONFIG[i].midi_cc);
    Serial.print(", ");
    Serial.print(A320_CONFIG[i].motor.is_endless ? "endless" : "limited");
    Serial.println(")");
  }
  
  Serial.println("\n=== Ready ===");
}

// ============================================================================
// MAIN CONTROL LOOP - Phase 6: Main Loop Integration
// ============================================================================

const float notch_factor = 10.0f / (2.0f * PI);

void loop() {
  // ===== 1. FOC Control Loop (~1 kHz) =====
  
  // Motor 0
  motor0.loopFOC();
  current_angle[0] = motor0.shaft_angle;
  motor0.move(target_angle[0]);
  
  // Motor 1 (placeholder, not fully configured yet)
  // motor1.loopFOC();
  // current_angle[1] = motor1.shaft_angle;
  // motor1.move(target_angle[1]);
  
  // ===== 2. MIDI Input (Async via native USB MIDI) =====
  // Read MIDI CC commands from native USB MIDI port
  // Format: Standard 3-byte MIDI CC messages
  while (usb_midi.available()) {
    handle_midi_byte(usb_midi.read());
  }
  
  // ===== 3. USB HID Output (~100 Hz) =====
  static unsigned long last_hid_update = 0;
  unsigned long now = millis();
  
  if (now - last_hid_update >= 10) {  // 100 Hz
    // Convert angles to joystick values
    axis_values[0] = angle_to_joystick_value(0);
    axis_values[1] = angle_to_joystick_value(1);
    
    // Send USB HID report
    send_hid_report();
    
    last_hid_update = now;
  }
  
  // ===== 4. Debug Serial Output (~1 Hz) =====
  static unsigned long last_debug = 0;
  
  if (now - last_debug >= 1000) {
    // Motor angles (quantized to 0.1 rad steps)
    float angle_q = round(current_angle[0] * notch_factor) / notch_factor;
    
    Serial.print("Angle: ");
    Serial.print(angle_q, 4);
    Serial.print(" rad (");
    Serial.print(angle_q * 180.0f / PI, 1);
    Serial.print("°)");
    
    Serial.print(" | Target: ");
    Serial.print(target_angle[0], 4);
    
    Serial.print(" | USB: ");
    Serial.print(axis_values[0]);
    Serial.println(" (0-1023)");
    
    last_debug = now;
  }
}
