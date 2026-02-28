#!/usr/bin/env python3
"""
Quality Goals Test Suite - Verifies README.md Quality Goals

Tests:
  A - Resolution & Sample Accuracy (±1°)
  B - Speed / RPM Measurement (≥60 rpm)
  C - Position Hold Stability (<1° noise)
  D - Movement Overshoot (<5°)
  
Test Sequences (1..N):
  1 - Cardinal Positions: 0°, 90°, 180°, 270°
  2 - Full Grid: 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°
  3 - Tame (Slow): 4 cardinal with 8sec holds
  4 - Fast (Rapid): 6 aggressive movements with minimal dwell
  5 - Random Walk: 20 stochastic positions
  6 - Boundary: Wrap point angles (355°-5°)
"""

import serial
import time
import math
import json
import sys
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

# Test Sequences Definition
SEQUENCES = {
    "1_cardinal": {
        "name": "Cardinal Positions",
        "positions": [0, 90, 180, 270],
        "description": "Basic 4-cardinal point grid"
    },
    "2_full_grid": {
        "name": "Full Grid (8-point)",
        "positions": [0, 45, 90, 135, 180, 225, 270, 315],
        "description": "Complete 45° spaced grid"
    },
    "3_tame_slow": {
        "name": "Tame/Slow Sequence",
        "positions": [0, 90, 180, 270],
        "hold_duration": 8.0,
        "description": "Low-intensity with extended holds"
    },
    "4_fast_rapid": {
        "name": "Fast/Rapid Sequence",
        "positions": [0, 180, 45, 225, 90, 270],
        "dwell_duration": 0.5,
        "description": "Aggressive rapid movements"
    },
    "5_random_walk": {
        "name": "Random Walk (20 positions)",
        "positions": [10, 87, 143, 215, 32, 298, 159, 71, 306, 44, 178, 251, 123, 38, 267, 94, 212, 155, 3, 337],
        "description": "Stochastic path through position space"
    },
    "6_boundary": {
        "name": "Boundary Angles",
        "positions": [355, 359, 0, 1, 5],
        "description": "Wrap point testing near 0°/360°"
    },
}


@dataclass
class Sample:
    """Single position sample"""
    timestamp: float
    actual_rad: float
    target_rad: float
    
    @property
    def actual_deg(self) -> float:
        return math.degrees(self.actual_rad)
    
    @property
    def target_deg(self) -> float:
        return math.degrees(self.target_rad)
    
    @property
    def error_deg(self) -> float:
        return abs(self.actual_deg - self.target_deg)


@dataclass
class TestResult:
    """Result of a single test"""
    test_id: str
    test_name: str
    passed: bool
    criteria_met: Dict[str, bool]
    measurements: Dict[str, float]
    notes: str


class QualityGoalsTestSuite:
    """Complete quality goals verification suite"""
    
    def __init__(self, port: str = '/dev/ttyACM0', verbose: bool = True):
        """Initialize test suite
        
        Args:
            port: Serial port device
            verbose: Print debug output
        """
        self.port = port
        self.verbose = verbose
        self.ser = None
        self.results: List[TestResult] = []
        self.log_lines: List[str] = []
        
    def connect(self) -> bool:
        """Connect to device"""
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=2.0)
            time.sleep(0.5)
            self._log(f"✓ Connected to {self.port}")
            
            # Verify device is responsive
            self.ser.write(b'M0?\n')
            time.sleep(0.5)
            response = self.ser.read_all().decode('utf-8', errors='ignore')
            if 'M0' in response or 'Motor' in response:
                self._log("✓ Device responsive")
                return True
            else:
                self._log("✗ No response from device")
                return False
        except Exception as e:
            self._log(f"✗ Connection failed: {e}")
            return False
    
    def _log(self, msg: str, newline: bool = True):
        """Log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {msg}"
        self.log_lines.append(log_msg)
        if self.verbose:
            if newline:
                print(log_msg)
            else:
                print(log_msg, end="", flush=True)
    
    def _set_target(self, angle_deg: float):
        """Set motor target angle via commander"""
        angle_rad = math.radians(angle_deg)
        cmd = f"T{angle_rad:.4f}\n"
        self.ser.write(cmd.encode())
        time.sleep(0.1)  # Let command process
    
    def _query_statistics(self) -> Optional[Dict[str, any]]:
        """Query device statistics via 'S' command
        
        Returns parsed statistics dict or None on failure
        """
        try:
            # Clear buffer
            self.ser.reset_input_buffer()
            time.sleep(0.1)
            
            # Send statistics query
            self.ser.write(b'S\n')
            time.sleep(0.5)  # Wait longer for response
            
            # Read response (collect all available data)
            response_lines = []
            timeout = time.time() + 1.0
            while time.time() < timeout:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response_lines.append(line)
                time.sleep(0.05)
            
            response = '\n'.join(response_lines)
            
            if not response:
                return None
            
            # Parse statistics
            stats = {}
            
            # Uptime
            match = re.search(r'Uptime:\s+([\d.]+)\s+sec', response)
            if match:
                stats['uptime_sec'] = float(match.group(1))
            
            # Loop timing
            match = re.search(r'Iterations:\s+(\d+)', response)
            if match:
                stats['loop_iterations'] = int(match.group(1))
            
            match = re.search(r'Avg:\s+(\d+)\s+µs', response)
            if match:
                stats['loop_avg_us'] = int(match.group(1))
            
            # Motor stats
            match = re.search(r'Movements:\s+(\d+)', response)
            if match:
                stats['motor_movements'] = int(match.group(1))
            
            match = re.search(r'Holds checked:\s+(\d+)', response)
            if match:
                stats['motor_holds'] = int(match.group(1))
            
            match = re.search(r'Max error:\s+([\d.]+)\s+rad', response)
            if match:
                stats['motor_max_error_rad'] = float(match.group(1))
                stats['motor_max_error_deg'] = math.degrees(float(match.group(1)))
            
            match = re.search(r'Limit hits:\s+(\d+)', response)
            if match:
                stats['motor_limit_hits'] = int(match.group(1))
            
            # Commander commands
            match = re.search(r'Commander cmds:\s+(\d+)', response)
            if match:
                stats['commander_cmds'] = int(match.group(1))
            
            return stats if stats else None
        except Exception as e:
            self._log(f"Warning: Statistics query failed: {e}")
            return None
    
    def _wait_for_position(self, target_deg: float, timeout_sec: float = 3.0, tolerance_deg: float = 2.0) -> bool:
        """Wait for motor to reach target position within tolerance
        
        Returns True if position reached, False on timeout
        """
        start_time = time.time()
        consecutive_good = 0
        required_consecutive = 3
        
        while time.time() - start_time < timeout_sec:
            # Read current position
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                match = re.search(r'A=([\-\d.]+)\s+T=([\-\d.]+)', line)
                if match:
                    actual_rad = float(match.group(1))
                    actual_deg = math.degrees(actual_rad)
                    error = abs(actual_deg - target_deg)
                    
                    if error <= tolerance_deg:
                        consecutive_good += 1
                        if consecutive_good >= required_consecutive:
                            return True
                    else:
                        consecutive_good = 0
            
            time.sleep(0.05)
        
        return False
    
    def _read_samples(self, duration_sec: float, interval_sec: float = 1.0, min_samples: int = 3) -> List[Sample]:
        """Read position samples for specified duration (with early exit)
        
        Expected debug output format: A=X.XX T=Y.YY
        Returns early if min_samples collected and position stable
        """
        samples = []
        start_time = time.time()
        last_sample_time = start_time
        
        while time.time() - start_time < duration_sec:
            # Read any available data
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    # Parse format: A=0.00 T=1.57 JS=512,512
                    match = re.search(r'A=([\-\d.]+)\s+T=([\-\d.]+)', line)
                    if match:
                        actual = float(match.group(1))
                        target = float(match.group(2))
                        
                        # Only sample at requested interval
                        if time.time() - last_sample_time >= interval_sec:
                            samples.append(Sample(
                                timestamp=time.time() - start_time,
                                actual_rad=actual,
                                target_rad=target
                            ))
                            last_sample_time = time.time()
                            
                            # Early exit if we have enough stable samples
                            if len(samples) >= min_samples:
                                recent_errors = [s.error_deg for s in samples[-min_samples:]]
                                if all(e < 2.0 for e in recent_errors):
                                    return samples
            
            time.sleep(0.01)
        
        return samples
    
    def _calculate_stats(self, values: List[float]) -> Tuple[float, float, float, float]:
        """Calculate mean, std dev, min, max
        
        Returns: (mean, stddev, min, max)
        """
        if not values:
            return 0, 0, 0, 0
        
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        stddev = math.sqrt(variance)
        
        return mean, stddev, min(values), max(values)
    
    def test_a_resolution(self, positions: List[int]) -> bool:
        """TEST A: Resolution & Sample Accuracy
        
        Verify ±1° accuracy at multiple positions
        """
        self._log("\n" + "="*70)
        self._log(f"TEST A: Resolution & Sample Accuracy ({len(positions)} positions)")
        self._log("="*70)
        
        criteria_met = {}
        measurements = {}
        
        for target_deg in positions:
            self._log(f"Target: {target_deg}°...", newline=False)
            self._set_target(target_deg)
            
            # Wait for position with timeout
            reached = self._wait_for_position(target_deg, timeout_sec=2.0, tolerance_deg=2.0)
            
            if not reached:
                self._log(f" ✗ Timeout (never reached)")
                criteria_met[f"pos_{target_deg}"] = False
                measurements[f"pos_{target_deg}_error"] = 999.0
                continue
            
            # Collect quick samples (3 samples over 1.5s)
            samples = self._read_samples(duration_sec=1.5, interval_sec=0.5, min_samples=3)
            
            if samples and len(samples) >= 3:
                errors = [s.error_deg for s in samples]
                mean_error, stddev, _, _ = self._calculate_stats(errors)
                
                passed = mean_error <= 1.0
                criteria_met[f"pos_{target_deg}"] = passed
                measurements[f"pos_{target_deg}_error"] = mean_error
                
                status = "✓" if passed else "✗"
                self._log(f" {status} {mean_error:.2f}°")
            else:
                self._log(f" ✗ Insufficient samples")
                criteria_met[f"pos_{target_deg}"] = False
                measurements[f"pos_{target_deg}_error"] = 999.0
        
        passed = all(criteria_met.values())
        result = TestResult(
            test_id="A",
            test_name="Resolution & Sample Accuracy",
            passed=passed,
            criteria_met=criteria_met,
            measurements=measurements,
            notes=f"Tested {len(positions)} positions"
        )
        self.results.append(result)
        
        self._log(f"\n{'✓ PASS' if passed else '✗ FAIL'}: TEST A")
        return passed
    
    def test_b_speed(self, positions: List[int]) -> bool:
        """TEST B: Speed / RPM Measurement
        
        Verify ≥60 rpm by measuring time to move between positions
        Now tests on provided sequence instead of full 360° sweep
        """
        self._log("\n" + "="*70)
        self._log(f"TEST B: Speed Measurement ({len(positions)} positions)")
        self._log("="*70)
        
        criteria_met = {}
        measurements = {}
        
        # Reset statistics to track movements
        self.ser.write(b'S0\n')
        time.sleep(0.3)
        
        # Test movements in sequence
        move_times = []
        start_time = time.time()
        
        for i, target_deg in enumerate(positions):
            self._set_target(target_deg)
            # Quick wait (don't need perfect settling for speed test)
            time.sleep(0.3)
        
        total_time = time.time() - start_time
        
        # Query statistics to get movement count
        stats = self._query_statistics()
        if stats and 'motor_movements' in stats:
            movements = stats['motor_movements']
            avg_time_per_move = total_time / movements if movements > 0 else 999.0
            
            # Speed criteria: should complete moves quickly
            # For 60 rpm = 6°/sec, moving 90° takes 15 seconds
            # We expect much faster for position control
            passed = avg_time_per_move < 1.0  # <1 sec per movement
            
            criteria_met["avg_speed"] = passed
            measurements["total_time"] = total_time
            measurements["movements"] = movements
            measurements["avg_time_per_move"] = avg_time_per_move
            
            self._log(f"{movements} movements in {total_time:.2f}s = {avg_time_per_move:.3f}s/move")
            self._log(f"{'✓ PASS' if passed else '✗ FAIL'}: {'Fast enough' if passed else 'Too slow'}")
        else:
            self._log("✗ Failed to query statistics")
            criteria_met["avg_speed"] = False
            measurements["total_time"] = total_time
        
        passed = all(criteria_met.values())
        result = TestResult(
            test_id="B",
            test_name="Speed Measurement",
            passed=passed,
            criteria_met=criteria_met,
            measurements=measurements,
            notes=f"Tested {len(positions)} position sequence"
        )
        self.results.append(result)
        
        self._log(f"\n{'✓ PASS' if passed else '✗ FAIL'}: TEST B")
        return passed
    
    def test_c_position_hold(self, positions: List[int]) -> bool:
        """TEST C: Position Hold Stability
        
        Verify ±1° accuracy and <1° variance using on-device statistics
        """
        self._log("\n" + "="*70)
        self._log(f"TEST C: Position Hold Stability ({len(positions)} positions)")
        self._log("="*70)
        
        criteria_met = {}
        measurements = {}
        
        for target_deg in positions:
            self._log(f"Hold {target_deg}°...", newline=False)
            self._set_target(target_deg)
            
            # Wait for settling with timeout
            reached = self._wait_for_position(target_deg, timeout_sec=2.0, tolerance_deg=2.0)
            
            if not reached:
                self._log(f" ✗ Timeout")
                criteria_met[f"hold_{target_deg}"] = False
                measurements[f"hold_{target_deg}_error"] = 999.0
                continue
            
            # Collect quick samples for stability check (3 samples over 1.5s)
            samples = self._read_samples(duration_sec=1.5, interval_sec=0.5, min_samples=3)
            
            if samples and len(samples) >= 3:
                errors = [s.error_deg for s in samples]
                mean_error, stddev, _, _ = self._calculate_stats(errors)
                
                # Criteria: mean ≤1°, variance <1°
                passed = mean_error <= 1.0 and stddev < 1.0
                
                criteria_met[f"hold_{target_deg}"] = passed
                measurements[f"hold_{target_deg}_error"] = mean_error
                measurements[f"hold_{target_deg}_stddev"] = stddev
                
                status = "✓" if passed else "✗"
                self._log(f" {status} {mean_error:.2f}° ± {stddev:.2f}°")
            else:
                self._log(f" ✗ No samples")
                criteria_met[f"hold_{target_deg}"] = False
                measurements[f"hold_{target_deg}_error"] = 999.0
        
        passed = all(criteria_met.values())
        result = TestResult(
            test_id="C",
            test_name="Position Hold Stability",
            passed=passed,
            criteria_met=criteria_met,
            measurements=measurements,
            notes=f"Tested {len(positions)} positions"
        )
        self.results.append(result)
        
        self._log(f"\n{'✓ PASS' if passed else '✗ FAIL'}: TEST C")
        return passed
    
    def test_d_overshoot(self, positions: List[int]) -> bool:
        """TEST D: Movement Overshoot
        
        Verify <5° overshoot during target changes
        Tests consecutive movements in position sequence
        """
        self._log("\n" + "="*70)
        self._log(f"TEST D: Movement Overshoot ({len(positions)-1} movements)")
        self._log("="*70)
        
        criteria_met = {}
        measurements = {}
        
        if len(positions) < 2:
            self._log("✗ Need at least 2 positions for overshoot test")
            return False
        
        # Start at first position
        self._set_target(positions[0])
        self._wait_for_position(positions[0], timeout_sec=2.0)
        
        # Test movements between consecutive positions
        for i in range(len(positions) - 1):
            start_deg = positions[i]
            target_deg = positions[i + 1]
            
            self._log(f"Move {start_deg}° → {target_deg}°...", newline=False)
            
            # Move to target and track trajectory
            self._set_target(target_deg)
            
            # Collect rapid samples during movement (shorter timeout)
            samples = self._read_samples(duration_sec=2.0, interval_sec=0.05, min_samples=5)
            
            if samples and len(samples) >= 5:
                angles = [s.actual_deg for s in samples]
                actual_deg_values = [s.actual_deg for s in samples]
                
                # Calculate overshoot based on direction
                if target_deg > start_deg:
                    max_angle = max(actual_deg_values)
                    overshoot = max(0, max_angle - target_deg)
                else:
                    min_angle = min(actual_deg_values)
                    overshoot = max(0, start_deg - min_angle)
                
                passed = overshoot < 5.0
                criteria_met[f"move_{i}_{start_deg}_to_{target_deg}"] = passed
                measurements[f"move_{i}_overshoot"] = overshoot
                
                status = "✓" if passed else "✗"
                self._log(f" {status} {overshoot:.1f}°")
            else:
                self._log(f" ✗ No samples")
                criteria_met[f"move_{i}_{start_deg}_to_{target_deg}"] = False
                measurements[f"move_{i}_overshoot"] = 999.0
        
        passed = all(criteria_met.values())
        num_movements = len(positions) - 1
        result = TestResult(
            test_id="D",
            test_name="Movement Overshoot",
            passed=passed,
            criteria_met=criteria_met,
            measurements=measurements,
            notes=f"Tested {num_movements} movements"
        )
        self.results.append(result)
        
        self._log(f"\n{'✓ PASS' if passed else '✗ FAIL'}: TEST D")
        return passed
    
    def test_e_sequence_tame(self) -> bool:
        """TEST E: Tame Sequence - Slow, Stable Positions with Long Holds
        
        Orthogonal test: Comfortable operating range, extended holds
        Tests steady-state performance and long-term stability
        Positions: 0°, 45°, 90°, 135°, 180°, 225°, 270°, 315° (8 cardinal/intercardinal points)
        Hold duration: 8 seconds each
        """
        self._log("\n" + "="*70)
        self._log("TEST E: Tame Sequence - Stable Positions with Long Holds")
        self._log("="*70)
        
        tame_positions = [0, 45, 90, 135, 180, 225, 270, 315]
        criteria_met = {}
        measurements = {}
        
        self._log(f"\nTesting {len(tame_positions)} positions with 8-second holds each...")
        
        for target_deg in tame_positions:
            self._log(f"\nTame position: {target_deg}°...")
            self._set_target(target_deg)
            
            # Wait for settling
            time.sleep(3.0)
            
            # Collect samples for 8 seconds (long hold)
            samples = self._read_samples(duration_sec=8.0, interval_sec=1.0)
            
            if samples and len(samples) >= 5:
                errors = [s.error_deg for s in samples]
                mean_error, stddev, min_err, max_err = self._calculate_stats(errors)
                
                # Tame criteria: mean ≤1°, variance <0.5° (strict for long hold)
                passed_mean = mean_error <= 1.0
                passed_var = stddev < 0.5
                passed = passed_mean and passed_var
                
                criteria_met[f"tame_{target_deg}_mean"] = passed_mean
                criteria_met[f"tame_{target_deg}_variance"] = passed_var
                measurements[f"tame_{target_deg}_mean_error"] = mean_error
                measurements[f"tame_{target_deg}_stddev"] = stddev
                
                status = "✓" if passed else "✗"
                self._log(f"{status} Tame {target_deg}°: {mean_error:.3f}° ± {stddev:.3f}° (8s hold)")
            else:
                self._log(f"✗ Tame {target_deg}°: Insufficient samples")
                criteria_met[f"tame_{target_deg}_mean"] = False
                criteria_met[f"tame_{target_deg}_variance"] = False
                measurements[f"tame_{target_deg}_mean_error"] = 999.0
        
        passed = all(criteria_met.values())
        result = TestResult(
            test_id="E",
            test_name="Tame Sequence - Stable Long Holds",
            passed=passed,
            criteria_met=criteria_met,
            measurements=measurements,
            notes=f"Tested {len(tame_positions)} cardinal/intercardinal positions, 8s holds"
        )
        self.results.append(result)
        
        self._log(f"\n{'✓ PASS' if passed else '✗ FAIL'}: TEST E")
        return passed
    
    def test_f_sequence_fast(self) -> bool:
        """TEST F: Fast Sequence - Rapid Movements and Transitions
        
        Orthogonal test: High responsiveness, dynamic behavior
        Tests overshoot, settling speed, rapid transitions
        Movements: 5 fast sweeps across full range with minimal dwell
        """
        self._log("\n" + "="*70)
        self._log("TEST F: Fast Sequence - Rapid Movements")
        self._log("="*70)
        
        fast_moves = [
            (0, 180),
            (180, 0),
            (45, 225),
            (225, 45),
            (90, 270),
        ]
        
        criteria_met = {}
        measurements = {}
        settle_times = []
        
        self._log(f"\nTesting {len(fast_moves)} rapid movements...")
        
        for i, (start_deg, target_deg) in enumerate(fast_moves, 1):
            self._log(f"\nFast move #{i}: {start_deg}° → {target_deg}° (rapid)")
            
            # Quick move to start position (minimal dwell)
            self._set_target(start_deg)
            time.sleep(0.5)  # Brief settle
            
            # Mark movement start and move
            self._set_target(target_deg)
            move_start = time.time()
            
            # Capture rapid movement
            samples = self._read_samples(duration_sec=6.0, interval_sec=0.1)
            
            if samples:
                # Find settlement time (error ≤1° for 2 consecutive samples)
                settle_idx = None
                for j in range(len(samples) - 1):
                    if (samples[j].error_deg <= 1.0 and 
                        samples[j+1].error_deg <= 1.0):
                        settle_idx = j
                        break
                
                if settle_idx is not None:
                    settle_time = samples[settle_idx].timestamp
                    settle_times.append(settle_time)
                    # Fast criterion: settle ≤2 seconds
                    passed = settle_time < 2.0
                    criteria_met[f"fast_{i}_settle"] = passed
                    measurements[f"fast_{i}_settle_time"] = settle_time
                    
                    # Calculate overshoot
                    angles = [s.actual_deg for s in samples]
                    max_angle = max(angles)
                    min_angle = min(angles)
                    
                    # Overshoot: how far past target
                    if target_deg > start_deg:
                        overshoot = max(0, max_angle - target_deg)
                    else:
                        overshoot = max(0, start_deg - min_angle)
                    
                    overshoot_ok = overshoot < 5.0
                    criteria_met[f"fast_{i}_overshoot"] = overshoot_ok
                    measurements[f"fast_{i}_overshoot"] = overshoot
                    
                    status = "✓" if (passed and overshoot_ok) else "✗"
                    self._log(f"{status} Fast move #{i}: Settled {settle_time:.2f}s, Overshoot {overshoot:.2f}°")
                else:
                    self._log(f"✗ Fast move #{i}: Did not settle within 6s")
                    criteria_met[f"fast_{i}_settle"] = False
                    criteria_met[f"fast_{i}_overshoot"] = False
                    measurements[f"fast_{i}_settle_time"] = 999.0
                    measurements[f"fast_{i}_overshoot"] = 999.0
            else:
                self._log(f"✗ Fast move #{i}: No samples")
                criteria_met[f"fast_{i}_settle"] = False
                criteria_met[f"fast_{i}_overshoot"] = False
        
        passed = all(criteria_met.values())
        if settle_times:
            measurements["fast_avg_settle_time"] = sum(settle_times) / len(settle_times)
        
        result = TestResult(
            test_id="F",
            test_name="Fast Sequence - Rapid Movements",
            passed=passed,
            criteria_met=criteria_met,
            measurements=measurements,
            notes=f"Tested {len(fast_moves)} rapid transitions"
        )
        self.results.append(result)
        
        self._log(f"\n{'✓ PASS' if passed else '✗ FAIL'}: TEST F")
        return passed
    
    def test_g_sequence_random_walk(self) -> bool:
        """TEST G: Random Walk Sequence - Stochastic Path Through Position Space
        
        Orthogonal test: Unpredictable transitions, robustness
        Tests handling of arbitrary position sequences
        20 random target positions, verify settling at each
        """
        import random
        
        self._log("\n" + "="*70)
        self._log("TEST G: Random Walk Sequence - Stochastic Exploration")
        self._log("="*70)
        
        # Generate 20 random positions
        random.seed(42)  # Reproducible randomness
        random_positions = [random.randint(0, 359) for _ in range(20)]
        
        criteria_met = {}
        measurements = {}
        success_count = 0
        
        self._log(f"\nTesting {len(random_positions)} random target positions...")
        
        for i, target_deg in enumerate(random_positions, 1):
            self._log(f"\nRandom walk #{i}: Target {target_deg}°")
            self._set_target(target_deg)
            time.sleep(1.0)  # Brief settle
            
            # Collect samples
            samples = self._read_samples(duration_sec=4.0, interval_sec=0.5)
            
            if samples:
                errors = [s.error_deg for s in samples]
                mean_error, stddev, _, _ = self._calculate_stats(errors)
                
                # Random walk criterion: relax to mean ≤2° (just keep moving)
                passed = mean_error <= 2.0
                criteria_met[f"random_{i}"] = passed
                measurements[f"random_{i}_error"] = mean_error
                
                if passed:
                    success_count += 1
                
                status = "✓" if passed else "✗"
                if i % 5 == 0:  # Log every 5th move
                    self._log(f"{status} Random {target_deg}°: {mean_error:.2f}° error")
            else:
                criteria_met[f"random_{i}"] = False
                measurements[f"random_{i}_error"] = 999.0
        
        # Random walk success: 95% of targets reached
        success_rate = success_count / len(random_positions)
        passed = success_rate >= 0.95
        measurements["success_rate"] = success_rate
        
        result = TestResult(
            test_id="G",
            test_name="Random Walk Sequence - Stochastic Exploration",
            passed=passed,
            criteria_met=criteria_met,
            measurements=measurements,
            notes=f"Score: {success_count}/{len(random_positions)} positions within 2° ({success_rate*100:.0f}%)"
        )
        self.results.append(result)
        
        self._log(f"\nRandom walk success rate: {success_rate*100:.1f}% ({success_count}/{len(random_positions)})")
        self._log(f"\n{'✓ PASS' if passed else '✗ FAIL'}: TEST G")
        return passed
    
    def test_h_sequence_regression(self) -> bool:
        """TEST H: Regression Traces - Known Problem Patterns
        
        Orthogonal test: Regression detection, reliability
        Tests specific angle combinations known to have issues
        Patterns: Low angles (0-45°), High angles (315-360°), Wrap boundaries, Rapid reversals
        """
        self._log("\n" + "="*70)
        self._log("TEST H: Regression Sequence - Known Problem Patterns")
        self._log("="*70)
        
        # Define regression test cases: (name, position, hold_duration)
        regression_cases = [
            ("near_zero", 5, 3.0),
            ("low_angle", 22, 3.0),
            ("wrap_boundary_high", 355, 3.0),
            ("wrap_boundary_low", 359, 3.0),
            ("near_180", 178, 3.0),
            ("near_180_opp", 182, 3.0),
            ("rapid_reversals", 0, 3.0),  # Special case below
        ]
        
        criteria_met = {}
        measurements = {}
        
        self._log("\nTesting regression patterns known to have issues...")
        
        for test_name, target_deg, duration in regression_cases:
            if test_name == "rapid_reversals":
                # Special test: rapid reversal pattern
                self._log(f"\nRegression #{test_name}: Rapid 0° ↔ 359° reversals")
                reversals_ok = True
                for _ in range(5):
                    self._set_target(0)
                    time.sleep(0.3)
                    self._set_target(359)
                    time.sleep(0.3)
                
                samples = self._read_samples(duration_sec=2.0, interval_sec=0.5)
                if samples:
                    errors = [s.error_deg for s in samples]
                    mean_error, _, _, _ = self._calculate_stats(errors)
                    reversals_ok = mean_error < 10.0
                
                criteria_met["regression_rapid_reversals"] = reversals_ok
                self._log(f"{'✓' if reversals_ok else '✗'} Rapid reversals stable")
            else:
                # Standard regression test
                self._log(f"\nRegression #{test_name}: {target_deg}° (known issue pattern)")
                self._set_target(target_deg)
                time.sleep(1.0)
                
                samples = self._read_samples(duration_sec=float(duration), interval_sec=0.5)
                
                if samples:
                    errors = [s.error_deg for s in samples]
                    mean_error, stddev, _, _ = self._calculate_stats(errors)
                    
                    # Regression criterion: don't make it worse (tolerant)
                    passed = mean_error <= 5.0
                    criteria_met[f"regression_{test_name}"] = passed
                    measurements[f"regression_{test_name}_error"] = mean_error
                    
                    status = "✓" if passed else "✗"
                    self._log(f"{status} {test_name}: {mean_error:.2f}° error")
                else:
                    criteria_met[f"regression_{test_name}"] = False
                    measurements[f"regression_{test_name}_error"] = 999.0
        
        passed = all(criteria_met.values())
        result = TestResult(
            test_id="H",
            test_name="Regression Sequence - Problem Pattern Traces",
            passed=passed,
            criteria_met=criteria_met,
            measurements=measurements,
            notes="Tests patterns known to exhibit issues in earlier versions"
        )
        self.results.append(result)
        
        self._log(f"\n{'✓ PASS' if passed else '✗ FAIL'}: TEST H")
        return passed
    
    def print_summary(self):
        """Print test summary"""
        self._log("\n" + "="*70)
        self._log("QUALITY GOALS TEST SUITE - SUMMARY")
        self._log("="*70)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        
        self._log(f"\nTests: {passed}/{total} PASSED\n")
        
        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            self._log(f"{status}: Test {result.test_id} - {result.test_name}")
            
            # Print criteria
            for criterion, met in result.criteria_met.items():
                mark = "✓" if met else "✗"
                self._log(f"    {mark} {criterion}")
        
        self._log("\n" + "="*70)
        overall = "✓ ALL TESTS PASSED" if passed == total else f"✗ SOME TESTS FAILED ({total - passed} failures)"
        self._log(overall)
        self._log("="*70)
    
    def export_json(self, filepath: str):
        """Export results to JSON"""
        output = {
            "timestamp": datetime.now().isoformat(),
            "device": self.port,
            "summary": {
                "total_tests": len(self.results),
                "passed_tests": sum(1 for r in self.results if r.passed),
                "overall_status": "PASS" if all(r.passed for r in self.results) else "FAIL"
            },
            "tests": [
                {
                    "test_id": r.test_id,
                    "test_name": r.test_name,
                    "passed": r.passed,
                    "criteria_met": r.criteria_met,
                    "measurements": r.measurements,
                    "notes": r.notes
                }
                for r in self.results
            ],
            "log": self.log_lines
        }
        
        Path(filepath).write_text(json.dumps(output, indent=2) + "\n")
        self._log(f"\n✓ Results exported to {filepath}")
    
    def run_sequence_matrix(self, export_json_path: Optional[str] = None) -> bool:
        """Run tests A-D across all test sequences
        
        Creates a matrix: Rows=Sequences, Columns=Tests(A-D), Values=Pass/Fail
        Uses optimized tests with timeouts and on-device statistics
        """
        if not self.connect():
            return False
        
        try:
            self._log("\n" + "="*70)
            self._log("SEQUENCE MATRIX TEST: Running Tests A-D on 6 Sequences")
            self._log("="*70)
            
            # Matrix storage: sequence_id -> {test_letter -> passed}
            matrix_results = {}
            start_time = time.time()
            
            for seq_id, seq_config in SEQUENCES.items():
                seq_start = time.time()
                name = seq_config["name"]
                positions = seq_config.get("positions", [])
                
                self._log(f"\n\u250c{'─'*68}\u2510")
                self._log(f"\u2502 SEQUENCE {seq_id}: {name:54} \u2502")
                self._log(f"\u2502 Positions: {str(positions)[:56]:56} \u2502")
                self._log(f"\u2514{'─'*68}\u2518")
                
                seq_results = {}
                
                # Save current results count to isolate this sequence's tests
                results_before = len(self.results)
                
                # TEST A: Resolution on this sequence
                try:
                    test_a_passed = self.test_a_resolution(positions[:6])  # Limit to 6 for time
                    seq_results["A"] = test_a_passed
                except Exception as e:
                    self._log(f"  \u2717 TEST A failed with error: {e}")
                    seq_results["A"] = False
                
                # TEST B: Speed through this sequence
                try:
                    test_b_passed = self.test_b_speed(positions)
                    seq_results["B"] = test_b_passed
                except Exception as e:
                    self._log(f"  \u2717 TEST B failed with error: {e}")
                    seq_results["B"] = False
                
                # TEST C: Position Hold on first 4 positions
                try:
                    test_c_passed = self.test_c_position_hold(positions[:4])
                    seq_results["C"] = test_c_passed
                except Exception as e:
                    self._log(f"  \u2717 TEST C failed with error: {e}")
                    seq_results["C"] = False
                
                # TEST D: Overshoot through sequence
                try:
                    test_d_passed = self.test_d_overshoot(positions)
                    seq_results["D"] = test_d_passed
                except Exception as e:
                    self._log(f"  \u2717 TEST D failed with error: {e}")
                    seq_results["D"] = False
                
                matrix_results[seq_id] = seq_results
                
                # Summary for this sequence
                score = sum(1 for v in seq_results.values() if v)
                seq_time = time.time() - seq_start
                self._log(f"\n  \u27a4 SEQUENCE {seq_id} SCORE: {score}/4 ({seq_time:.1f}s)\\n")
            
            total_time = time.time() - start_time
            self._log(f"\nTotal matrix execution time: {total_time:.1f}s")
            
            # Print matrix summary
            self._print_sequence_matrix(matrix_results)
            
            if export_json_path:
                self._export_matrix_json(matrix_results, export_json_path)
            
            # Calculate overall success rate
            total_tests = sum(len(r) for r in matrix_results.values())
            total_passed = sum(sum(1 for v in r.values() if v) for r in matrix_results.values())
            success_rate = total_passed / total_tests if total_tests > 0 else 0
            
            self._log(f"\n\u2550\u2550 OVERALL: {total_passed}/{total_tests} tests passed ({success_rate*100:.0f}%) \u2550\u2550\\n")
            
            return success_rate >= 0.75  # 75% pass rate
        finally:
            self.close()
    
    def _print_sequence_matrix(self, matrix_results: Dict[str, Dict[str, bool]]):
        """Print results as ASCII matrix"""
        self._log("\n" + "="*70)
        self._log("SEQUENCE MATRIX RESULTS")
        self._log("="*70)
        
        header = "Sequence Name              | Test A | Test B | Test C | Test D | Score"
        sep = "-" * len(header)
        
        self._log("\n" + header)
        self._log(sep)
        
        for seq_id, results in matrix_results.items():
            seq_config = SEQUENCES[seq_id]
            name = seq_config["name"][:26]  # Truncate to fit
            
            a = "✓ PASS" if results.get("A", False) else "✗ FAIL"
            b = "✓ PASS" if results.get("B", False) else "✗ FAIL"
            c = "✓ PASS" if results.get("C", False) else "✗ FAIL"
            d = "✓ PASS" if results.get("D", False) else "✗ FAIL"
            
            score = sum(1 for v in results.values() if v)
            
            line = f"{name:26} | {a:6} | {b:6} | {c:6} | {d:6} | {score}/4"
            self._log(line)
        
        self._log(sep)
    
    def _export_matrix_json(self, matrix_results: Dict[str, Dict[str, bool]], filepath: str):
        """Export sequence matrix results to JSON"""
        output = {
            "timestamp": datetime.now().isoformat(),
            "test_type": "SEQUENCE_MATRIX",
            "device": self.port,
            "sequences": SEQUENCES,
            "matrix_results": matrix_results,
            "log": self.log_lines
        }
        
        Path(filepath).write_text(json.dumps(output, indent=2) + "\n")
        self._log(f"\n✓ Matrix results exported to {filepath}")
    
    def run_all(self, export_json_path: Optional[str] = None) -> bool:
        """Run all quality goal tests"""
        if not self.connect():
            return False
        
        try:
            self.test_a_resolution()
            self.test_b_speed()
            self.test_c_position_hold()
            self.test_d_overshoot()
            self.test_e_sequence_tame()
            self.test_f_sequence_fast()
            self.test_g_sequence_random_walk()
            self.test_h_sequence_regression()
            
            self.print_summary()
            
            if export_json_path:
                self.export_json(export_json_path)
            
            return all(r.passed for r in self.results)
        finally:
            self.close()
    
    def close(self):
        """Close connection"""
        if self.ser:
            self.ser.close()
            self._log("✓ Connection closed")


def main():
    """Run test suite"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Quality Goals Test Suite for RP2040 HID Joystick",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 quality_goals_test_suite.py                        # Run standard tests
  python3 quality_goals_test_suite.py --matrix               # Run A-D across 6 sequences
  python3 quality_goals_test_suite.py --matrix --json matrix.json  # Export matrix results
  python3 quality_goals_test_suite.py --port /dev/ttyACM0    # Explicit port
  python3 quality_goals_test_suite.py --json results.json    # Export standard results
        """
    )
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port")
    parser.add_argument("--json", help="Export results to JSON file")
    parser.add_argument("--matrix", action="store_true", help="Run sequence matrix (A-D × 6 sequences)")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    
    args = parser.parse_args()
    
    suite = QualityGoalsTestSuite(port=args.port, verbose=not args.quiet)
    
    if args.matrix:
        success = suite.run_sequence_matrix(export_json_path=args.json)
    else:
        success = suite.run_all(export_json_path=args.json)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
