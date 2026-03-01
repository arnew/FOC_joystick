#!/usr/bin/env python3
"""
Quality Goals Test Suite v2 — Observation-Based Fast Testing

Relies on device-side rolling statistics (@T telemetry from telemetry.h).
Device computes error + variance at ~1kHz; host polls at 10Hz.
Early termination when device reports settled → 5-10x faster than v1.

Tests (A-D share one observation run, E-H are standalone sequences):
  A - Accuracy: mean |error| at settled positions
  B - Speed: time from command to settled
  C - Stability: error mean + stddev at settled
  D - Overshoot: peak deviation during movement

  E - Tame: 8-position long-hold stability
  F - Fast: rapid transitions
  G - Random Walk: 20 stochastic positions
  H - Regression: known problem patterns

Usage:
  python3 test/quality_goals_test_suite.py                 # tests A-D cardinal
  python3 test/quality_goals_test_suite.py --tests A,B,E   # specific tests
  python3 test/quality_goals_test_suite.py --matrix         # A-D x 6 sequences
  python3 test/quality_goals_test_suite.py --json out.json  # export results
"""

import serial
import time
import math
import json
import sys
import argparse
import statistics as pystats
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ===================================================================
# SEQUENCES
# ===================================================================

SEQUENCES = {
    "1_cardinal": {
        "name": "Cardinal Positions",
        "positions": [0, 90, 180, 270],
    },
    "2_full_grid": {
        "name": "Full Grid (8-point)",
        "positions": [0, 45, 90, 135, 180, 225, 270, 315],
    },
    "3_tame_slow": {
        "name": "Tame/Slow Sequence",
        "positions": [0, 90, 180, 270],
    },
    "4_fast_rapid": {
        "name": "Fast/Rapid Sequence",
        "positions": [0, 180, 45, 225, 90, 270],
    },
    "5_random_walk": {
        "name": "Random Walk (20 positions)",
        "positions": [10, 87, 143, 215, 32, 298, 159, 71, 306, 44,
                      178, 251, 123, 38, 267, 94, 212, 155, 3, 337],
    },
    "6_boundary": {
        "name": "Boundary Angles",
        "positions": [355, 359, 0, 1, 5],
    },
}

# ===================================================================
# ACCEPTANCE LIMITS
# ===================================================================

LIMITS = {
    "loaded": {
        "name": "loaded",
        "accuracy_mean_deg": 1.0,
        "speed_s": 1.0,
        "hold_mean_deg": 1.0,
        "hold_std_deg": 1.0,
        "overshoot_deg": 5.0,
    },
    "unloaded": {
        "name": "unloaded",
        "accuracy_mean_deg": 10.0,
        "speed_s": 5.0,
        "hold_mean_deg": 10.0,
        "hold_std_deg": 5.0,
        "overshoot_deg": 20.0,
    },
}

# ===================================================================
# DATA CLASSES
# ===================================================================

@dataclass
class Obs:
    """Single device telemetry observation (@T line)."""
    device_ms: int
    target: float       # rad
    actual: float       # rad
    error: float        # rad (signed shortest-path)
    rms: float          # rad (EMA RMS error)
    variance: float     # rad^2 (device rolling 0.5s window)
    settled: bool
    host_t: float       # time.time()

    @property
    def error_deg(self) -> float:
        return math.degrees(self.error)

    @property
    def actual_deg(self) -> float:
        return math.degrees(self.actual)

    @property
    def target_deg(self) -> float:
        return math.degrees(self.target)


@dataclass
class Step:
    """Observations collected for one target command."""
    target_deg: float
    obs: List[Obs]
    settled: bool
    settle_time_s: Optional[float]
    duration_s: float

    @property
    def settled_obs(self) -> List[Obs]:
        return [o for o in self.obs if o.settled]

    @property
    def trajectory_obs(self) -> List[Obs]:
        return [o for o in self.obs if not o.settled]


@dataclass
class Result:
    """One test verdict."""
    test_id: str
    name: str
    passed: bool
    detail: Dict
    notes: str = ""


# ===================================================================
# DEVICE LINK
# ===================================================================

class DeviceLink:
    """Serial connection: send commands, parse @T telemetry."""

    def __init__(self, port: str = "/dev/ttyACM0"):
        self.port = port
        self.ser: Optional[serial.Serial] = None

    def connect(self, timeout: float = 10.0) -> bool:
        """Open serial, wait for the first @T line."""
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=0.5)
            time.sleep(0.3)
        except Exception as e:
            print(f"* Cannot open {self.port}: {e}")
            return False

        deadline = time.time() + timeout
        while time.time() < deadline:
            obs = self.poll()
            if obs is not None:
                print(f"+ Device live on {self.port}  "
                      f"target={obs.target_deg:.1f} "
                      f"actual={obs.actual_deg:.1f}")
                return True
            time.sleep(0.02)

        print("* No @T telemetry - is firmware up to date?")
        return False

    def send_target(self, angle_deg: float):
        """Send T<degrees> commander command."""
        if self.ser:
            self.ser.write(f"T{angle_deg:.2f}\n".encode())

    def poll(self) -> Optional[Obs]:
        """Non-blocking: read one @T line or return None."""
        if not self.ser or not self.ser.in_waiting:
            return None
        try:
            raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
            return self._parse(raw)
        except Exception:
            return None

    def drain(self):
        """Discard all pending serial data."""
        if self.ser:
            self.ser.reset_input_buffer()

    def close(self):
        if self.ser:
            self.ser.close()
            self.ser = None

    @staticmethod
    def _parse(line: str) -> Optional[Obs]:
        """Parse '@T ms,target,actual,error,rms,variance,settled'."""
        if not line.startswith("@T "):
            return None
        try:
            parts = line[3:].split(",")
            if len(parts) < 7:
                return None
            return Obs(
                device_ms=int(parts[0]),
                target=float(parts[1]),
                actual=float(parts[2]),
                error=float(parts[3]),
                rms=float(parts[4]),
                variance=float(parts[5]),
                settled=parts[6].strip() == "1",
                host_t=time.time(),
            )
        except (ValueError, IndexError):
            return None


# ===================================================================
# RUNNER
# ===================================================================

class Runner:
    """Drive sequences, collect observations with early termination."""

    def __init__(self, link: DeviceLink, verbose: bool = True):
        self.link = link
        self.verbose = verbose

    def log(self, msg: str):
        if self.verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {msg}")

    def move_and_observe(self, target_deg: float,
                         min_s: float = 0.3, max_s: float = 5.0,
                         n_ok: int = 5) -> Step:
        """Command target, observe until settled or timeout.

        Always observes >= min_s.  Exits early after n_ok consecutive
        device-settled readings AND min_s elapsed.  Hard cap at max_s.
        """
        self.link.drain()
        self.link.send_target(target_deg)
        start = time.time()

        observations: List[Obs] = []
        consec_ok = 0
        settle_time: Optional[float] = None

        while True:
            elapsed = time.time() - start
            if elapsed >= max_s:
                break

            obs = self.link.poll()
            if obs is not None:
                observations.append(obs)

                if obs.settled:
                    consec_ok += 1
                    if settle_time is None:
                        settle_time = elapsed
                    if consec_ok >= n_ok and elapsed >= min_s:
                        break
                else:
                    consec_ok = 0
                    settle_time = None
            else:
                time.sleep(0.02)

        duration = time.time() - start
        settled = consec_ok >= n_ok

        if observations:
            last = observations[-1]
            flag = "+ settled" if settled else "* timeout"
            t_str = f"{settle_time:.2f}s" if settle_time else "---"
            self.log(
                f"  {target_deg:6.1f}deg | "
                f"err={last.error_deg:+6.2f}deg "
                f"var={last.variance:.6f} | {t_str:>6} | "
                f"{len(observations):3d} obs {duration:.1f}s | {flag}")
        else:
            self.log(
                f"  {target_deg:6.1f}deg | "
                f"NO TELEMETRY | {duration:.1f}s | *")

        return Step(
            target_deg=target_deg,
            obs=observations,
            settled=settled,
            settle_time_s=settle_time,
            duration_s=duration,
        )

    def run_sequence(self, positions: List[int],
                     min_s: float = 0.3, max_s: float = 5.0,
                     pre_position: bool = True) -> List[Step]:
        """Run through positions, pre-positioning to the first."""
        self.log(f"  SEQUENCE: {len(positions)} positions  "
                 f"(min={min_s}s max={max_s}s)")
        self.log(
            f"  {'target':>8} | {'error':>16} {'variance':>12} | "
            f"{'settle':>6} | {'observations':>16} | result")
        self.log(
            f"  {'--------':>8} | {'----------------':>16} "
            f"{'------------':>12} | {'------':>6} | "
            f"{'----------------':>16} | ----------")

        steps: List[Step] = []

        if pre_position and positions:
            self.log(f"  PRE-POSITION -> {positions[0]}deg")
            self.move_and_observe(positions[0], min_s=0.5, max_s=max_s)

        for deg in positions:
            step = self.move_and_observe(deg, min_s=min_s, max_s=max_s)
            steps.append(step)

        return steps


# ===================================================================
# ANALYSIS — pure functions on Steps -> Results
# ===================================================================

def analyze_accuracy(steps: List[Step], limit_deg: float) -> Result:
    """TEST A: Mean |error| at settled observations."""
    detail = {}
    all_pass = True
    for s in steps:
        settled = s.settled_obs
        key = f"{s.target_deg:.0f}deg"
        if not settled:
            detail[key] = {"pass": False, "note": "never settled"}
            all_pass = False
            continue
        errors = [abs(o.error_deg) for o in settled]
        mean_err = pystats.mean(errors)
        passed = mean_err <= limit_deg
        detail[key] = {
            "pass": passed,
            "mean_error_deg": round(mean_err, 2),
            "n": len(settled),
        }
        if not passed:
            all_pass = False
    return Result("A", "Accuracy", all_pass, detail,
                  f"limit <={limit_deg}deg")


def analyze_speed(steps: List[Step], limit_s: float) -> Result:
    """TEST B: Time from command to first device-settled."""
    detail = {}
    all_pass = True
    for s in steps:
        key = f"{s.target_deg:.0f}deg"
        if s.settle_time_s is not None:
            passed = s.settle_time_s <= limit_s
            detail[key] = {
                "pass": passed,
                "settle_s": round(s.settle_time_s, 2),
            }
        else:
            passed = False
            detail[key] = {"pass": False, "note": "didn't settle"}
        if not passed:
            all_pass = False
    return Result("B", "Speed", all_pass, detail,
                  f"limit <{limit_s}s")


def analyze_stability(steps: List[Step],
                      mean_lim: float, std_lim: float) -> Result:
    """TEST C: Hold stability — mean error + stddev at settled."""
    detail = {}
    all_pass = True
    for s in steps:
        settled = s.settled_obs
        key = f"{s.target_deg:.0f}deg"
        if len(settled) < 2:
            detail[key] = {"pass": False, "note": "insufficient data"}
            all_pass = False
            continue
        errors = [o.error_deg for o in settled]
        abs_errors = [abs(e) for e in errors]
        mean_err = pystats.mean(abs_errors)
        std_err = pystats.stdev(errors) if len(errors) > 1 else 0
        dev_var = pystats.mean([o.variance for o in settled])
        passed = mean_err <= mean_lim and std_err < std_lim
        detail[key] = {
            "pass": passed,
            "mean_deg": round(mean_err, 2),
            "std_deg": round(std_err, 2),
            "dev_variance": round(dev_var, 6),
            "n": len(settled),
        }
        if not passed:
            all_pass = False
    return Result("C", "Stability", all_pass, detail,
                  f"mean<={mean_lim}deg std<{std_lim}deg")


def analyze_overshoot(steps: List[Step], limit_deg: float) -> Result:
    """TEST D: Peak deviation past target during movement."""
    detail = {}
    all_pass = True
    for i, s in enumerate(steps):
        if i == 0:
            continue
        if not s.obs:
            key = f"->{s.target_deg:.0f}deg"
            detail[key] = {"pass": False, "note": "no data"}
            all_pass = False
            continue

        prev_deg = steps[i - 1].target_deg
        actuals = [o.actual_deg for o in s.obs]
        target = s.target_deg

        if target > prev_deg:
            overshoot = max(0, max(actuals) - target)
        else:
            overshoot = max(0, target - min(actuals))

        passed = overshoot < limit_deg
        key = f"{prev_deg:.0f}->{target:.0f}deg"
        detail[key] = {
            "pass": passed,
            "overshoot_deg": round(overshoot, 1),
        }
        if not passed:
            all_pass = False
    return Result("D", "Overshoot", all_pass, detail,
                  f"limit <{limit_deg}deg")


# ===================================================================
# STANDALONE TESTS E-H
# ===================================================================

def test_e_tame(runner: Runner, limits: Dict) -> Result:
    """TEST E: 8-position long-hold stability."""
    positions = [0, 45, 90, 135, 180, 225, 270, 315]
    steps = runner.run_sequence(positions, min_s=1.0, max_s=8.0)
    r = analyze_stability(steps, limits["hold_mean_deg"],
                          limits["hold_std_deg"])
    return Result("E", "Tame Holds", r.passed, r.detail, r.notes)


def test_f_fast(runner: Runner, limits: Dict) -> Result:
    """TEST F: rapid transitions — settle speed + overshoot."""
    moves = [0, 180, 45, 225, 90, 270]
    steps = runner.run_sequence(moves, min_s=0.2, max_s=3.0)
    speed_r = analyze_speed(steps, limits["speed_s"])
    overshoot_r = analyze_overshoot(steps, limits["overshoot_deg"])
    passed = speed_r.passed and overshoot_r.passed
    detail = {"speed": speed_r.detail, "overshoot": overshoot_r.detail}
    return Result("F", "Fast Transitions", passed, detail)


def test_g_random(runner: Runner, limits: Dict) -> Result:
    """TEST G: 20 random positions — count settled."""
    positions = SEQUENCES["5_random_walk"]["positions"]
    steps = runner.run_sequence(positions, min_s=0.3, max_s=3.0)
    n_settled = sum(1 for s in steps if s.settled)
    rate = n_settled / len(steps) if steps else 0
    passed = rate >= 0.95
    detail = {"settled": n_settled, "total": len(steps),
              "rate": round(rate, 3)}
    return Result("G", "Random Walk", passed, detail,
                  f"{n_settled}/{len(steps)} ({rate*100:.0f}%)")


def test_h_regression(runner: Runner, limits: Dict) -> Result:
    """TEST H: known problem positions."""
    positions = [5, 22, 355, 359, 178, 182]
    steps = runner.run_sequence(positions, min_s=0.5, max_s=5.0)
    detail = {}
    all_pass = True
    for s in steps:
        settled = s.settled_obs
        key = f"{s.target_deg:.0f}deg"
        if not settled:
            detail[key] = {"pass": False, "note": "never settled"}
            all_pass = False
            continue
        errors = [abs(o.error_deg) for o in settled]
        mean_err = pystats.mean(errors)
        passed = mean_err <= limits["accuracy_mean_deg"]
        detail[key] = {"pass": passed, "mean_err_deg": round(mean_err, 2)}
        if not passed:
            all_pass = False
    return Result("H", "Regression Patterns", all_pass, detail)


# ===================================================================
# SUITE
# ===================================================================

class Suite:
    """Top-level test orchestrator."""

    def __init__(self, port: str, load: str, verbose: bool,
                 tests: Optional[List[str]] = None):
        self.link = DeviceLink(port)
        self.limits = LIMITS[load]
        self.verbose = verbose
        self.tests = ([t.upper() for t in tests] if tests
                      else list("ABCDEFGH"))
        self.results: List[Result] = []
        self.start_time: Optional[float] = None

    def run(self, json_path: Optional[str] = None) -> bool:
        if not self.link.connect():
            return False
        self.start_time = time.time()
        runner = Runner(self.link, self.verbose)

        try:
            lim = self.limits

            # A-D share one cardinal observation
            abcd = [t for t in self.tests if t in "ABCD"]
            if abcd:
                self._log("TESTS A-D on cardinal positions")
                positions = SEQUENCES["1_cardinal"]["positions"]
                steps = runner.run_sequence(
                    positions, min_s=0.3, max_s=5.0)

                analyses = {
                    "A": lambda s=steps: analyze_accuracy(
                        s, lim["accuracy_mean_deg"]),
                    "B": lambda s=steps: analyze_speed(
                        s, lim["speed_s"]),
                    "C": lambda s=steps: analyze_stability(
                        s, lim["hold_mean_deg"], lim["hold_std_deg"]),
                    "D": lambda s=steps: analyze_overshoot(
                        s, lim["overshoot_deg"]),
                }
                for tid in abcd:
                    self.results.append(analyses[tid]())

            # E-H standalone
            standalone = {
                "E": lambda: test_e_tame(runner, lim),
                "F": lambda: test_f_fast(runner, lim),
                "G": lambda: test_g_random(runner, lim),
                "H": lambda: test_h_regression(runner, lim),
            }
            for tid in self.tests:
                if tid in standalone:
                    self.results.append(standalone[tid]())

            self._print_summary()
            if json_path:
                self._export_json(json_path)

            return all(r.passed for r in self.results)
        finally:
            self.link.close()

    def run_matrix(self, json_path: Optional[str] = None) -> bool:
        if not self.link.connect():
            return False
        self.start_time = time.time()
        runner = Runner(self.link, self.verbose)
        lim = self.limits
        matrix: Dict[str, Dict[str, bool]] = {}

        try:
            for seq_id, cfg in SEQUENCES.items():
                self._log(f"\n{'=' * 60}")
                self._log(
                    f"SEQUENCE: {cfg['name']} ({seq_id})")
                self._log(f"{'=' * 60}")

                positions = cfg["positions"][:6]
                try:
                    steps = runner.run_sequence(
                        positions, min_s=0.3, max_s=5.0)
                except Exception as e:
                    self._log(f"  * Observation failed: {e}")
                    matrix[seq_id] = {t: False for t in "ABCD"}
                    continue

                seq_r = {}
                for tid, fn in [
                    ("A", lambda s=steps: analyze_accuracy(
                        s, lim["accuracy_mean_deg"])),
                    ("B", lambda s=steps: analyze_speed(
                        s, lim["speed_s"])),
                    ("C", lambda s=steps: analyze_stability(
                        s, lim["hold_mean_deg"], lim["hold_std_deg"])),
                    ("D", lambda s=steps: analyze_overshoot(
                        s, lim["overshoot_deg"])),
                ]:
                    try:
                        r = fn()
                        seq_r[tid] = r.passed
                        self.results.append(r)
                    except Exception as e:
                        self._log(f"  * TEST {tid}: {e}")
                        seq_r[tid] = False

                matrix[seq_id] = seq_r
                score = sum(1 for v in seq_r.values() if v)
                self._log(f"  => {seq_id}: {score}/4")

            total_time = time.time() - self.start_time
            self._print_matrix(matrix)
            self._log(f"\nMatrix in {total_time:.1f}s")

            if json_path:
                self._export_matrix_json(matrix, json_path)

            total = sum(len(r) for r in matrix.values())
            passed = sum(
                sum(1 for v in r.values() if v)
                for r in matrix.values())
            return (passed / total) >= 0.75 if total else False
        finally:
            self.link.close()

    # -- display helpers -------------------------------------------

    def _log(self, msg: str):
        if self.verbose:
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {msg}")

    def _print_summary(self):
        elapsed = (time.time() - self.start_time
                   if self.start_time else 0)
        print(f"\n{'=' * 60}")
        print("QUALITY GOALS -- SUMMARY")
        print(f"{'=' * 60}")

        total = len(self.results)
        n_pass = sum(1 for r in self.results if r.passed)

        for r in self.results:
            mark = "+" if r.passed else "*"
            print(f"  {mark} Test {r.test_id}: {r.name}  "
                  f"({r.notes})")
            for key, val in r.detail.items():
                if isinstance(val, dict):
                    p = "+" if val.get("pass") else "*"
                    info = "  ".join(
                        f"{k}={v}" for k, v in val.items()
                        if k != "pass")
                    print(f"      {p} {key}: {info}")

        status = ("+ ALL PASSED" if n_pass == total
                  else f"* {total - n_pass} FAILED")
        print(f"\n  {n_pass}/{total} passed  "
              f"({elapsed:.1f}s)  {status}")
        print(f"{'=' * 60}")

    def _print_matrix(self, matrix):
        print(f"\n{'=' * 60}")
        print("SEQUENCE MATRIX")
        print(f"{'=' * 60}")
        header = f"{'Sequence':<26} | A | B | C | D | Score"
        print(header)
        print("-" * len(header))
        for seq_id, results in matrix.items():
            name = SEQUENCES[seq_id]["name"][:24]
            cells = " | ".join(
                "+" if results.get(t) else "*"
                for t in "ABCD")
            score = sum(1 for v in results.values() if v)
            print(f"{name:<26} | {cells} | {score}/4")

    def _export_json(self, path: str):
        out = {
            "timestamp": datetime.now().isoformat(),
            "limits": self.limits,
            "results": [asdict(r) for r in self.results],
        }
        Path(path).write_text(
            json.dumps(out, indent=2, default=str) + "\n")
        print(f"+ Exported to {path}")

    def _export_matrix_json(self, matrix, path: str):
        out = {
            "timestamp": datetime.now().isoformat(),
            "type": "SEQUENCE_MATRIX",
            "limits": self.limits,
            "matrix": matrix,
        }
        Path(path).write_text(
            json.dumps(out, indent=2, default=str) + "\n")
        print(f"+ Matrix exported to {path}")


# ===================================================================
# CLI
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Quality Goals Test Suite v2 "
                    "(observation-based)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 test/quality_goals_test_suite.py
  python3 test/quality_goals_test_suite.py --tests A,B
  python3 test/quality_goals_test_suite.py --matrix
  python3 test/quality_goals_test_suite.py --json out.json
        """,
    )
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--json", help="Export results to JSON")
    parser.add_argument("--matrix", action="store_true",
                        help="A-D across all 6 sequences")
    parser.add_argument("--tests",
                        help="Comma-separated test IDs (A-H)")
    parser.add_argument("--load",
                        choices=["loaded", "unloaded"],
                        default="unloaded")
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()
    test_list = ([t.strip() for t in args.tests.split(",")]
                 if args.tests else None)

    suite = Suite(port=args.port, load=args.load,
                  verbose=not args.quiet, tests=test_list)

    if args.matrix:
        ok = suite.run_matrix(json_path=args.json)
    else:
        ok = suite.run(json_path=args.json)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
