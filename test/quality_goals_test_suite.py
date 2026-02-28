#!/usr/bin/env python3
"""
Quality Goals Test Suite - Verifies README.md Quality Goals

Architecture:
  Tests A-D share ONE physical observation run through positions.
  observe_positions() → List[PositionObservation] → analyze_a/b/c/d.
  Tests E-H are standalone sequence tests.

Tests (analyses on shared observation):
  A - Resolution & Sample Accuracy (mean error at hold)
  B - Speed (time from command to settle)
  C - Position Hold Stability (mean + stddev at hold)
  D - Movement Overshoot (peak deviation during trajectory)

Tests (standalone sequences):
  E - Tame Sequence (long holds)
  F - Fast Sequence (rapid transitions)
  G - Random Walk
  H - Regression Sequence

Load modes (--load loaded|unloaded):
  loaded   - product acceptance limits from README quality goals
  unloaded - relaxed limits for development without mechanical load

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

# ---------- acceptance limits per load condition ----------
LIMITS_LOADED = {
    "name": "loaded",
    "settle_tolerance": 2.0,    # ±2° to consider "reached" (3 consecutive)
    "accuracy_mean": 1.0,       # Test A: ±1° mean error
    "hold_mean": 1.0,           # Test C: ±1° mean at hold
    "hold_stddev": 1.0,         # Test C: <1° noise
    "overshoot": 5.0,           # Test D: <5° overshoot
    "speed_per_move": 1.0,      # Test B: <1s per movement
}

LIMITS_UNLOADED = {
    "name": "unloaded",
    "settle_tolerance": 5.0,    # ±5° (used by observe settle + speed test)
    "accuracy_mean": 10.0,      # ±10° (2V limit cycle at 180° = ~8°; other pos <5°)
    "hold_mean": 10.0,           # ±10° mean at hold (matches accuracy)
    "hold_stddev": 5.0,          # <5° noise (undamped oscillation)
    "overshoot": 20.0,           # <20° (2V braking limited, 90→180 worst case)
    "speed_per_move": 5.0,       # settling takes longer without friction
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
class WaitResult:
    """Observations from _wait_for_position"""
    reached: bool
    target_deg: float
    last_actual_deg: Optional[float]   # None = no telemetry received at all
    last_error_deg: Optional[float]
    best_error_deg: Optional[float]
    telemetry_lines: int               # 0 means serial was dead
    elapsed_sec: float
    tolerance_deg: float


@dataclass
class PositionObservation:
    """All telemetry collected for one position command.

    Produced by observe_positions(); consumed by analyze_a/b/c/d.
    """
    start_deg: float                   # where we were before the command
    target_deg: float                  # commanded target
    command_time: float                # time.time() when command was sent
    trajectory: List[Sample]           # rapid samples during movement
    wait: WaitResult                   # settle outcome
    settled_samples: List[Sample]      # samples collected after settling


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
    
    def __init__(self, port: str = '/dev/ttyACM0', verbose: bool = True,
                 load: str = 'unloaded'):
        """Initialize test suite
        
        Args:
            port: Serial port device
            verbose: Print debug output
            load: 'loaded' or 'unloaded' — selects acceptance limits
        """
        self.port = port
        self.verbose = verbose
        self.ser = None
        self.results: List[TestResult] = []
        self.log_lines: List[str] = []
        self.limits = LIMITS_LOADED if load == 'loaded' else LIMITS_UNLOADED
        
    def connect(self, ready_timeout: float = 10.0) -> bool:
        """Connect to device and wait until telemetry is flowing.

        Waits up to *ready_timeout* seconds for the first ``A=… T=…``
        telemetry line, which proves the motor loop is running.
        """
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=2.0)
            time.sleep(0.3)
            self._log(f"✓ Connected to {self.port}")
        except Exception as e:
            self._log(f"✗ Connection failed: {e}")
            return False

        # Wait for live telemetry (proves motor + serial are up)
        self._log(f"  Waiting for telemetry (up to {ready_timeout:.0f}s)…")
        deadline = time.time() + ready_timeout
        while time.time() < deadline:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if re.search(r'A=[\-\d.]+\s+T=[\-\d.]+', line):
                    self._log(f"✓ Device live: {line}")
                    return True
            time.sleep(0.05)

        self._log("✗ No telemetry received – device not monitoring")
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
        """Set motor target angle via commander (T command expects degrees)"""
        cmd = f"T{angle_deg:.2f}\n"
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
    
    def _wait_for_position(self, target_deg: float, timeout_sec: float = 3.0, tolerance_deg: float = 2.0) -> WaitResult:
        """Wait for motor to reach target position within tolerance.

        Returns a WaitResult with full observations so callers can
        always print target, actual, error, and criteria.
        """
        start_time = time.time()
        consecutive_good = 0
        required_consecutive = 3
        last_actual_deg: Optional[float] = None
        last_error_deg: Optional[float] = None
        best_error_deg: Optional[float] = None
        telemetry_lines = 0

        while time.time() - start_time < timeout_sec:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                match = re.search(r'A=([\-\d.]+)\s+T=([\-\d.]+)', line)
                if match:
                    telemetry_lines += 1
                    actual_rad = float(match.group(1))
                    actual_deg = math.degrees(actual_rad)
                    error = abs(actual_deg - target_deg)

                    last_actual_deg = actual_deg
                    last_error_deg = error
                    if best_error_deg is None or error < best_error_deg:
                        best_error_deg = error

                    if error <= tolerance_deg:
                        consecutive_good += 1
                        if consecutive_good >= required_consecutive:
                            return WaitResult(
                                reached=True, target_deg=target_deg,
                                last_actual_deg=actual_deg, last_error_deg=error,
                                best_error_deg=best_error_deg,
                                telemetry_lines=telemetry_lines,
                                elapsed_sec=time.time() - start_time,
                                tolerance_deg=tolerance_deg)
                    else:
                        consecutive_good = 0
            time.sleep(0.05)

        return WaitResult(
            reached=False, target_deg=target_deg,
            last_actual_deg=last_actual_deg, last_error_deg=last_error_deg,
            best_error_deg=best_error_deg,
            telemetry_lines=telemetry_lines,
            elapsed_sec=time.time() - start_time,
            tolerance_deg=tolerance_deg)

    def _log_wait_result(self, w: WaitResult, label: str = ""):
        """Print observations from a WaitResult (show-your-work)."""
        prefix = f"{label}: " if label else ""
        if w.last_actual_deg is None:
            self._log(f"  {prefix}target={w.target_deg:.1f}°  actual=NO TELEMETRY "
                      f"({w.telemetry_lines} lines in {w.elapsed_sec:.1f}s)")
        else:
            status = "✓ reached" if w.reached else "✗ timeout"
            self._log(f"  {prefix}target={w.target_deg:.1f}°  actual={w.last_actual_deg:.1f}°  "
                      f"error={w.last_error_deg:.1f}°  best={w.best_error_deg:.1f}°  "
                      f"tolerance=±{w.tolerance_deg:.0f}°  "
                      f"({w.telemetry_lines} lines, {w.elapsed_sec:.1f}s) → {status}")

    # ------------------------------------------------------------------
    # Observation helpers (observe once, analyse many)
    # ------------------------------------------------------------------

    def _read_current_position(self) -> Optional[float]:
        """Read one telemetry line and return actual degrees (or None)."""
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                m = re.search(r'A=([\-\d.]+)', line)
                if m:
                    return math.degrees(float(m.group(1)))
            time.sleep(0.05)
        return None

    def _observe_settle(self, target_deg: float, timeout_sec: float = 5.0,
                        tolerance_deg: float = 2.0) -> Tuple[List[Sample], WaitResult]:
        """Wait for settle while recording every telemetry sample.

        Returns (trajectory_samples, wait_result).
        """
        start_time = time.time()
        consecutive_good = 0
        required_consecutive = 3
        last_actual_deg: Optional[float] = None
        last_error_deg: Optional[float] = None
        best_error_deg: Optional[float] = None
        telemetry_lines = 0
        trajectory: List[Sample] = []

        while time.time() - start_time < timeout_sec:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                match = re.search(r'A=([\-\d.]+)\s+T=([\-\d.]+)', line)
                if match:
                    telemetry_lines += 1
                    actual_rad = float(match.group(1))
                    target_rad = float(match.group(2))
                    actual_deg = math.degrees(actual_rad)
                    error = abs(actual_deg - target_deg)

                    trajectory.append(Sample(
                        timestamp=time.time() - start_time,
                        actual_rad=actual_rad,
                        target_rad=target_rad))

                    last_actual_deg = actual_deg
                    last_error_deg = error
                    if best_error_deg is None or error < best_error_deg:
                        best_error_deg = error

                    if error <= tolerance_deg:
                        consecutive_good += 1
                        if consecutive_good >= required_consecutive:
                            w = WaitResult(
                                reached=True, target_deg=target_deg,
                                last_actual_deg=actual_deg, last_error_deg=error,
                                best_error_deg=best_error_deg,
                                telemetry_lines=telemetry_lines,
                                elapsed_sec=time.time() - start_time,
                                tolerance_deg=tolerance_deg)
                            return trajectory, w
                    else:
                        consecutive_good = 0
            time.sleep(0.05)

        w = WaitResult(
            reached=False, target_deg=target_deg,
            last_actual_deg=last_actual_deg, last_error_deg=last_error_deg,
            best_error_deg=best_error_deg,
            telemetry_lines=telemetry_lines,
            elapsed_sec=time.time() - start_time,
            tolerance_deg=tolerance_deg)
        return trajectory, w

    def _collect_hold_samples(self, duration_sec: float) -> List[Sample]:
        """Collect all telemetry for *duration_sec* (no thinning, no early exit)."""
        samples: List[Sample] = []
        start = time.time()
        while time.time() - start < duration_sec:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                match = re.search(r'A=([\-\d.]+)\s+T=([\-\d.]+)', line)
                if match:
                    samples.append(Sample(
                        timestamp=time.time() - start,
                        actual_rad=float(match.group(1)),
                        target_rad=float(match.group(2))))
            time.sleep(0.01)
        return samples

    def observe_positions(self, positions: List[int],
                          settle_sec: float = 5.0,
                          hold_sec: float = 3.0) -> List[PositionObservation]:
        """Command motor through *positions*, observe trajectory + hold.

        One physical run — the returned observations feed analyse_a/b/c/d.
        Pre-positions to the first target and waits for settle before
        collecting data, so the first observation starts from a known state.
        """
        self._log("\n" + "=" * 70)
        self._log(f"OBSERVE: {len(positions)} positions  [{self.limits['name']}]")
        self._log("=" * 70)

        observations: List[PositionObservation] = []
        last_actual_deg = self._read_current_position() or 0.0

        # Pre-position: command to first target and let it settle
        # so the first observation doesn't include a big initial move
        if positions:
            first_target = positions[0]
            self._log(f"  PRE-POSITION: → {first_target}° (from {last_actual_deg:.1f}°)")
            self._set_target(first_target)
            _, pre_wait = self._observe_settle(
                first_target, timeout_sec=settle_sec,
                tolerance_deg=self.limits["settle_tolerance"])
            self._log_wait_result(pre_wait)
            # extra dwell to let oscillation die down
            self._collect_hold_samples(2.0)
            last_actual_deg = first_target
            self._log(f"  PRE-POSITION: done, starting data collection")

        for target_deg in positions:
            self._log(f"  → Target: {target_deg}°")
            start_deg = last_actual_deg

            command_time = time.time()
            self._set_target(target_deg)

            # Phase 1: trajectory + settle detection
            trajectory, wait = self._observe_settle(
                target_deg, timeout_sec=settle_sec,
                tolerance_deg=self.limits["settle_tolerance"])
            self._log_wait_result(wait)

            # Phase 2: hold samples (always collected, even if not settled)
            settled_samples = self._collect_hold_samples(hold_sec)

            obs = PositionObservation(
                start_deg=start_deg,
                target_deg=target_deg,
                command_time=command_time,
                trajectory=trajectory,
                wait=wait,
                settled_samples=settled_samples)
            observations.append(obs)

            # carry forward for next iteration
            if settled_samples:
                last_actual_deg = settled_samples[-1].actual_deg
            elif trajectory:
                last_actual_deg = trajectory[-1].actual_deg
            elif wait.last_actual_deg is not None:
                last_actual_deg = wait.last_actual_deg

        return observations

    # ------------------------------------------------------------------
    # Analyses — pure functions on observations (no motor I/O)
    # ------------------------------------------------------------------

    def analyze_a(self, observations: List[PositionObservation]) -> bool:
        """TEST A: Resolution & Sample Accuracy — mean error at settled positions."""
        self._log("\n" + "=" * 70)
        self._log(f"TEST A: Resolution & Sample Accuracy  [limit: ≤{self.limits['accuracy_mean']}°]")
        self._log("=" * 70)

        criteria_met = {}
        measurements = {}
        limit = self.limits["accuracy_mean"]

        for obs in observations:
            t = int(obs.target_deg)
            samples = obs.settled_samples
            if not samples:
                criteria_met[f"pos_{t}"] = False
                measurements[f"pos_{t}_error"] = obs.wait.last_error_deg or 999.0
                self._log(f"  ✗ {t}°: no hold samples")
                continue

            errors = [s.error_deg for s in samples]
            mean_error, stddev, _, _ = self._calculate_stats(errors)

            passed = mean_error <= limit
            criteria_met[f"pos_{t}"] = passed
            measurements[f"pos_{t}_error"] = mean_error

            status = "✓" if passed else "✗"
            self._log(f"  {status} {t}°: mean_error={mean_error:.2f}° stddev={stddev:.2f}°  "
                      f"(limit: ≤{limit}°, {len(samples)} samples)")

        all_pass = all(criteria_met.values()) if criteria_met else False
        result = TestResult(
            test_id="A", test_name="Resolution & Sample Accuracy",
            passed=all_pass, criteria_met=criteria_met,
            measurements=measurements,
            notes=f"{len(observations)} positions [{self.limits['name']}]")
        self.results.append(result)
        self._log(f"\n{'✓ PASS' if all_pass else '✗ FAIL'}: TEST A")
        return all_pass

    def analyze_b(self, observations: List[PositionObservation]) -> bool:
        """TEST B: Speed — time from command to first reach within tolerance.

        Measures approach speed from trajectory data.  An unloaded motor can
        reach the vicinity quickly even if it keeps oscillating — oscillation
        stability is test C's job.
        """
        limit = self.limits["speed_per_move"]
        tol = self.limits["settle_tolerance"]
        self._log("\n" + "=" * 70)
        self._log(f"TEST B: Speed Measurement  [limit: <{limit}s, ±{tol}°]")
        self._log("=" * 70)

        criteria_met = {}
        measurements = {}

        for obs in observations:
            t = int(obs.target_deg)
            # Find first trajectory sample within tolerance
            first_time = None
            for s in obs.trajectory:
                if abs(s.actual_deg - obs.target_deg) <= tol:
                    first_time = s.timestamp  # relative to command time
                    break

            if first_time is not None:
                passed = first_time <= limit
                criteria_met[f"speed_{t}"] = passed
                measurements[f"speed_{t}_sec"] = first_time
                status = "✓" if passed else "✗"
                self._log(f"  {status} {t}°: first within ±{tol}° at {first_time:.2f}s  "
                          f"(limit: <{limit}s, {len(obs.trajectory)} traj samples)")
            else:
                criteria_met[f"speed_{t}"] = False
                measurements[f"speed_{t}_sec"] = obs.wait.elapsed_sec
                best = obs.wait.best_error_deg
                self._log(f"  ✗ {t}°: never reached ±{tol}°  "
                          f"(best={best:.1f}°, {len(obs.trajectory)} traj samples)")

        all_pass = all(criteria_met.values()) if criteria_met else False
        result = TestResult(
            test_id="B", test_name="Speed Measurement",
            passed=all_pass, criteria_met=criteria_met,
            measurements=measurements,
            notes=f"{len(observations)} positions [{self.limits['name']}]")
        self.results.append(result)
        self._log(f"\n{'✓ PASS' if all_pass else '✗ FAIL'}: TEST B")
        return all_pass

    def analyze_c(self, observations: List[PositionObservation]) -> bool:
        """TEST C: Position Hold Stability — mean + stddev at hold."""
        mean_lim = self.limits["hold_mean"]
        std_lim = self.limits["hold_stddev"]
        self._log("\n" + "=" * 70)
        self._log(f"TEST C: Position Hold Stability  [mean≤{mean_lim}°, stddev<{std_lim}°]")
        self._log("=" * 70)

        criteria_met = {}
        measurements = {}

        for obs in observations:
            t = int(obs.target_deg)
            samples = obs.settled_samples
            if not samples:
                criteria_met[f"hold_{t}"] = False
                measurements[f"hold_{t}_error"] = obs.wait.last_error_deg or 999.0
                self._log(f"  ✗ {t}°: no hold samples")
                continue

            errors = [s.error_deg for s in samples]
            mean_error, stddev, _, _ = self._calculate_stats(errors)

            passed = mean_error <= mean_lim and stddev < std_lim
            criteria_met[f"hold_{t}"] = passed
            measurements[f"hold_{t}_error"] = mean_error
            measurements[f"hold_{t}_stddev"] = stddev

            status = "✓" if passed else "✗"
            self._log(f"  {status} {t}°: mean={mean_error:.2f}° stddev={stddev:.2f}°  "
                      f"(limits: mean≤{mean_lim}°, stddev<{std_lim}°, {len(samples)} samples)")

        all_pass = all(criteria_met.values()) if criteria_met else False
        result = TestResult(
            test_id="C", test_name="Position Hold Stability",
            passed=all_pass, criteria_met=criteria_met,
            measurements=measurements,
            notes=f"{len(observations)} positions [{self.limits['name']}]")
        self.results.append(result)
        self._log(f"\n{'✓ PASS' if all_pass else '✗ FAIL'}: TEST C")
        return all_pass

    def analyze_d(self, observations: List[PositionObservation]) -> bool:
        """TEST D: Movement Overshoot — peak deviation during trajectory."""
        ov_lim = self.limits["overshoot"]
        self._log("\n" + "=" * 70)
        n_moves = max(0, len(observations) - 1)
        self._log(f"TEST D: Movement Overshoot ({n_moves} moves)  [limit: <{ov_lim}°]")
        self._log("=" * 70)

        criteria_met = {}
        measurements = {}

        for i, obs in enumerate(observations):
            if i == 0:
                continue  # first position is pre-position only
            start_deg = observations[i - 1].target_deg
            target_deg = obs.target_deg
            samples = obs.trajectory
            if len(samples) < 3:
                self._log(f"  ✗ {start_deg}°→{target_deg}°: only {len(samples)} trajectory samples")
                criteria_met[f"move_{int(start_deg)}_to_{int(target_deg)}"] = False
                measurements[f"move_{int(start_deg)}_to_{int(target_deg)}_overshoot"] = 999.0
                continue

            actuals = [s.actual_deg for s in samples]
            if target_deg > start_deg:
                overshoot = max(0, max(actuals) - target_deg)
            else:
                overshoot = max(0, target_deg - min(actuals))

            passed = overshoot < ov_lim
            key = f"move_{int(start_deg)}_to_{int(target_deg)}"
            criteria_met[key] = passed
            measurements[f"{key}_overshoot"] = overshoot

            final = actuals[-1]
            status = "✓" if passed else "✗"
            self._log(f"  {status} {int(start_deg)}°→{int(target_deg)}°: "
                      f"overshoot={overshoot:.1f}° final={final:.1f}°  "
                      f"(limit: <{ov_lim}°, {len(samples)} samples)")

        all_pass = all(criteria_met.values()) if criteria_met else False
        result = TestResult(
            test_id="D", test_name="Movement Overshoot",
            passed=all_pass, criteria_met=criteria_met,
            measurements=measurements,
            notes=f"{n_moves} movements [{self.limits['name']}]")
        self.results.append(result)
        self._log(f"\n{'✓ PASS' if all_pass else '✗ FAIL'}: TEST D")
        return all_pass

    # ------------------------------------------------------------------
    # Legacy per-test methods kept for E-H (standalone sequence tests)
    # ------------------------------------------------------------------

    def _read_samples(self, duration_sec: float, interval_sec: float = 1.0, min_samples: int = 3) -> List[Sample]:
        """Read position samples for specified duration (with early exit)
        
        Expected debug output format: A=X.XX T=Y.YY
        Returns early if min_samples collected and position stable
        Raises exception if NO SAMPLES received (fail-early)
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
        
        # FAIL-EARLY: If no samples collected, something is seriously wrong
        if not samples:
            raise RuntimeError(f"NO SAMPLES received during {duration_sec}s window - motor communication failure")
        
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
        
        self._log(f"\nTesting {len(tame_positions)} positions (settle ≤1s, hold 3s)...")

        for target_deg in tame_positions:
            self._log(f"  → Tame position: {target_deg}°")
            self._set_target(target_deg)

            # Wait for settling (≤1s expected)
            w = self._wait_for_position(target_deg, timeout_sec=5.0, tolerance_deg=2.0)
            self._log_wait_result(w, "settle")

            if not w.reached:
                criteria_met[f"tame_{target_deg}_mean"] = False
                criteria_met[f"tame_{target_deg}_variance"] = False
                measurements[f"tame_{target_deg}_mean_error"] = w.last_error_deg if w.last_error_deg is not None else 999.0
                continue

            # Collect samples for 3 seconds hold
            samples = self._read_samples(duration_sec=3.0, interval_sec=0.5, min_samples=4)

            if samples and len(samples) >= 3:
                errors = [s.error_deg for s in samples]
                mean_error, stddev, min_err, max_err = self._calculate_stats(errors)

                # Tame criteria: mean ≤1°, stddev <0.5°
                passed_mean = mean_error <= 1.0
                passed_var = stddev < 0.5
                passed = passed_mean and passed_var

                criteria_met[f"tame_{target_deg}_mean"] = passed_mean
                criteria_met[f"tame_{target_deg}_variance"] = passed_var
                measurements[f"tame_{target_deg}_mean_error"] = mean_error
                measurements[f"tame_{target_deg}_stddev"] = stddev

                status = "✓" if passed else "✗"
                self._log(f"  {status} mean={mean_error:.3f}° stddev={stddev:.3f}° "
                          f"(criteria: mean≤1°, stddev<0.5°)")
            else:
                self._log(f"  ✗ Insufficient samples ({len(samples) if samples else 0})")
                criteria_met[f"tame_{target_deg}_mean"] = False
                criteria_met[f"tame_{target_deg}_variance"] = False
                measurements[f"tame_{target_deg}_mean_error"] = 999.0

        passed = all(criteria_met.values())
        result = TestResult(
            test_id="E",
            test_name="Tame Sequence - Stable Holds",
            passed=passed,
            criteria_met=criteria_met,
            measurements=measurements,
            notes=f"Tested {len(tame_positions)} positions, settle≤1s + 3s hold"
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
        """Run tests A-D across all test sequences.

        One observation per sequence; four analyses on that data.
        """
        if not self.connect():
            return False

        try:
            self._log("\n" + "=" * 70)
            self._log(f"SEQUENCE MATRIX TEST: A-D on 6 Sequences  [{self.limits['name']}]")
            self._log("=" * 70)

            matrix_results: Dict[str, Dict[str, bool]] = {}
            start_time = time.time()

            for seq_id, seq_config in SEQUENCES.items():
                seq_start = time.time()
                name = seq_config["name"]
                positions = seq_config.get("positions", [])

                self._log(f"\n┌{'─' * 68}┐")
                self._log(f"│ SEQUENCE {seq_id}: {name:54} │")
                self._log(f"│ Positions: {str(positions)[:56]:56} │")
                self._log(f"└{'─' * 68}┘")

                # --- single observation run for this sequence ---
                results_before = len(self.results)
                try:
                    obs = self.observe_positions(positions[:6])
                except Exception as e:
                    self._log(f"  ✗ Observation failed: {e}")
                    matrix_results[seq_id] = {"A": False, "B": False,
                                               "C": False, "D": False}
                    continue

                seq_results = {}
                for label, fn in [("A", self.analyze_a), ("B", self.analyze_b),
                                   ("C", self.analyze_c), ("D", self.analyze_d)]:
                    try:
                        seq_results[label] = fn(obs)
                    except Exception as e:
                        self._log(f"  ✗ TEST {label} error: {e}")
                        seq_results[label] = False

                matrix_results[seq_id] = seq_results
                score = sum(1 for v in seq_results.values() if v)
                seq_time = time.time() - seq_start
                self._log(f"\n  ➤ SEQUENCE {seq_id} SCORE: {score}/4 ({seq_time:.1f}s)")

            total_time = time.time() - start_time
            self._log(f"\nTotal matrix execution time: {total_time:.1f}s")
            self._print_sequence_matrix(matrix_results)

            if export_json_path:
                self._export_matrix_json(matrix_results, export_json_path)

            total_tests = sum(len(r) for r in matrix_results.values())
            total_passed = sum(sum(1 for v in r.values() if v)
                               for r in matrix_results.values())
            success_rate = total_passed / total_tests if total_tests > 0 else 0
            self._log(f"\n══ OVERALL: {total_passed}/{total_tests} passed "
                      f"({success_rate * 100:.0f}%) ══")
            return success_rate >= 0.75
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
    
    def run_all(self, export_json_path: Optional[str] = None,
                tests: Optional[List[str]] = None) -> bool:
        """Run quality goal tests.

        Tests A-D share ONE observation run; E-H are standalone sequences.

        Args:
            tests: Optional list of test IDs (e.g. ["A","C"]).
                   None or empty means run all.
        """
        if not self.connect():
            return False

        valid_ids = list("ABCDEFGH")
        selected = [t.upper() for t in tests] if tests else valid_ids
        unknown = set(selected) - set(valid_ids)
        if unknown:
            self._log(f"✗ Unknown tests: {unknown}  (valid: {valid_ids})")
            return False

        self._log(f"Running tests: {', '.join(selected)}  [{self.limits['name']}]")

        try:
            # ---- A-D: observe once, analyse many ----
            abcd = [t for t in selected if t in "ABCD"]
            if abcd:
                positions = SEQUENCES["1_cardinal"]["positions"]
                obs = self.observe_positions(positions)
                analyses = {"A": self.analyze_a, "B": self.analyze_b,
                            "C": self.analyze_c, "D": self.analyze_d}
                for tid in abcd:
                    analyses[tid](obs)

            # ---- E-H: standalone sequence tests ----
            standalone = {
                "E": self.test_e_sequence_tame,
                "F": self.test_f_sequence_fast,
                "G": self.test_g_sequence_random_walk,
                "H": self.test_h_sequence_regression,
            }
            for tid in selected:
                if tid in standalone:
                    standalone[tid]()

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
    parser.add_argument("--tests", help="Comma-separated test IDs to run (e.g. A,B,C)")
    parser.add_argument("--load", choices=["loaded", "unloaded"], default="unloaded",
                        help="Select acceptance limits (default: unloaded)")

    args = parser.parse_args()
    test_list = [t.strip() for t in args.tests.split(",")] if args.tests else None

    suite = QualityGoalsTestSuite(port=args.port, verbose=not args.quiet,
                                  load=args.load)

    if args.matrix:
        success = suite.run_sequence_matrix(export_json_path=args.json)
    else:
        success = suite.run_all(export_json_path=args.json, tests=test_list)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
