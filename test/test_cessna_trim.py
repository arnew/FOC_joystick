#!/usr/bin/env python3
"""
Cessna Trim Profile — Linearity & Endstop Quality Test

Profile 0 "Cessna Trim": 6480° range (18 full turns), 648 uniform
detents, endstop margin 5°.  This test preserves observed quality by
verifying motor accuracy across the full travel range.

Tests:
  1. Forward sweep  — 7 equidistant positions (0° → 6480°)
  2. Reverse sweep  — same 7 positions (6480° → 0°)
  3. Linearity      — max |error|, slope, hysteresis
  4. Lower endstop  — command past 0° → verify clamping
  5. Upper endstop  — command past 6480° → verify clamping

Usage:
  python3 test/test_cessna_trim.py
  python3 test/test_cessna_trim.py --json cessna_trim_results.json
  python3 test/test_cessna_trim.py --port /dev/ttyACM1
"""

import sys
import time
import math
import json
import argparse
import statistics as pystats
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple

# Import shared infrastructure from the quality suite
sys.path.insert(0, str(Path(__file__).parent))
from quality_goals_test_suite import DeviceLink, Runner, Step, Result


# ===================================================================
# PROFILE CONSTANTS (must match config.h PROFILE_CESSNA_TRIM)
# ===================================================================

PROFILE_ID       = 0        # PROFILE_CESSNA_TRIM
RANGE_DEG        = 6480.0
CENTER_DEG       = 3240.0
ENDSTOP_MARGIN   = 5.0
DETENT_COUNT     = 648
LO_DEG           = CENTER_DEG - RANGE_DEG / 2.0   # 0.0
HI_DEG           = CENTER_DEG + RANGE_DEG / 2.0    # 6480.0

# Sweep: 7 points at 0%, 17%, 33%, 50%, 67%, 83%, 100% of range
SWEEP_POSITIONS  = [LO_DEG + i * RANGE_DEG / 6.0 for i in range(7)]
# → [0, 1080, 2160, 3240, 4320, 5400, 6480]

# ===================================================================
# ACCEPTANCE LIMITS
# ===================================================================

MAX_ERROR_DEG        = 10.0    # max |error| at any sweep point
MAX_HYSTERESIS_DEG   = 8.0     # max |fwd_err - rev_err| at same position
MAX_SLOPE_DEG_PER_DEG = 0.005  # linearity: |d(error)/d(position)|
ENDSTOP_OVERSHOOT_DEG = 15.0   # max beyond range when commanding past
SETTLE_TIMEOUT_S     = 30.0    # generous — 1080° steps are big moves


# ===================================================================
# ANALYSIS
# ===================================================================

@dataclass
class SweepPoint:
    """One observation in the linearity sweep."""
    commanded_deg: float
    actual_deg: float
    error_deg: float
    settled: bool
    settle_s: Optional[float]


def collect_sweep(runner: Runner, positions: List[float],
                  direction: str) -> List[SweepPoint]:
    """Run a sequence of positions, return per-point summary."""
    runner.log(f"  {direction.upper()} SWEEP: {len(positions)} points "
               f"({positions[0]:.0f}° → {positions[-1]:.0f}°)")
    runner.log(f"  {'target':>10} | {'error':>12} | {'settle':>8} | result")
    runner.log(f"  {'----------':>10} | {'------------':>12} | "
               f"{'--------':>8} | ----------")

    points: List[SweepPoint] = []
    for deg in positions:
        step = runner.move_and_observe(deg, min_s=1.0,
                                       max_s=SETTLE_TIMEOUT_S)
        if step.obs:
            last = step.obs[-1]
            sp = SweepPoint(
                commanded_deg=deg,
                actual_deg=last.actual_deg,
                error_deg=last.error_deg,
                settled=step.settled,
                settle_s=step.settle_time_s,
            )
        else:
            sp = SweepPoint(
                commanded_deg=deg, actual_deg=float('nan'),
                error_deg=float('nan'), settled=False, settle_s=None)
        points.append(sp)
    return points


def analyze_linearity(fwd: List[SweepPoint],
                      rev: List[SweepPoint]) -> Result:
    """Combine forward + reverse sweep into linearity verdict."""
    detail: Dict = {"forward": [], "reverse": []}
    all_errors: List[float] = []
    hysteresis_values: List[float] = []

    for sp in fwd:
        d = {"pos": sp.commanded_deg, "error": round(sp.error_deg, 2),
             "settled": sp.settled}
        detail["forward"].append(d)
        if sp.settled:
            all_errors.append(abs(sp.error_deg))

    for sp in rev:
        d = {"pos": sp.commanded_deg, "error": round(sp.error_deg, 2),
             "settled": sp.settled}
        detail["reverse"].append(d)
        if sp.settled:
            all_errors.append(abs(sp.error_deg))

    # Hysteresis: compare forward and reverse at same positions
    for f, r in zip(fwd, rev):
        if f.settled and r.settled:
            hysteresis_values.append(abs(f.error_deg - r.error_deg))

    # Linear regression: error vs position → slope
    settled_fwd = [(sp.commanded_deg, sp.error_deg)
                   for sp in fwd if sp.settled]
    slope = _linear_slope(settled_fwd) if len(settled_fwd) >= 3 else 0.0

    max_err = max(all_errors) if all_errors else float('inf')
    max_hyst = max(hysteresis_values) if hysteresis_values else float('inf')
    n_settled = sum(1 for sp in fwd + rev if sp.settled)
    n_total = len(fwd) + len(rev)

    passed = (max_err <= MAX_ERROR_DEG
              and max_hyst <= MAX_HYSTERESIS_DEG
              and abs(slope) <= MAX_SLOPE_DEG_PER_DEG
              and n_settled == n_total)

    detail["summary"] = {
        "max_error_deg": round(max_err, 2),
        "max_hysteresis_deg": round(max_hyst, 2),
        "linearity_slope": round(slope, 6),
        "settled_ratio": f"{n_settled}/{n_total}",
    }
    notes = (f"max_err={max_err:.1f}° hyst={max_hyst:.1f}° "
             f"slope={slope:.5f}")
    return Result("LIN", "Linearity", passed, detail, notes)


def analyze_endstop(steps: List[Step], which: str,
                    boundary_deg: float) -> Result:
    """Verify endstop clamping."""
    detail: Dict = {}
    all_pass = True

    for step in steps:
        key = f"cmd_{step.target_deg:.0f}deg"
        if not step.obs:
            detail[key] = {"pass": False, "note": "no telemetry"}
            all_pass = False
            continue

        last = step.obs[-1]
        actual = last.actual_deg

        if which == "lower":
            overshoot = max(0, LO_DEG - actual)
        else:
            overshoot = max(0, actual - HI_DEG)

        ok = overshoot <= ENDSTOP_OVERSHOOT_DEG
        detail[key] = {
            "pass": ok,
            "actual_deg": round(actual, 2),
            "error_deg": round(last.error_deg, 2),
            "overshoot_past_range_deg": round(overshoot, 2),
            "settled": step.settled,
        }
        if not ok:
            all_pass = False

    notes = f"{which} endstop @ {boundary_deg:.0f}°"
    return Result(f"END_{which[0].upper()}", f"Endstop {which.title()}",
                  all_pass, detail, notes)


def _linear_slope(points: List[Tuple[float, float]]) -> float:
    """Ordinary least-squares slope of (x, y) pairs."""
    n = len(points)
    if n < 2:
        return 0.0
    xs, ys = zip(*points)
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in points)
    ss_xx = sum((x - x_mean) ** 2 for x in xs)
    if ss_xx == 0:
        return 0.0
    return ss_xy / ss_xx


# ===================================================================
# TEST RUNNER
# ===================================================================

def run_cessna_trim_test(port: str, json_path: Optional[str],
                         verbose: bool) -> bool:
    """Main test entry point."""
    link = DeviceLink(port=port)
    if not link.connect(timeout=10.0):
        return False

    # Switch to Cessna Trim profile
    print(f"\n{'=' * 64}")
    print("CESSNA TRIM LINEARITY & ENDSTOP TEST")
    print(f"{'=' * 64}")
    print(f"  Profile:  #{PROFILE_ID} — range {RANGE_DEG:.0f}° "
          f"({RANGE_DEG/360:.0f} turns), {DETENT_COUNT} detents")
    print(f"  Sweep:    {len(SWEEP_POSITIONS)} points, "
          f"{SWEEP_POSITIONS[0]:.0f}° → {SWEEP_POSITIONS[-1]:.0f}°")
    print(f"  Limits:   err≤{MAX_ERROR_DEG}° "
          f"hyst≤{MAX_HYSTERESIS_DEG}° "
          f"slope≤{MAX_SLOPE_DEG_PER_DEG}")
    print()

    if not link.switch_profile(PROFILE_ID):
        print("* Failed to switch to Cessna Trim profile")
        return False

    # Reconnect after profile switch (causes reboot)
    link = DeviceLink(port=port)
    if not link.connect(timeout=15.0):
        print("* Device did not come back after profile switch")
        return False

    runner = Runner(link, verbose=verbose)
    results: List[Result] = []
    start = time.time()

    try:
        # ---- 1. Forward sweep ----
        fwd = collect_sweep(runner, SWEEP_POSITIONS, "forward")

        # ---- 2. Reverse sweep ----
        rev = collect_sweep(runner, list(reversed(SWEEP_POSITIONS)),
                            "reverse")
        # Reverse the rev list so indices match fwd positions
        rev_aligned = list(reversed(rev))

        # ---- 3. Linearity analysis ----
        lin_result = analyze_linearity(fwd, rev_aligned)
        results.append(lin_result)

        # ---- 4. Lower endstop test ----
        runner.log("  LOWER ENDSTOP TEST")
        lo_steps = []
        # Move to near lower end first
        runner.move_and_observe(100.0, min_s=1.0, max_s=15.0)
        # Command to edge
        lo_steps.append(
            runner.move_and_observe(ENDSTOP_MARGIN, min_s=2.0,
                                   max_s=SETTLE_TIMEOUT_S))
        # Command past lower endstop
        lo_steps.append(
            runner.move_and_observe(-100.0, min_s=2.0,
                                   max_s=SETTLE_TIMEOUT_S))
        lo_result = analyze_endstop(lo_steps, "lower", LO_DEG)
        results.append(lo_result)

        # ---- 5. Upper endstop test ----
        runner.log("  UPPER ENDSTOP TEST")
        hi_steps = []
        # Move to near upper end first
        runner.move_and_observe(RANGE_DEG - 100.0, min_s=1.0,
                                max_s=SETTLE_TIMEOUT_S)
        # Command to edge
        hi_steps.append(
            runner.move_and_observe(RANGE_DEG - ENDSTOP_MARGIN,
                                   min_s=2.0, max_s=SETTLE_TIMEOUT_S))
        # Command past upper endstop
        hi_steps.append(
            runner.move_and_observe(RANGE_DEG + 100.0, min_s=2.0,
                                   max_s=SETTLE_TIMEOUT_S))
        hi_result = analyze_endstop(hi_steps, "upper", HI_DEG)
        results.append(hi_result)

    finally:
        link.close()

    elapsed = time.time() - start

    # ---- Print summary ----
    print(f"\n{'=' * 64}")
    print("CESSNA TRIM -- RESULTS")
    print(f"{'=' * 64}")

    n_pass = 0
    for r in results:
        mark = "+" if r.passed else "*"
        print(f"  {mark} {r.name}  ({r.notes})")
        if r.test_id == "LIN":
            s = r.detail.get("summary", {})
            print(f"      max_error:    {s.get('max_error_deg', '?')}°"
                  f"  (limit ≤{MAX_ERROR_DEG}°)")
            print(f"      hysteresis:   {s.get('max_hysteresis_deg', '?')}°"
                  f"  (limit ≤{MAX_HYSTERESIS_DEG}°)")
            print(f"      slope:        {s.get('linearity_slope', '?')}"
                  f"  (limit ≤±{MAX_SLOPE_DEG_PER_DEG})")
            print(f"      settled:      {s.get('settled_ratio', '?')}")
        else:
            for key, val in r.detail.items():
                if isinstance(val, dict):
                    p = "+" if val.get("pass") else "*"
                    info = "  ".join(
                        f"{k}={v}" for k, v in val.items()
                        if k != "pass")
                    print(f"      {p} {key}: {info}")
        if r.passed:
            n_pass += 1

    total = len(results)
    status = "+ ALL PASSED" if n_pass == total else f"* {total - n_pass} FAILED"
    print(f"\n  {n_pass}/{total} passed  ({elapsed:.1f}s)  {status}")
    print(f"{'=' * 64}")

    # ---- Export JSON ----
    if json_path:
        out = {
            "timestamp": datetime.now().isoformat(),
            "test": "cessna_trim_linearity",
            "profile": {
                "id": PROFILE_ID,
                "range_deg": RANGE_DEG,
                "center_deg": CENTER_DEG,
                "detent_count": DETENT_COUNT,
                "endstop_margin": ENDSTOP_MARGIN,
            },
            "limits": {
                "max_error_deg": MAX_ERROR_DEG,
                "max_hysteresis_deg": MAX_HYSTERESIS_DEG,
                "max_slope": MAX_SLOPE_DEG_PER_DEG,
                "endstop_overshoot_deg": ENDSTOP_OVERSHOOT_DEG,
            },
            "results": [asdict(r) for r in results],
            "elapsed_s": round(elapsed, 1),
            "passed": n_pass == total,
        }
        Path(json_path).write_text(
            json.dumps(out, indent=2, default=str) + "\n")
        print(f"+ Exported to {json_path}")

    return n_pass == total


# ===================================================================
# CLI
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Cessna Trim linearity & endstop quality test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sweeps the full 6480° range (18 turns) forward and reverse,
then tests both endstops.  Measures accuracy, hysteresis,
linearity slope, and endstop clamping.

Examples:
  python3 test/test_cessna_trim.py
  python3 test/test_cessna_trim.py --json results.json
  python3 test/test_cessna_trim.py --port /dev/ttyACM1
        """,
    )
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--json", help="Export results to JSON")
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()
    ok = run_cessna_trim_test(port=args.port, json_path=args.json,
                              verbose=not args.quiet)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
