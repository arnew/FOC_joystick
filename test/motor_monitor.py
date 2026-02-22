#!/usr/bin/env python3
"""
High-Speed Motor Monitor - 100-500 Hz position/velocity tracking

Provides fast serial reading with timestamps for capturing motor dynamics.
Used by both test suite and calibration scripts.
"""

import serial
import time
import re
from collections import deque
from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class MotorSample:
    """Single motor position sample with timing"""
    timestamp: float       # Absolute time since epoch
    time_offset: float    # Time since monitoring started (seconds)
    angle: float          # Motor angle (radians)
    target: float         # Target angle (radians)
    velocity: float       # Estimated velocity (rad/s, computed from samples)


class HighSpeedMonitor:
    """Fast serial reader for motor monitoring at 100+ Hz"""
    
    def __init__(self, serial_port: serial.Serial, buffer_size: int = 500):
        """
        Initialize monitor
        
        Args:
            serial_port: Open serial.Serial connection
            buffer_size: Max samples to retain
        """
        self.ser = serial_port
        self.samples: deque = deque(maxlen=buffer_size)
        self.start_time = None
        self.last_angle = None
        self.last_time = None
    
    def sample_once(self, timeout: float = 0.01) -> Optional[MotorSample]:
        """
        Try to read one angle sample from device
        
        Args:
            timeout: Max time to wait for a line
        
        Returns:
            MotorSample if found, None if timeout or parse error
        """
        if self.start_time is None:
            self.start_time = time.time()
        
        start = time.time()
        while time.time() - start < timeout:
            if self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    
                    # Parse compact format: "A=1.23 T=4.56"
                    # A = angle (radians), T = target (radians)
                    angle_match = re.search(r'A=([\-\d.]+)', line)
                    target_match = re.search(r'T=([\-\d.]+)', line)
                    
                    if angle_match and target_match:
                        current_time = time.time()
                        time_offset = current_time - self.start_time
                        angle = float(angle_match.group(1))
                        target = float(target_match.group(1))
                        
                        # Compute velocity
                        velocity = 0.0
                        if self.last_time is not None and self.last_angle is not None:
                            dt = current_time - self.last_time
                            if dt > 0:
                                velocity = (angle - self.last_angle) / dt
                        
                        self.last_angle = angle
                        self.last_time = current_time
                        
                        sample = MotorSample(
                            timestamp=current_time,
                            time_offset=time_offset,
                            angle=angle,
                            target=target,
                            velocity=velocity
                        )
                        self.samples.append(sample)
                        return sample
                except Exception as e:
                    pass
            
            time.sleep(0.001)
        
        return None
    
    def collect_samples(self, duration: float, target_hz: int = 100) -> List[MotorSample]:
        """
        Collect samples for fixed duration at target frequency
        
        Args:
            duration: How long to sample (seconds)
            target_hz: Target sampling rate (for logging purposes)
        
        Returns:
            List of MotorSample objects
        """
        timeout = 1.0 / target_hz if target_hz > 0 else 0.01
        start = time.time()
        
        while time.time() - start < duration:
            self.sample_once(timeout=timeout)
        
        return list(self.samples)
    
    def reset(self):
        """Clear sample buffer and timing"""
        self.samples.clear()
        self.start_time = None
        self.last_angle = None
        self.last_time = None
    
    def get_stats(self) -> Optional[Dict]:
        """Get statistics from collected samples"""
        if len(self.samples) < 2:
            return None
        
        samples = list(self.samples)
        angles = [s.angle for s in samples]
        velocities = [s.velocity for s in samples]
        times = [s.time_offset for s in samples]
        
        return {
            'count': len(samples),
            'duration': times[-1] - times[0],
            'angle_min': min(angles),
            'angle_max': max(angles),
            'angle_range': max(angles) - min(angles),
            'velocity_mean': sum(velocities) / len(velocities),
            'velocity_max': max(velocities),
            'sample_rate': len(samples) / (times[-1] - times[0]) if times[-1] > times[0] else 0,
        }
    
    def print_samples(self, limit: int = None):
        """Print collected samples"""
        samples = list(self.samples)
        if limit:
            samples = samples[-limit:]
        
        print(f"\n{'Time (s)':>10} {'Angle (rad)':>12} {'Target (rad)':>12} {'Velocity (r/s)':>12}")
        print("-" * 50)
        for sample in samples:
            print(f"{sample.time_offset:10.3f} {sample.angle:12.4f} {sample.target:12.4f} {sample.velocity:12.4f}")


def find_debug_port():
    """Auto-detect RP2040 debug port"""
    from serial.tools import list_ports
    
    ports = list_ports.comports()
    for p in ports:
        if p.device.startswith('/dev/ttyACM') or p.device.startswith('/dev/ttyUSB'):
            return p.device
    return None


if __name__ == '__main__':
    # Demo: Connect and monitor for 5 seconds
    port = find_debug_port()
    if not port:
        print("No debug port found")
        exit(1)
    
    ser = serial.Serial(port, 115200, timeout=1)
    time.sleep(0.5)
    ser.reset_input_buffer()
    
    print(f"Monitoring {port} at 115200 baud...")
    
    monitor = HighSpeedMonitor(ser)
    samples = monitor.collect_samples(duration=5.0, target_hz=100)
    
    print(f"\nCollected {len(samples)} samples")
    stats = monitor.get_stats()
    if stats:
        print(f"Sample rate: {stats['sample_rate']:.1f} Hz")
        print(f"Angle range: {stats['angle_min']:.3f} → {stats['angle_max']:.3f} rad")
        print(f"Velocity range: 0 → {stats['velocity_max']:.3f} rad/s")
    
    monitor.print_samples(limit=10)
    
    ser.close()
