#!/usr/bin/env python3
"""
PID Calibration Script using Ziegler-Nichols Relay Method

Complete automated tuning workflow:
1. [Phase 1] Ramp test: Sanity check + motor type detection (endless vs limited)
2. [Phase 2] Relay tuning: Square wave injection + oscillation analysis
3. [Phase 3] Step response validation: Measure rise time & overshoot
4. Calculate PID gains using Ziegler-Nichols rules with 0.65 safety factor

Usage:
    python3 test/calibrate_pid.py              # Run full calibration (all phases)
    python3 test/calibrate_pid.py --ramp-only  # [Phase 1] Sanity check only
    python3 test/calibrate_pid.py --relay-only # [Phase 2] Skip ramp, do relay+relay analysis
    python3 test/calibrate_pid.py --step-only  # [Phase 3] Step response validation only
    python3 test/calibrate_pid.py --debug      # Enable verbose output
"""

import os
import sys
import time
import argparse
import serial
from serial.tools import list_ports
import struct

# Import high-speed monitor for better dynamics capture
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from motor_monitor import HighSpeedMonitor

try:
    import pygame.midi
    PYGAME_MIDI_AVAILABLE = True
except ImportError:
    PYGAME_MIDI_AVAILABLE = False


class PIDCalibrator:
    """Ziegler-Nichols PID calibration via relay method"""
    
    def __init__(self, debug_port, motor_id=0, debug=False):
        self.debug_port = debug_port
        self.motor_id = motor_id
        self.debug = debug
        self.debug_ser = None
        self.midi_output = None  # Persistent MIDI output device
        self.midi_initialized = False
        
        # Initialize pygame.midi once at startup
        self._init_midi()
    
    def _init_midi(self):
        """Initialize pygame.midi once with persistent connection"""
        if not PYGAME_MIDI_AVAILABLE:
            return False
        
        try:
            pygame.midi.init()
            # Find Pico MIDI output port
            for i in range(pygame.midi.get_count()):
                info = pygame.midi.get_device_info(i)
                # info = (interface, name, input, output, is_open)
                if b"Pico" in info[1] and info[3] == 1:  # output=1
                    self.midi_output = pygame.midi.Output(i)
                    self.midi_initialized = True
                    if self.debug:
                        print(f"✓ pygame.midi: {info[1].decode()}")
                    return True
        except Exception as e:
            if self.debug:
                print(f"⚠ pygame.midi init: {e}")
        
        return False
        
    def connect(self):
        """Connect to debug serial port and verify responsiveness"""
        if not self.debug_port:
            print("✗ No debug port available")
            return False
        
        try:
            self.debug_ser = serial.Serial(self.debug_port, 115200, timeout=2)
            print(f"✓ Connected to debug port: {self.debug_port}")
            
            # Clear any startup messages
            time.sleep(0.5)
            self.debug_ser.reset_input_buffer()
            
            # Wait for firmware to stabilize
            time.sleep(1.5)
            
            # Verify we can read debug output
            print("Verifying device responsiveness...")
            self.debug_ser.reset_input_buffer()
            
            for attempt in range(3):
                lines = self.read_debug_lines(timeout=1.0, max_lines=5)
                if lines:
                    for line in lines:
                        if "Angle:" in line:
                            print(f"✓ Device responsive: {line[:50]}...")
                            return True
                if attempt < 2:
                    time.sleep(0.5)
            
            print("⚠ Warning: Device not responding with debug output yet")
            print("  Will attempt calibration anyway...")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def close(self):
        """Close serial and MIDI connections"""
        if self.debug_ser:
            self.debug_ser.close()
        if self.midi_output:
            try:
                self.midi_output.close()
            except:
                pass
    
    def read_debug_lines(self, timeout=1.0, max_lines=100):
        """Read lines from debug serial output"""
        lines = []
        start = time.time()
        while time.time() - start < timeout:
            try:
                if self.debug_ser.in_waiting:
                    line = self.debug_ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        lines.append(line)
                        if self.debug:
                            print(f"  [DBG] {line}")
                else:
                    time.sleep(0.01)
            except:
                pass
        
        return lines
    
    def read_debug_lines_buffered(self, timeout=0.2):
        """
        Read all available lines from debug port (buffered for ~1 Hz serial output)
        Accumulates multiple samples in one read window since device outputs at ~1 Hz
        """
        lines = []
        start = time.time()
        while time.time() - start < timeout:
            if self.debug_ser.in_waiting > 0:
                try:
                    line = self.debug_ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        lines.append(line)
                except:
                    pass
            time.sleep(0.01)  # 10 ms granularity
        return lines
    
    def capture_dynamics_highspeed(self, duration=3.0):
        """
        Capture motor dynamics at high speed using HighSpeedMonitor
        
        Returns:
            dict: {velocity_mean, velocity_max, sample_rate} or None if failed
        """
        if not self.debug_ser:
            return None
        
        try:
            monitor = HighSpeedMonitor(self.debug_ser)
            samples = monitor.collect_samples(duration=duration, target_hz=100)
            
            if len(samples) < 3:
                return None
            
            stats = monitor.get_stats()
            if self.debug:
                print(f"  ✓ High-speed capture: {len(samples)} samples @ {stats['sample_rate']:.1f} Hz")
                print(f"    Velocity: {stats['velocity_mean']:.4f} rad/s (avg), {stats['velocity_max']:.4f} rad/s (max)")
            
            return stats
        except Exception as e:
            if self.debug:
                print(f"  ⚠ High-speed monitor error: {e}")
            return None
    
    def send_midi_cc(self, cc_num, cc_val):
        """Send MIDI CC via persistent pygame.midi connection"""
        if not self.midi_initialized or not self.midi_output:
            # Retry initialization if it failed
            if not self._init_midi():
                return False
        
        try:
            self.midi_output.write([[[0xB0, cc_num & 0x7F, cc_val & 0x7F, 0], pygame.midi.time()]])
            return True
        except Exception as e:
            if self.debug:
                print(f"⚠ MIDI write failed: {e}")
            return False
    
    def relay_test(self, duration=5.0, frequency=2):
        """
        Perform relay tuning: send square wave input, measure response
        
        Returns:
            dict: {oscillation_freq, peak_amplitude, settling_time}
        """
        print("\n" + "="*70)
        print(f"RELAY TEST: Motor {self.motor_id}")
        print("="*70)
        print(f"Duration: {duration}s, Frequency: {frequency} Hz")
        print("Sending square wave: 10° → 90° → 10° → ...")
        
        samples = []
        start_time = time.time()
        
        # Clear any buffered input
        self.debug_ser.reset_input_buffer()
        
        # Send initial MIDI commands to establish square wave
        print("Initializing square wave...")
        wave_period = 1.0 / frequency
        half_period = wave_period / 2
        
        cc_low = 25   # ~10°
        cc_high = 90  # ~75°
        
        mid_point_time = start_time + duration
        next_send_time = start_time
        cc_val = cc_low
        
        while time.time() < mid_point_time:
            current_time = time.time()
            
            # Send MIDI on schedule (every half period)
            if current_time >= next_send_time:
                success = self.send_midi_cc(64, cc_val)
                if self.debug:
                    print(f"  [MIDI] CC#64 = {cc_val} {'✓' if success else '⚠'}")
                
                # Toggle for next send
                cc_val = cc_high if cc_val == cc_low else cc_low
                next_send_time += half_period
            
            # Read motor response continuously
            lines = self.read_debug_lines(timeout=0.1)
            for line in lines:
                # More lenient parsing - accept various formats
                if "Angle:" in line:
                    try:
                        # Try multiple parsing strategies
                        angle = None
                        
                        # Strategy 1: "Angle: 1.2345 rad"
                        if "rad" in line:
                            parts = line.split("Angle:")
                            if len(parts) > 1:
                                num_str = parts[1].strip().split()[0]
                                angle = float(num_str)
                        
                        # Strategy 2: Direct index (fallback)
                        if angle is None:
                            words = line.split()
                            for i, w in enumerate(words):
                                if w == "Angle:" and i+1 < len(words):
                                    try:
                                        angle = float(words[i+1])
                                        break
                                    except:
                                        pass
                        
                        if angle is not None:
                            samples.append({
                                'time': current_time - start_time,
                                'angle': angle
                            })
                            if self.debug:
                                print(f"  [SAMPLE] t={samples[-1]['time']:.2f}s, angle={angle:.3f} rad")
                    except Exception as e:
                        if self.debug:
                            print(f"  [PARSE ERROR] {line[:50]}: {e}")
        
        if not samples:
            print("✗ No motor response data collected")
            print("  Check:")
            print("  - Device is connected and running")
            print("  - MIDI port is accessible (pygame.midi)")
            print("  - Motor is powered and encoder is working")
            return None
        
        print(f"✓ Collected {len(samples)} samples over {duration}s")
        
        # Analyze collected samples
        result = self._analyze_oscillation(samples, is_relay=True)
        return result
    
    def _analyze_oscillation(self, samples, is_relay=False):
        """
        Analyze oscillation frequency and amplitude from samples
        
        Returns:
            dict: Tuning parameters (Ku, Pu, Kp, Ki, Kd)
        """
        if len(samples) < 5:
            print("⚠ Very few samples for analysis (< 5)")
            # Return conservative defaults
            print("  Using conservative default tuning...")
            Ku = 2.0
            Pu = 1.0
        else:
            angles = [s['angle'] for s in samples]
            times = [s['time'] for s in samples]
            
            # Find zero crossings to estimate frequency
            zero_crossings = 0
            target_angle = sum(angles) / len(angles)  # mean
            
            for i in range(1, len(angles)):
                if (angles[i-1] - target_angle) * (angles[i] - target_angle) < 0:
                    zero_crossings += 1
            
            if zero_crossings < 2:
                print(f"⚠ Weak oscillation detected ({zero_crossings} zero crossings)")
                print(f"  Mean angle: {target_angle:.3f} rad")
                print(f"  Min angle: {min(angles):.3f} rad") 
                print(f"  Max angle: {max(angles):.3f} rad")
                print(f"  Amplitude: {(max(angles) - min(angles))/2:.3f} rad")
                
                # Conservative estimate
                Ku = 2.0
                Pu = 1.0
            else:
                # Period = 2 * (total_time / zero_crossings)
                total_time = times[-1] - times[0]
                Pu = 2.0 * total_time / zero_crossings
                
                # Ultimate gain (relay amplitude / oscillation amplitude)
                amplitude = (max(angles) - min(angles)) / 2.0
                relay_amplitude = (90.0 - 25.0) * 0.5  # 65° / 2
                
                if amplitude > 0.01:
                    Ku = relay_amplitude / amplitude
                else:
                    Ku = 2.0
                
                print(f"✓ Oscillation detected:")
                print(f"  Period (Pu): {Pu:.3f}s")
                print(f"  Frequency: {1/Pu:.2f} Hz")
                print(f"  Mean angle: {target_angle:.3f} rad ({target_angle*180/3.14159:.1f}°)")
                print(f"  Amplitude: {amplitude:.3f} rad ({amplitude*180/3.14159:.1f}°)")
                print(f"  Ultimate Gain (Ku): {Ku:.3f}")
        
        # Ziegler-Nichols Tuning Rules
        Kp = 0.6 * Ku
        Ki = 1.2 * Ku / Pu if Pu > 0 else 0.0
        Kd = 3.0 * Ku * Pu / 40.0
        
        # Safety factor for real hardware (reduce gains by 35%)
        safety_factor = 0.65
        Kp *= safety_factor
        Ki *= safety_factor
        Kd *= safety_factor
        
        print(f"\n✓ Ziegler-Nichols PID Gains (with 0.65 safety factor):")
        print(f"  Kp: {Kp:.6f}")
        print(f"  Ki: {Ki:.6f}")
        print(f"  Kd: {Kd:.6f}")
        
        return {
            'Ku': Ku,
            'Pu': Pu,
            'Kp': Kp,
            'Ki': Ki,
            'Kd': Kd,
            'samples': len(samples),
            'zero_crossings': zero_crossings if len(samples) >= 5 else 0
        }
    
    def ramp_test(self, duration=4.0):
        """
        Ramp test: slowly sweep motor from min to max
        
        Used to:
        1. Sanity check motor responsiveness
        2. Detect physical limits (endless vs limited)
        3. Measure angle range
        
        Returns:
            dict: {min_angle, max_angle, is_endless, samples, motor_responding}
        """
        print("\n" + "="*70)
        print(f"RAMP TEST: Motor {self.motor_id}")
        print("="*70)
        print(f"Duration: {duration}s, Serial output rate: ~1 Hz")
        print(f"Ramping CC#64: 0 → 127")
        
        samples = []
        start_time = time.time()
        
        # Clear buffer
        self.debug_ser.reset_input_buffer()
        time.sleep(0.2)
        
        # Ramp from 0 to 127 linearly
        ramp_start = time.time()
        while time.time() - ramp_start < duration:
            elapsed = time.time() - ramp_start
            progress = elapsed / duration  # 0.0 to 1.0
            cc_val = int(progress * 127.0)
            cc_val = max(0, min(127, cc_val))  # Clamp to [0, 127]
            
            # Send command
            success = self.send_midi_cc(64, cc_val)
            
            # Read all available samples in this window (works with 1 Hz output)
            lines = self.read_debug_lines_buffered(timeout=0.15)
            for line in lines:
                if "Angle:" in line:
                    try:
                        # Parse angle value
                        angle = None
                        if "rad" in line:
                            parts = line.split("Angle:")
                            if len(parts) > 1:
                                num_str = parts[1].strip().split()[0]
                                angle = float(num_str)
                        
                        if angle is not None:
                            samples.append({
                                'time': time.time() - start_time,
                                'cc_val': cc_val,
                                'angle': angle
                            })
                            if self.debug:
                                print(f"  [RAMP {progress*100:.0f}%] CC#{64} = {cc_val:3d}, Motor angle: {angle:.4f} rad {('✓' if success else '⚠')}")
                    except:
                        pass
        
        if not samples:
            print("✗ No motor response during ramp")
            print("  ⚠️ HARDWARE CHECK REQUIRED:")
            print("    - Is the motor powered?")
            print("    - Is the encoder connected (I2C) and calibrated?")
            print("    - Are motor GPIO pins 13/12/11 (PWM) and 10 (Enable) connected?")
            return None
        
        # Analyze ramp response
        angles = [s['angle'] for s in samples]
        min_angle = min(angles)
        max_angle = max(angles)
        angle_range = max_angle - min_angle
        
        print(f"\n✓ Collected {len(samples)} samples over {duration}s")
        print(f"  Angle range: {min_angle:.3f} → {max_angle:.3f} rad")
        print(f"  Total range: {angle_range:.3f} rad ({angle_range*180/3.14159:.1f}°)")
        
        # Check if motor is actually responding
        motor_responding = angle_range > 0.01  # >0.5° movement indicates motor is working
        if not motor_responding:
            print(f"\n⚠️ MOTOR NOT RESPONDING TO MIDI:")
            print(f"  Angle stayed constant at {min_angle:.4f} rad during ramp")
            print(f"  Check:")
            print(f"    - Motor power supply")
            print(f"    - Encoder connection (I2C address 0x36)")
            print(f"    - Motor driver Enable pin (GPIO 10) is HIGH")
            print(f"    - SimpleFOC motor initialization (check serial output at startup)")
            return None
        
        # Detect if motor has hard limits (endless vs limited)
        # If angle stops changing near the end, it's hitting a hard limit
        is_endless = self._detect_motor_type(samples)
        motor_type = "Endless" if is_endless else "Limited-Range"
        print(f"  Motor type: {motor_type}")
        
        return {
            'min_angle': min_angle,
            'max_angle': max_angle,
            'angle_range': angle_range,
            'is_endless': is_endless,
            'samples': len(samples),
            'motor_responding': True
        }
    
    def _detect_motor_type(self, ramp_samples):
        """
        Analyze ramp response to detect if motor is endless or limited
        
        Logic:
        - Limited motor: angle will plateau (slope → 0) near endpoints
        - Endless motor: angle changes smoothly throughout
        
        Returns:
            bool: True if endless, False if limited-range
        """
        if len(ramp_samples) < 10:
            return True  # Default to endless if insufficient data
        
        # Divide samples into quartiles and compare slope
        quarter = len(ramp_samples) // 4
        
        # First quarter: should have steep slope (motor responding)
        first_quarter = ramp_samples[:quarter]
        first_slope = (first_quarter[-1]['angle'] - first_quarter[0]['angle']) / max(0.001, first_quarter[-1]['time'] - first_quarter[0]['time'])
        
        # Last quarter: if slope is ~0, motor hit limit
        last_quarter = ramp_samples[-quarter:]
        last_slope = abs((last_quarter[-1]['angle'] - last_quarter[0]['angle']) / max(0.001, last_quarter[-1]['time'] - last_quarter[0]['time']))
        
        # If last slope is <5% of first slope, motor is limited
        if last_slope < first_slope * 0.05:
            return False  # Limited range
        
        return True  # Endless
    
    def step_response_test(self, step_size=45.0, settle_time=3.0):
        """
        Perform step response test: measure rise time, overshoot, settling time
        
        Returns:
            dict: {rise_time, overshoot, settling_time, peak}
        """
        print("\n" + "="*70)
        print(f"STEP RESPONSE TEST: Motor {self.motor_id}")
        print("="*70)
        print(f"Step size: {step_size}°, Settling time: {settle_time}s")
        
        samples = []
        start_time = time.time()
        
        # Clear buffer
        self.debug_ser.reset_input_buffer()
        
        # Give steady state baseline
        print("1. Sending step input (0° → baseline)...")
        self.send_midi_cc(64, 50)  # ~50° baseline
        time.sleep(1.0)
        
        # Read baseline
        baseline_samples = []
        for _ in range(50):
            lines = self.read_debug_lines(timeout=0.05)
            for line in lines:
                if "Angle:" in line:
                    try:
                        angle = float(line.split()[1])
                        baseline_samples.append(angle)
                    except:
                        pass
            time.sleep(0.02)
        
        baseline = sum(baseline_samples) / len(baseline_samples) if baseline_samples else 0
        print(f"   Baseline angle: {baseline:.3f} rad ({baseline*180/3.14159:.1f}°)")
        
        # Send step
        print("2. Sending step to target...")
        step_cc = int(50 + (step_size / 180) * 127)  # Convert angle to CC value
        self.send_midi_cc(64, step_cc)
        
        # Collect response
        start_time = time.time()
        step_start = start_time
        
        while time.time() - start_time < settle_time:
            lines = self.read_debug_lines(timeout=0.05)
            for line in lines:
                if "Angle:" in line:
                    try:
                        angle = float(line.split()[1])
                        samples.append({
                            'time': time.time() - step_start,
                            'angle': angle
                        })
                    except:
                        pass
        
        if not samples:
            print("✗ No step response data")
            return None
        
        angles = [s['angle'] for s in samples]
        times = [s['time'] for s in samples]
        
        peak = max(angles)
        final = angles[-1]
        overshoot = ((peak - baseline) - (final - baseline)) / (final - baseline) * 100 if final != baseline else 0
        
        # Find settling time (2% criterion)
        settling_band = abs(final - baseline) * 0.02
        settling_idx = len(angles)
        for i in range(len(angles)-1, -1, -1):
            if abs(angles[i] - final) > settling_band:
                settling_idx = i
                break
        settling_time = times[settling_idx] if settling_idx < len(times) else settle_time
        
        print(f"\n✓ Step Response Results:")
        print(f"  Baseline: {baseline:.3f} rad ({baseline*180/3.14159:.1f}°)")
        print(f"  Final: {final:.3f} rad ({final*180/3.14159:.1f}°)")
        print(f"  Peak: {peak:.3f} rad ({peak*180/3.14159:.1f}°)")
        print(f"  Overshoot: {overshoot:.1f}%")
        print(f"  Settling Time (2%): {settling_time:.2f}s")
        
        # Optional: Capture high-speed dynamics for velocity controller analysis
        print("\n  Monitoring velocity response for controller tuning...")
        vel_stats = self.capture_dynamics_highspeed(duration=2.0)
        if vel_stats:
            print(f"  Velocity controller analysis:")
            print(f"    Measured velocity: {vel_stats['velocity_max']:.4f} rad/s (peak)")
            print(f"    Sample rate: {vel_stats['sample_rate']:.1f} Hz")
        
        return {
            'baseline': baseline,
            'final': final,
            'peak': peak,
            'overshoot': overshoot,
            'settling_time': settling_time,
            'samples': len(samples),
            'velocity_stats': vel_stats
        }
    
    def run_full_calibration(self):
        """Run complete calibration: ramp → relay test → analysis → step response validation"""
        print("\n" + "="*70)
        print("FULL PID CALIBRATION SEQUENCE")
        print("="*70)
        
        # 0. Ramp test (sanity check + limit detection)
        print("\n[Phase 1/3] Sanity Check & Motor Characterization")
        ramp_result = self.ramp_test(duration=4.0)
        if not ramp_result:
            print("\n⚠ Ramp test failed - motor not responding to MIDI")
            print("  Check: MIDI port, motor power, encoder wiring")
            return False
        
        # 1. Relay test (main tuning)
        print(f"\n[Phase 2/3] Ziegler-Nichols Relay Tuning")
        relay_result = self.relay_test(duration=5.0, frequency=1.5)
        if not relay_result:
            print("\n⚠ Relay test inconclusive, using conservative defaults")
            relay_result = {
                'Ku': 2.0,
                'Pu': 1.0,
                'Kp': 0.78,  # 0.6 * 2.0 * 0.65
                'Ki': 1.56,  # 1.2 * 2.0 / 1.0 * 0.65
                'Kd': 0.195, # 3.0 * 2.0 * 1.0 / 40.0 * 0.65
                'samples': 0,
                'zero_crossings': 0
            }
        
        # 2. Step response test (to validate tuning)
        time.sleep(1.0)
        print(f"\n[Phase 3/3] Step Response Validation")
        step_result = self.step_response_test(step_size=45.0, settle_time=2.0)
        
        # Summary
        print("\n" + "="*70)
        print("CALIBRATION SUMMARY")
        print("="*70)
        print("\n✓ Recommended PID Gains:")
        print(f"  Kp = {relay_result['Kp']:.6f}")
        print(f"  Ki = {relay_result['Ki']:.6f}")
        print(f"  Kd = {relay_result['Kd']:.6f}")
        
        if step_result:
            print("\nStep Response Validation:")
            print(f"  Overshoot: {step_result['overshoot']:.1f}% (target: <5%)")
            print(f"  Settling Time: {step_result['settling_time']:.2f}s (target: <1.5s)")
        else:
            print("\n⚠ Step response test skipped")
        
        print("\n" + "="*70)
        print("NEXT STEPS:")
        print("="*70)
        print("\n1. Edit include/pid_config.h and update:")
        print(f"   #define MOTOR0_PID_P  {relay_result['Kp']:.6f}f")
        print(f"   #define MOTOR0_PID_I  {relay_result['Ki']:.6f}f")
        print(f"   #define MOTOR0_PID_D  {relay_result['Kd']:.6f}f")
        print("\n2. Rebuild firmware:")
        print("   platformio run -e pico_1motor_endless")
        print("\n3. Upload:")
        print("   platformio run -e pico_1motor_endless --target upload")
        print("\n4. Test:")
        print("   bash test/run_tests.sh pico_1motor_endless")
        
        print("\n✓ Calibration complete!")
        
        return True


def find_debug_port():
    """Auto-detect debug serial port"""
    env = os.environ.get("DEBUG_PORT")
    if env:
        return env
    
    ports = list_ports.comports()
    candidates = [p.device for p in ports if p.device.startswith('/dev/ttyACM') or p.device.startswith('/dev/ttyUSB')]
    return candidates[0] if candidates else None


def main():
    parser = argparse.ArgumentParser(description='SimpleFOC PID Calibration via Ziegler-Nichols')
    parser.add_argument('--motor', type=int, default=0, help='Motor ID (0 or 1)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--ramp-only', action='store_true', help='[Phase 1] Ramp test only (sanity check + limit detection)')
    parser.add_argument('--relay-only', action='store_true', help='[Phase 2] Relay test only (skip ramp check)')
    parser.add_argument('--step-only', action='store_true', help='[Phase 3] Step response only')
    parser.add_argument('--monitor-only', action='store_true', help='Capture motor dynamics at high speed (no tuning)')
    
    args = parser.parse_args()
    
    debug_port = find_debug_port()
    if not debug_port:
        print("✗ No debug port found. Connect RP2040 and/or set DEBUG_PORT env var")
        sys.exit(1)
    
    print(f"Using debug port: {debug_port}")
    
    calibrator = PIDCalibrator(debug_port, motor_id=args.motor, debug=args.debug)
    
    if not calibrator.connect():
        sys.exit(1)
    
    try:
        if args.ramp_only:
            ramp_result = calibrator.ramp_test(duration=4.0)
            if ramp_result:
                print("\n✓ Ramp test complete")
                print(f"  Motor type: {'Endless' if ramp_result['is_endless'] else 'Limited-Range'}")
            else:
                sys.exit(1)
        elif args.relay_only:
            relay_result = calibrator.relay_test()
            if relay_result:
                print("\n✓ Relay test complete")
            else:
                sys.exit(1)
        elif args.step_only:
            step_result = calibrator.step_response_test()
            if step_result:
                print("\n✓ Step response test complete")
            else:
                sys.exit(1)
        elif args.monitor_only:
            print("\nCapturing high-speed motor dynamics for 5 seconds...")
            vel_stats = calibrator.capture_dynamics_highspeed(duration=5.0)
            if vel_stats:
                print(f"\n✓ Motor Dynamics Summary:")
                print(f"  Sample rate: {vel_stats['sample_rate']:.1f} Hz")
                print(f"  Angle range: {vel_stats['angle_min']:.4f} → {vel_stats['angle_max']:.4f} rad")
                print(f"  Velocity: {vel_stats['velocity_mean']:.4f} rad/s (avg), {vel_stats['velocity_max']:.4f} rad/s (max)")
                print(f"  Duration: {vel_stats['duration']:.2f}s")
            else:
                print("✗ No dynamics data collected")
                sys.exit(1)
        else:
            success = calibrator.run_full_calibration()
            sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        print("\n⊘ Calibration interrupted")
        sys.exit(0)
    
    finally:
        calibrator.close()


if __name__ == '__main__':
    main()
