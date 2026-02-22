/**
 *
 * SimpleFOCMini motor control example
 * 
 * For Arduino UNO or the other boards with the UNO headers
 * the most convenient way to use the board is to stack it to the pins:
 * - 12 - ENABLE
 * - 11 - IN1
 * - 10 - IN2
 * -  9 - IN3
 *
 */
#include <Arduino.h>
#include <SimpleFOC.h>


MagneticSensorI2C sensor = MagneticSensorI2C(AS5600_I2C);

// BLDC motor & driver instance
// BLDCMotor( int pp , float R)
// - pp            - pole pair number
// - R             - motor phase resistance
// - KV            - motor kv rating (rmp/v)
// - L             - motor phase inductance
BLDCMotor motor = BLDCMotor(7); 
// BLDCDriver3PWM driver = BLDCDriver3PWM(11, 10, 9, 8); // mini v1.0
// BLDCDriver3PWM(int phA,int phB,int phC, int en1 = NOT_SET, int en2 = NOT_SET, int en3 = NOT_SET);
BLDCDriver3PWM driver = BLDCDriver3PWM(13, 12, 11, 10); // mini v1.0 on rp2040




void setup() {

  // use monitoring with serial 
  Serial.begin(115200);
  // enable more verbose output for debugging
  // comment out if not needed
  SimpleFOCDebug::enable(&Serial);
  
  // power supply voltage
  driver.voltage_power_supply = 12;
  driver.pwm_frequency = 30000;
  driver.init();
  motor.linkDriver(&driver);

  // initialise magnetic sensor hardware
  sensor.init();
  // link the motor to the sensor
  motor.linkSensor(&sensor);

  // aligning voltage 
  // motor.voltage_sensor_align = 1.0f;
//  motor.sensor_direction=Direction::CW;
//  motor.zero_electric_angle=3.9960;


  // choose FOC modulation (optional)
  // motor.foc_modulation = FOCModulationType::SpaceVectorPWM;

  // motor.torque_controller = TorqueControlType::voltage;
  // set motion control loop to be used
  motor.controller = MotionControlType::angle;

  // contoller configuration
  // default parameters in defaults.h

  // velocity PI controller parameters
  motor.PID_velocity.P *= 0.25f;
  // motor.PID_velocity.I = 0.0f;
  // motor.PID_velocity.D = 0.0f;
  // motor.PID_velocity.P = 0.2f;
  // motor.PID_velocity.I = 2.0f;
  // motor.PID_velocity.D = 0;
  // maximal voltage to be set to the motor
  
  // velocity low pass filtering time constant
  // the lower the less filtered
  // motor.LPF_velocity.Tf *= 10.0f;
  motor.LPF_angle.Tf = 0.01f;

  // angle P controller
  // motor.P_angle.P = 10.0f;
  // maximal velocity of the position control


  motor.voltage_limit = 2.0f;
  // motor.velocity_limit = 5.0f;
  

  // initialize motor
  motor.init();
  // align sensor and start FOC
  motor.initFOC();
}

const float notch_factor = 10/(2*PI) ;

void loop() {
    
  // main FOC algorithm function
  motor.loopFOC();
  float angle = motor.shaft_angle;
  Serial.print("Angle: ");
  Serial.print(angle, 4);
  angle = round(angle*notch_factor)/notch_factor; // 0.1 rad steps
  Serial.print(" Target angle: ");
  Serial.println(angle, 4);

  // Motion control function
  motor.move(angle);
}

