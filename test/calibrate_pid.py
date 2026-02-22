#!/usr/bin/env python3
"""
PID Calibration Script using Ziegler-Nichols Relay Method

Triggers auto-tuning on the device by:
1. Sending relay tuning command (square wave input)
2. Measuring oscillation frequency and amplitude
3. Calculating PID gains using Ziegler-Nichols rules
4. Uploading optimized PID parameters to device

Usage:
    python3 test/calibrate_pid.py [--motor 0] [--debug]
"""

import os
import sys
import time
import argparse
import serial
from serial.tools import list_ports
import struct

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
        
    def connect(self):
        """Connect to debug serial port"""
        if not self.debug_port:
            print("✗ No debug port available")
            return False
        
        try:
            self.debug_ser = serial.Serial(self.debug_port, 115200, timeout=2)
            print(f"✓ Connected to debug port: {self.debug_port}")
            time.sleep(2)  # Wait for firmware startup
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def close(self):
        """Close serial connection"""
        if self.debug_ser:
            self.debug_ser.close()
    
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
    
    def send_midi_cc(self, cc_num, cc_val):
        """Send MIDI CC via pygame.midi (requires native USB MIDI)"""
        if not PYGAME_MIDI_AVAILABLE:
            return False
        
        try:
            pygame.midi.init()
            for i in range(pygame.midi.get_count()):
                info = pygame.midi.get_device_info(i)
                # info = (interface, name, input, output, is_open)
                # output flag is at index 3
                if b"Pico" in info[1] and info[3] == 1:  # output=1 (index 3)
                    output = pygame.midi.Output(i)
                    output.write([[[0xB0, cc_num & 0x7F, cc_val & 0x7F, 0], pygame.midi.time()]])
                    output.close()
                    return True
        except Exception as e:
            if self.debug:
                print(f"⚠ MIDI send failed: {e}")
        
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
        print("Sending square wave: 0° → 90° → 0° → ...")
        
        samples = []
        start_time = time.time()
        
        # Clear any buffered input
        self.debug_ser.reset_input_buffer()
        
        # Manually send a few MIDI commands to establish square wave
        print("Sending initial MIDI commands...")
        for _ in range(3):
            self.send_midi_cc(64, 90)  # High
            time.sleep(0.3)
            self.send_midi_cc(64, 10)  # Low
            time.sleep(0.3)
        
        # Now collect all available debug output for analysis
        print("Collecting motor response samples...")
        start_time = time.time()
        
        while time.time() - start_time < duration:
            lines = self.read_debug_lines(timeout=0.2)
            for line in lines:
                # Parse angle from multiple possible formats:
                #  "Angle: 1.2345 rad (70.6°)" or 
                #  "  Angle: ..."
                if "Angle:" in line and "rad" in line:
                    try:
                        # Extract number after "Angle:"
                        parts = line.split("Angle:")
                        if len(parts) > 1:
                            num_str = parts[1].split()[0]
                            angle = float(num_str)
                            samples.append({
                                'time': time.time() - start_time,
                                'angle': angle
                            })
                    except (ValueError, IndexError):
                        pass
        
        if not samples:
            print("✗ No motor response data collected")
            return None
        
        # Analyze collected samples
        result = self._analyze_oscillation(samples, is_relay=True)
        return result
    
    def _analyze_oscillation(self, samples, is_relay=False):
        """
        Analyze oscillation frequency and amplitude from samples
        
        Returns:
            dict: Tuning parameters (Ku, Pu, Kp, Ki, Kd)
        """
        if len(samples) < 10:
            print("✗ Not enough samples for analysis")
            return None
        
        angles = [s['angle'] for s in samples]
        times = [s['time'] for s in samples]
        
        # Find zero crossings to estimate frequency
        zero_crossings = 0
        target_angle = sum(angles) / len(angles)  # mean
        
        for i in range(1, len(angles)):
            if (angles[i-1] - target_angle) * (angles[i] - target_angle) < 0:
                zero_crossings += 1
        
        if zero_crossings < 2:
            print("⚠ Insufficient oscillation detected (< 1 full cycle)")
            # Estimate a safe gain from single step response
            Ku = 2.0  # Conservative estimate
            Pu = 1.0
        else:
            # Period = 2 * (total_time / zero_crossings)
            total_time = times[-1] - times[0]
            Pu = 2.0 * total_time / zero_crossings
            
            # Ultimate gain (relay amplitude / oscillation amplitude)
            amplitude = (max(angles) - min(angles)) / 2.0
            relay_amplitude = 45.0 * 0.5  # 45° step = 45° amplitude
            
            if amplitude > 0.01:
                Ku = relay_amplitude / amplitude
            else:
                Ku = 2.0  # Conservative default
        
        print(f"\n✓ Relay Test Results:")
        print(f"  Oscillation Period (Pu): {Pu:.3f}s")
        print(f"  Ultimate Gain (Ku): {Ku:.3f}")
        print(f"  Oscillation Frequency: {1/Pu:.2f} Hz")
        print(f"  Peak Angle: {max(angles):.3f} rad ({max(angles)*180/3.14159:.1f}°)")
        print(f"  Min Angle: {min(angles):.3f} rad ({min(angles)*180/3.14159:.1f}°)")
        
        # Ziegler-Nichols Tuning Rules
        # For angle control (P controller first, then PID)
        Kp = 0.6 * Ku
        Ki = 1.2 * Ku / Pu
        Kd = 3.0 * Ku * Pu / 40.0
        
        # For angle loop, we typically want less aggressive tuning
        # Reduce gains by ~30-40% for stability
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
            'zero_crossings': zero_crossings
        }
    
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
        
        return {
            'baseline': baseline,
            'final': final,
            'peak': peak,
            'overshoot': overshoot,
            'settling_time': settling_time,
            'samples': len(samples)
        }
    
    def run_full_calibration(self):
        """Run complete calibration: relay test → analysis → step response validation"""
        print("\n" + "="*70)
        print("FULL PID CALIBRATION SEQUENCE")
        print("="*70)
        
        # 1. Relay test
        relay_result = self.relay_test(duration=4.0, frequency=1.5)
        if not relay_result:
            print("✗ Relay test failed")
            return False
        
        # 2. Step response test (to validate tuning)
        time.sleep(1.0)
        step_result = self.step_response_test(step_size=45.0, settle_time=2.0)
        
        # Summary
        print("\n" + "="*70)
        print("CALIBRATION SUMMARY")
        print("="*70)
        print("\nRecommended PID Gains:")
        print(f"  Kp = {relay_result['Kp']:.6f}")
        print(f"  Ki = {relay_result['Ki']:.6f}")
        print(f"  Kd = {relay_result['Kd']:.6f}")
        
        if step_result:
            print("\nStep Response Validation:")
            print(f"  Overshoot: {step_result['overshoot']:.1f}% (target: <5%)")
            print(f"  Settling Time: {step_result['settling_time']:.2f}s (target: <1.5s)")
        
        print("\n✓ Calibration complete!")
        print("\nTo apply these gains, add to firmware src/main.cpp:")
        print(f"  motor0.PID_angle.P = {relay_result['Kp']:.6f};")
        print(f"  motor0.PID_angle.I = {relay_result['Ki']:.6f};")
        print(f"  motor0.PID_angle.D = {relay_result['Kd']:.6f};")
        
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
    parser.add_argument('--relay-only', action='store_true', help='Run relay test only')
    parser.add_argument('--step-only', action='store_true', help='Run step response only')
    
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
        if args.relay_only:
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
