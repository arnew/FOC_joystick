#!/usr/bin/env python3
"""
Dual PID Calibration Script: Angle + Velocity Controllers using Ziegler-Nichols

SimpleFOC uses nested control architecture:
  - Outer loop:  P_angle controller (position) → velocity command
  - Inner loop:  PID_velocity controller (speed) → voltage command

Calibration workflow (both controllers):
1. [Phase 1] Ramp test: Sanity check + motor type detection (endless vs limited)
2. [Phase 2a] Velocity relay tuning: Tune inner loop for smooth speed response
3. [Phase 2b] Angle relay tuning: Tune outer loop for accurate position control
4. [Phase 3] Step response validation: Measure rise time, overshoot & settling
5. Generate both MOTOR0_VELOCITY_* and MOTOR0_PID_* gains

Usage:
    python3 test/calibrate_pid.py                # Full dual-loop calibration
    python3 test/calibrate_pid.py --ramp-only    # [Phase 1] Sanity check only
    python3 test/calibrate_pid.py --velocity-only # [Phase 2a] Velocity controller only
    python3 test/calibrate_pid.py --angle-only    # [Phase 2b] Angle controller only
    python3 test/calibrate_pid.py --step-only     # [Phase 3] Step response only
    python3 test/calibrate_pid.py --monitor-only  # Dynamics capture only
    python3 test/calibrate_pid.py --debug         # Verbose output
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
    
    def relay_test(self, duration=5.0, frequency=2, controller_type='angle'):
        """
        Perform relay tuning: send square wave input, measure response with high-speed monitoring
        
        Args:
            duration: Test duration in seconds
            frequency: Square wave frequency in Hz
            controller_type: 'velocity' for speed tuning or 'angle' for position tuning
        
        Returns:
            dict: {oscillation_freq, peak_amplitude, settling_time} or None if failed
        """
        print("\n" + "="*70)
        print(f"RELAY TEST ({controller_type} controller): Motor {self.motor_id}")
        print("="*70)
        print(f"Duration: {duration}s, Frequency: {frequency} Hz")
        
        if controller_type == 'velocity':
            print("Ramping speed: 0 → 90% → 0 → ...")
            cc_low = 0    # 0% → ~0 rad/s
            cc_high = 90  # 90% → high speed
        else:  # angle
            print("Sending square wave: 25 → 95 → 25 → ... (position pulses)")
            cc_low = 25   # ~10°
            cc_high = 90  # ~75°
        
        samples = []
        start_time = time.time()
        
        # Clear any buffered input
        self.debug_ser.reset_input_buffer()
        time.sleep(0.2)
        
        # Start high-speed monitor
        monitor = HighSpeedMonitor(self.debug_ser)
        
        # Send initial MIDI commands to establish square wave
        print("Initializing square wave...")
        wave_period = 1.0 / frequency
        half_period = wave_period / 2
        
        cc_low = 25   # ~10°
        cc_high = 90  # ~75°
        
        mid_point_time = start_time + duration
        next_send_time = start_time
        cc_val = cc_low
        
        try:
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
                
                # Collect samples continuously (non-blocking)
                sample = monitor.sample_once(timeout=0.01)
                if sample:
                    samples.append({
                        'time': sample.time_offset,
                        'angle': sample.angle
                    })
                    if self.debug:
                        print(f"  [SAMPLE] t={sample.time_offset:.2f}s, angle={sample.angle:.3f} rad")
                
                time.sleep(0.001)  # Small sleep to avoid busy-waiting
        except Exception as e:
            if self.debug:
                print(f"Relay test error: {e}")
        
        if not samples:
            print("✗ No motor response data collected")
            print("  Check:")
            print("  - Device is connected and running")
            print("  - MIDI port is accessible (pygame.midi)")
            print("  - Motor is powered and encoder is working")
            return None
        
        print(f"✓ Collected {len(samples)} samples over {duration}s @{len(samples)/duration:.0f} Hz")
        
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
        Ramp test: slowly sweep motor from min to max using high-speed monitoring
        
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
        print(f"Duration: {duration}s, using high-speed monitoring (100+ Hz)")
        print(f"Ramping CC#64: 0 → 127")
        
        samples = []
        start_time = time.time()
        
        # Clear buffer and start high-speed monitor
        self.debug_ser.reset_input_buffer()
        time.sleep(0.2)
        
        monitor = HighSpeedMonitor(self.debug_ser)
        
        # Ramp from 0 to 127 linearly while monitoring
        ramp_start = time.time()
        try:
            while time.time() - ramp_start < duration:
                elapsed = time.time() - ramp_start
                progress = elapsed / duration  # 0.0 to 1.0
                cc_val = int(progress * 127.0)
                cc_val = max(0, min(127, cc_val))  # Clamp to [0, 127]
                
                # Send command
                success = self.send_midi_cc(64, cc_val)
                
                # Collect one sample if available (non-blocking)
                sample = monitor.sample_once(timeout=0.01)
                if sample:
                    samples.append({
                        'time': sample.time_offset,
                        'cc_val': cc_val,
                        'angle': sample.angle,
                        'velocity': sample.velocity
                    })
                    if self.debug:
                        print(f"  [RAMP {progress*100:.0f}%] CC#{64} = {cc_val:3d}, Angle: {sample.angle:.4f} rad, V: {sample.velocity:.2f} rad/s")
                
                time.sleep(0.01)  # 100 Hz sampling rate
        except Exception as e:
            if self.debug:
                print(f"Monitor error: {e}")
        
        if not samples:
            print("✗ No motor response during ramp")
            print("  ⚠️ HARDWARE CHECK REQUIRED:")
            print("    - Is the motor powered?")
            print("    - Is the encoder connected (I2C) and calibrated?")
            print("    - Are motor GPIO pins 13/12/11 (PWM) and 10 (Enable) connected?")
            return None
        
        # Analyze ramp response
        angles = [s['angle'] for s in samples]
        velocities = [s['velocity'] for s in samples]
        min_angle = min(angles)
        max_angle = max(angles)
        angle_range = max_angle - min_angle
        
        print(f"\n✓ Collected {len(samples)} samples over {duration}s @{len(samples)/duration:.0f} Hz")
        print(f"  Angle range: {min_angle:.3f} → {max_angle:.3f} rad")
        print(f"  Total range: {angle_range:.3f} rad ({angle_range*180/3.14159:.1f}°)")
        if velocities:
            avg_vel = sum(velocities) / len([v for v in velocities if v != 0])
            max_vel = max(velocities)
            print(f"  Velocity: avg={avg_vel:.3f}, max={max_vel:.3f} rad/s")
        
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
    
    def step_response_test(self, step_size=90.0, settle_time=3.0, baseline_cc=64):
        """
        Perform step response test with high-speed monitoring: measure rise time, overshoot, settling time
        AND evaluate tuning quality (steady-state stability, noise, drift)
        
        Args:
            step_size: Step size in degrees (default 90°)
            settle_time: Time to monitor settling in seconds (default 3s)
            baseline_cc: Starting MIDI CC value (0-127, default 64=middle)
        
        Returns:
            dict: {rise_time, overshoot, settling_time, peak, tuning_quality_score, ...}
        """
        print("\n" + "="*70)
        print(f"STEP RESPONSE TEST: Motor {self.motor_id}")
        print("="*70)
        print(f"Step size: {step_size}°, Settling time: {settle_time}s")
        
        samples = []
        
        # Clear buffer and start monitor
        self.debug_ser.reset_input_buffer()
        time.sleep(0.2)
        monitor = HighSpeedMonitor(self.debug_ser)
        
        # Give steady state baseline
        print("1. Sending step input (baseline)...")
        self.send_midi_cc(64, baseline_cc)
        time.sleep(1.0)
        
        # Read baseline (collect 50ms worth of samples)
        baseline_samples = []
        baseline_start = time.time()
        while time.time() - baseline_start < 0.5:
            sample = monitor.sample_once(timeout=0.01)
            if sample:
                baseline_samples.append(sample.angle)
            time.sleep(0.005)
        
        baseline = sum(baseline_samples) / len(baseline_samples) if baseline_samples else 0
        print(f"   Baseline angle: {baseline:.3f} rad ({baseline*180/3.14159:.1f}°) [from CC={baseline_cc}]")
        
        # Send step
        print("2. Sending step to target...")
        step_cc = int(baseline_cc + (step_size / 180) * 127)  # Convert angle to CC value from baseline
        step_cc = max(0, min(127, step_cc))  # Clamp to valid MIDI range
        self.send_midi_cc(64, step_cc)
        
        # Collect response with high-speed monitoring
        step_start = time.time()
        while time.time() - step_start < settle_time:
            sample = monitor.sample_once(timeout=0.01)
            if sample:
                samples.append({
                    'time': sample.time_offset,
                    'angle': sample.angle,
                    'velocity': sample.velocity
                })
            time.sleep(0.001)
        
        if not samples:
            print("✗ No step response data")
            return None
        
        angles = [s['angle'] for s in samples]
        times = [s['time'] for s in samples]
        velocities = [s['velocity'] for s in samples]
        
        peak = max(angles)
        final = angles[-1]
        
        # Calculate overshoot properly handling both positive and negative steps
        step_magnitude = final - baseline
        if abs(step_magnitude) > 0.001:  # Only calculate if step is meaningful
            # Overshoot = amount beyond final position / total step magnitude
            overshoot_amount = peak - final
            # Check if step was in "peak" direction
            if (overshoot_amount > 0 and step_magnitude > 0) or (overshoot_amount < 0 and step_magnitude < 0):
                overshoot = (overshoot_amount / step_magnitude) * 100
            else:
                overshoot = 0  # No overshoot in the problematic direction
        else:
            # No meaningful step
            overshoot = 0
        
        # Find settling time (2% criterion)
        settling_band = abs(final - baseline) * 0.02 if abs(final - baseline) > 0.001 else 0.02
        settling_idx = len(angles)
        for i in range(len(angles)-1, -1, -1):
            if abs(angles[i] - final) > settling_band:
                settling_idx = i
                break
        settling_time_measured = times[settling_idx] if settling_idx < len(times) else settle_time
        
        # Velocity analysis
        vel_filtered = [v for v in velocities if v != 0]
        avg_vel = sum(vel_filtered) / len(vel_filtered) if vel_filtered else 0
        max_vel = max(vel_filtered) if vel_filtered else 0
        
        print(f"\n✓ Step Response Results (collected {len(samples)} samples @{len(samples)/settle_time:.0f} Hz):")
        print(f"  Baseline: {baseline:.3f} rad ({baseline*180/3.14159:.1f}°)")
        print(f"  Final: {final:.3f} rad ({final*180/3.14159:.1f}°)")
        print(f"  Peak: {peak:.3f} rad ({peak*180/3.14159:.1f}°)")
        print(f"  Overshoot: {overshoot:.1f}%")
        print(f"  Settling Time (2%): {settling_time_measured:.2f}s")
        print(f"  Velocity: avg={avg_vel:.4f}, max={max_vel:.4f} rad/s")
        
        # ===== TUNING QUALITY EVALUATION =====
        print("\n3. Measuring Steady-State Stability & Noise...")
        
        # Monitor steady state for additional time to measure noise and drift
        steady_samples = []
        steady_start = time.time()
        steady_duration = 5.0  # Monitor for 5 seconds after step
        target_angle = final
        
        while time.time() - steady_start < steady_duration:
            sample = monitor.sample_once(timeout=0.01)
            if sample:
                steady_samples.append({
                    'time': sample.time_offset,
                    'angle': sample.angle,
                    'error': sample.angle - target_angle
                })
            time.sleep(0.001)
        
        # Calculate steady-state metrics
        if steady_samples:
            steady_angles = [s['angle'] for s in steady_samples]
            steady_errors = [s['error'] for s in steady_samples]
            
            # Drift = how much position changed over time
            drift = steady_angles[-1] - steady_angles[0]
            drift_magnitude = abs(drift)
            
            # Noise = standard deviation of position error  
            if len(steady_errors) > 1:
                mean_error = sum(steady_errors) / len(steady_errors)
                variance = sum((e - mean_error) ** 2 for e in steady_errors) / len(steady_errors)
                noise_stddev = variance ** 0.5
            else:
                noise_stddev = 0.0
            
            # Position stability = how often error exceeded certain threshold
            error_threshold = 0.05  # 0.05 rad = ~2.9°
            unstable_samples = sum(1 for e in steady_errors if abs(e) > error_threshold)
            stability_percentage = 100.0 * (1.0 - unstable_samples / max(1, len(steady_errors)))
            
            print(f"\n✓ Steady-State Stability (monitoring {steady_duration}s after settling):")
            print(f"  Position drift: {drift_magnitude:.4f} rad ({drift_magnitude*180/3.14159:.2f}°)")
            print(f"  Position noise (σ): {noise_stddev:.4f} rad ({noise_stddev*180/3.14159:.2f}°)")
            print(f"  Stability: {stability_percentage:.1f}% (within ±{error_threshold*180/3.14159:.1f}°)")
            
            # Calculate tuning quality score (0-100)
            quality_score = self._calculate_tuning_quality(
                overshoot=overshoot,
                settling_time=settling_time_measured,
                noise=noise_stddev,
                drift=drift_magnitude,
                stability=stability_percentage
            )
            
            result = {
                'baseline': baseline,
                'final': final,
                'peak': peak,
                'overshoot': overshoot,
                'settling_time': settling_time_measured,
                'samples': len(samples),
                'velocity_mean': avg_vel,
                'velocity_max': max_vel,
                'steady_state_drift': drift_magnitude,
                'steady_state_noise': noise_stddev,
                'steady_state_stability': stability_percentage,
                'tuning_quality_score': quality_score,
                'steady_state_samples': len(steady_samples)
            }
            
            # Print tuning quality assessment
            self._print_tuning_quality_report(result)
            
        else:
            print("⚠ Could not measure steady-state stability")
            result = {
                'baseline': baseline,
                'final': final,
                'peak': peak,
                'overshoot': overshoot,
                'settling_time': settling_time_measured,
                'samples': len(samples),
                'velocity_mean': avg_vel,
                'velocity_max': max_vel
            }
        
        return result
    
    def _calculate_tuning_quality(self, overshoot, settling_time, noise, drift, stability):
        """
        Calculate overall tuning quality score (0-100)
        
        Scoring:
        - Overshoot: 0% best (100 pts), >20% worst (0 pts)
        - Settling time: <1s best (100 pts), >5s worst (0 pts)
        - Noise: <0.01 rad best (100 pts), >0.1 rad worst (0 pts)
        - Drift: 0 best (100 pts), >0.2 worst (0 pts)
        - Stability: 100% best (100 pts), <50% worst (0 pts)
        """
        
        # Overshoot score (0-100): 0% = 100 pts, 20%+ = 0 pts
        # Use absolute value since overshoot can be negative on reverse steps
        abs_overshoot = abs(overshoot)
        overshoot_score = max(0, min(100, 100 - (abs_overshoot / 20.0) * 100))
        
        # Settling time score (0-100): <1s = 100 pts, >5s = 0 pts
        if settling_time <= 1.0:
            settling_score = 100
        elif settling_time >= 5.0:
            settling_score = 0
        else:
            settling_score = max(0, 100 - ((settling_time - 1.0) / 4.0) * 100)
        
        # Noise score (0-100): <0.01 rad = 100 pts, >0.1 rad = 0 pts
        if noise <= 0.01:
            noise_score = 100
        elif noise >= 0.1:
            noise_score = 0
        else:
            noise_score = max(0, 100 - ((noise - 0.01) / 0.09) * 100)
        
        # Drift score (0-100): 0 = 100 pts, >0.2 rad = 0 pts
        if drift <= 0.02:  # Allow tiny drift due to encoder noise
            drift_score = 100
        elif drift >= 0.2:
            drift_score = 0
        else:
            drift_score = max(0, 100 - ((drift - 0.02) / 0.18) * 100)
        
        # Stability score (0-100): 100% = 100 pts, 50% = 0 pts (linear scale)
        if stability >= 100:
            stability_score = 100
        elif stability <= 50:
            stability_score = 0
        else:
            stability_score = (stability - 50.0) / 50.0 * 100
        
        # Weighted average (all factors equally important for now)
        overall_score = (overshoot_score + settling_score + noise_score + drift_score + stability_score) / 5.0
        
        return overall_score
    
    def _print_tuning_quality_report(self, result):
        """Print detailed tuning quality assessment and recommendations"""
        
        score = result.get('tuning_quality_score', 0)
        overshoot = result.get('overshoot', 0)
        settling = result.get('settling_time', 0)
        noise = result.get('steady_state_noise', 0)
        drift = result.get('steady_state_drift', 0)
        stability = result.get('steady_state_stability', 100)
        
        print(f"\n" + "="*70)
        print(f"TUNING QUALITY ASSESSMENT")
        print("="*70)
        print(f"Overall Score: {score:.1f}/100.0", end="")
        
        if score >= 80:
            print(" ✅ EXCELLENT")
        elif score >= 60:
            print(" ✓ GOOD")
        elif score >= 40:
            print(" ⚠ FAIR (needs adjustment)")
        else:
            print(" ✗ POOR (major tuning issues)")
        
        print(f"\nBreakdown:")
        print(f"  Overshoot: {overshoot:.1f}% (target: <5%)")
        if overshoot > 20:
            print(f"    → TOO HIGH: Reduce Kp or increase Kd")
        elif overshoot > 10:
            print(f"    → Slightly high: Increase Kd (damping)")
        
        print(f"  Settling Time: {settling:.2f}s (target: <1.5s)")
        if settling > 5.0:
            print(f"    → TOO SLOW: Increase Kp")
        elif settling > 2.0:
            print(f"    → Slow: Slightly increase Kp")
        
        print(f"  Position Noise: {noise*180/3.14159:.2f}° (target: <0.5°)")
        if noise > 0.1:
            print(f"    → HIGH NOISE: Increase Kd, check encoder stability")
        elif noise > 0.05:
            print(f"    → Moderate noise: Increase Kd for damping")
        
        print(f"  Position Drift: {drift*180/3.14159:.2f}° over {result.get('steady_state_samples', 0)} samples")
        if drift > 0.2:
            print(f"    → UNSTABLE: Increase Ki (integral gain) for position holding")
        elif drift > 0.1:
            print(f"    → Slight drift: Increase Ki")
        
        print(f"  Steady-State Stability: {stability:.1f}% (target: >90%)")
        if stability < 70:
            print(f"    → POOR STABILITY: Position not holding - increase Ki and/or Kd")
        elif stability < 85:
            print(f"    → Fair stability: Increase Ki slightly")
        
        # Overall recommendation
        print(f"\n{'='*70}")
        if score < 50:
            print("RECOMMENDATION: Re-run calibration or manually adjust gains:")
            if overshoot > 10 or settling > 2:
                print("  • Inner loop (velocity): Run --velocity-only and increase ultimate gain tuning")
            if drift > 0.1 or stability < 85:
                print("  • Try increasing Ki values to improve position holding")
            if noise > 0.05:
                print("  • Increase Kd values to reduce jitter/noise")
            print("\nIf still unstable after tuning:")
            print("  • Check mechanical coupling for play/backlash")
            print("  • Verify encoder I2C connection and calibration")
            print("  • Ensure motor power supply is stable (no voltage sag)")

    
    def run_full_calibration(self, tune_velocity=True, tune_angle=True):
        """Run complete dual-loop calibration: ramp → velocity relay → angle relay → step response
        
        Args:
            tune_velocity: If True, calibrate velocity controller (inner loop)
            tune_angle: If True, calibrate angle controller (outer loop)
        """
        print("\n" + "="*70)
        print("DUAL-LOOP PID CALIBRATION SEQUENCE (Angle + Velocity)")
        print("="*70)
        
        velocity_result = None
        angle_result = None
        
        # 0. Ramp test (sanity check + limit detection)
        print("\n[Phase 1/4] Sanity Check & Motor Characterization")
        ramp_result = self.ramp_test(duration=4.0)
        if not ramp_result:
            print("\n⚠ Ramp test failed - motor not responding to MIDI")
            print("  Check: MIDI port, motor power, encoder wiring")
            return False
        
        # 1a. Velocity relay test (tune inner loop)
        if tune_velocity:
            print("\n[Phase 2a/4] Velocity Controller Relay Tuning (Inner Loop)")
            print("="*70)
            print("Tuning velocity/speed controller for smooth motion response...")
            velocity_result = self.relay_test(duration=5.0, frequency=3.0, controller_type='velocity')
            if not velocity_result:
                print("\n⚠ Velocity relay test failed")
                velocity_result = None
        
        # 1b. Angle relay test (tune outer loop)
        if tune_angle:
            print("\n[Phase 2b/4] Angle Controller Relay Tuning (Outer Loop)")
            print("="*70)
            print("Tuning angle/position controller for accurate positioning...")
            angle_result = self.relay_test(duration=5.0, frequency=2.0, controller_type='angle')
        
        # 2. Step response test (to validate tuning)
        time.sleep(1.0)
        print(f"\n[Phase 3/4] Step Response Validation")
        step_result = self.step_response_test(step_size=90.0, settle_time=2.0)
        
        # Summary with both controller gains
        print("\n" + "="*70)
        print("CALIBRATION SUMMARY - DUAL LOOP GAINS")
        print("="*70)
        
        if velocity_result:
            print("\n✓ Velocity Controller (Inner Loop) Gains:")
            print(f"  P  = {velocity_result['Kp']:.6f}")
            print(f"  I  = {velocity_result['Ki']:.6f}")
            print(f"  D  = {velocity_result['Kd']:.6f}")
            print(f"  (Period: {velocity_result['Pu']:.3f}s, Ultimate Gain: {velocity_result['Ku']:.3f})")
        else:
            print("\n⚠ Velocity controller tuning skipped - using defaults")
            velocity_result = {'Kp': 0.5, 'Ki': 10.0, 'Kd': 0.0}
        
        if angle_result:
            print("\n✓ Angle Controller (Outer Loop) Gains:")
            print(f"  P  = {angle_result['Kp']:.6f}")
            print(f"  I  = {angle_result['Ki']:.6f}")
            print(f"  D  = {angle_result['Kd']:.6f}")
            print(f"  (Period: {angle_result['Pu']:.3f}s, Ultimate Gain: {angle_result['Ku']:.3f})")
        else:
            print("\n⚠ Angle controller tuning skipped - using defaults")
            angle_result = {'Kp': 20.0, 'Ki': 0.0, 'Kd': 0.5}
        
        if step_result:
            print("\n✓ Step Response Validation:")
            print(f"  Overshoot: {step_result['overshoot']:.1f}% (target: <5%)")
            print(f"  Settling Time: {step_result['settling_time']:.2f}s (target: <1.5s)")
        else:
            print("\n⚠ Step response test skipped")
        
        print("\n" + "="*70)
        print("NEXT STEPS:")
        print("="*70)
        print("\n1. Edit include/pid_config.h and update:")
        print(f"\n   // Velocity Controller (Inner Loop)")
        print(f"   #define MOTOR0_VELOCITY_P  {velocity_result['Kp']:.6f}f")
        print(f"   #define MOTOR0_VELOCITY_I  {velocity_result['Ki']:.6f}f")
        print(f"   #define MOTOR0_VELOCITY_D  {velocity_result['Kd']:.6f}f")
        print(f"\n   // Angle Controller (Outer Loop)")
        print(f"   #define MOTOR0_PID_P  {angle_result['Kp']:.6f}f")
        print(f"   #define MOTOR0_PID_I  {angle_result['Ki']:.6f}f")
        print(f"   #define MOTOR0_PID_D  {angle_result['Kd']:.6f}f")
        print("\n2. Rebuild firmware:")
        print("   platformio run -e pico_1motor_endless")
        print("\n3. Upload:")
        print("   platformio run -e pico_1motor_endless --target upload")
        print("\n4. Test:")
        print("   bash test/run_tests.sh pico_1motor_endless")
        
        print("\n✓ Dual-loop calibration complete!")
        
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
    parser = argparse.ArgumentParser(description='SimpleFOC Dual-Loop PID Calibration (Angle + Velocity)')
    parser.add_argument('--motor', type=int, default=0, help='Motor ID (0 or 1)')
    parser.add_argument('--step-size', type=float, default=90.0, help='Step size in degrees (default 90°)')
    parser.add_argument('--baseline-cc', type=int, default=64, help='Starting MIDI CC value for step test (0-127, default 64=middle)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--ramp-only', action='store_true', help='[Phase 1] Ramp test only')
    parser.add_argument('--velocity-only', action='store_true', help='[Phase 2a] Velocity controller relay test only')
    parser.add_argument('--angle-only', action='store_true', help='[Phase 2b] Angle controller relay test only')
    parser.add_argument('--relay-only', action='store_true', help='Deprecated: use --velocity-only and --angle-only')
    parser.add_argument('--step-only', action='store_true', help='[Phase 3] Step response validation only')
    parser.add_argument('--monitor-only', action='store_true', help='Capture motor dynamics at high speed')
    
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
        elif args.velocity_only:
            vel_result = calibrator.relay_test(duration=5.0, frequency=3.0, controller_type='velocity')
            if vel_result:
                print("\n✓ Velocity relay test complete")
                print(f"  Recommended velocity gains:")
                print(f"    P ={vel_result['Kp']:.6f}")
                print(f"    I ={vel_result['Ki']:.6f}")
                print(f"    D ={vel_result['Kd']:.6f}")
            else:
                sys.exit(1)
        elif args.angle_only:
            ang_result = calibrator.relay_test(duration=5.0, frequency=2.0, controller_type='angle')
            if ang_result:
                print("\n✓ Angle relay test complete")
                print(f"  Recommended angle gains:")
                print(f"    P ={ang_result['Kp']:.6f}")
                print(f"    I ={ang_result['Ki']:.6f}")
                print(f"    D ={ang_result['Kd']:.6f}")
            else:
                sys.exit(1)
        elif args.relay_only:
            print("⚠ --relay-only is deprecated, use --velocity-only and --angle-only")
            sys.exit(1)
        elif args.step_only:
            step_result = calibrator.step_response_test(step_size=args.step_size, baseline_cc=args.baseline_cc)
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
