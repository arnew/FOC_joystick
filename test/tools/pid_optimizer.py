#!/usr/bin/env python3
"""
PID Optimizer — Coordinate Descent with Adaptive Step Sizes

Iteratively tunes SimpleFOC PID parameters via Commander serial protocol.
Each evaluation moves to cardinal positions and scores settle performance.

Algorithm:
  For each round, sweep all parameters one at a time.
  For each parameter, try current±step.  Keep the best.
  If a full round produces no improvement → halve all steps.
  Stop when steps fall below min thresholds or max rounds hit.

Safety:
  - Voltage limit (2.0V thermal) is NEVER touched.
  - Best-so-far parameters are tracked; reverts on catastrophic regression.
  - Each parameter has hard bounds (physics + thermal limits).

Usage:
  python3 test/tools/pid_optimizer.py                     # run optimizer
  python3 test/tools/pid_optimizer.py --rounds 5          # limit rounds
  python3 test/tools/pid_optimizer.py --dry-run            # show plan only
  python3 test/tools/pid_optimizer.py --port /dev/ttyACM1  # alt serial port
"""

import serial
import time
import math
import json
import sys
import argparse
import copy
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Tuple

# ===================================================================
# PARAMETER DEFINITIONS
# ===================================================================

@dataclass
class Param:
    """One tunable PID parameter."""
    name: str
    cmd: str           # Commander command prefix (e.g. 'MAP')
    value: float       # current value
    step: float        # current step size
    min_step: float    # convergence threshold
    lo: float          # hard lower bound
    hi: float          # hard upper bound

    def clamp(self, v: float) -> float:
        return max(self.lo, min(self.hi, v))


def default_params() -> List[Param]:
    """Starting parameters — best known values from manual tuning history.

    These are the "iteration 12-14" sweet spot, before the *0.3/*0 degradation.
    The optimizer refines from here rather than starting from degraded values.
    """
    return [
        #              name        cmd   start  step  min_step  lo     hi
        Param("angle_P",   "MAP", 10.0,  2.0,   0.3,   2.0,  25.0),
        Param("angle_I",   "MAI",  0.2,  0.05,  0.01,  0.0,   1.0),
        Param("angle_D",   "MAD",  2.0,  0.5,   0.1,   0.0,   5.0),
        Param("vel_P",     "MVP",  0.2,  0.05,  0.01,  0.02,  1.0),
        Param("vel_I",     "MVI",  0.5,  0.1,   0.02,  0.0,   2.0),
        Param("angle_lim", "MAL",  4.0,  1.0,   0.3,   1.0,  15.0),
        Param("lpf_Tf",    "MAF",  0.01, 0.005, 0.001, 0.001, 0.05),
    ]


# ===================================================================
# COST FUNCTION WEIGHTS
# ===================================================================

COST_WEIGHTS = {
    "unsettled_frac": 50.0,    # fraction of positions that didn't settle
    "mean_error_deg": 15.0,    # mean |error| from last observations (degrees)
    "settle_time_s":   3.0,    # average settle time (seconds)
    "variance_deg2":  30.0,    # mean ACTUAL variance from last obs (degrees²)
    "overshoot_deg":   2.0,    # peak overshoot after first approach (degrees)
}

# Evaluation targets — 4 cardinal directions
EVAL_POSITIONS = [0.0, 90.0, 180.0, 270.0]
EVAL_TIMEOUT_S = 5.0          # max observe time per position
EVAL_MIN_S = 0.3              # min observe time per position
SETTLE_CONSEC = 5             # consecutive settled readings = done


# ===================================================================
# TELEMETRY OBSERVATION
# ===================================================================

@dataclass
class Obs:
    """Single @T telemetry reading."""
    device_ms: int
    target: float       # rad
    actual: float       # rad
    error: float        # rad
    variance: float     # rad²
    settled: bool
    host_t: float


# ===================================================================
# DEVICE LINK
# ===================================================================

class DeviceLink:
    """Serial interface: Commander commands + @T telemetry parsing."""

    def __init__(self, port: str = "/dev/ttyACM0"):
        self.port = port
        self.ser: Optional[serial.Serial] = None

    def connect(self, timeout: float = 10.0) -> bool:
        self.ser = serial.Serial(self.port, 115200, timeout=0.5)
        time.sleep(0.5)
        self.ser.reset_input_buffer()

        deadline = time.time() + timeout
        while time.time() < deadline:
            obs = self._poll_obs()
            if obs is not None:
                log(f"Device live on {self.port}  "
                    f"target={math.degrees(obs.target):.1f}° "
                    f"actual={math.degrees(obs.actual):.1f}°")
                return True
            time.sleep(0.02)
        log("ERROR: No @T telemetry from device")
        return False

    def close(self):
        if self.ser:
            self.ser.close()
            self.ser = None

    def send(self, cmd: str):
        """Send a Commander command (adds newline)."""
        if self.ser:
            self.ser.write(f"{cmd}\n".encode())

    def drain(self):
        if self.ser:
            self.ser.reset_input_buffer()

    def query_param(self, cmd: str) -> Optional[float]:
        """Query a parameter (e.g. 'MAP') and parse the returned value."""
        self.drain()
        self.send(cmd)
        time.sleep(0.2)
        # Read all available lines, look for the PID echo
        deadline = time.time() + 1.0
        while time.time() < deadline:
            if not self.ser or not self.ser.in_waiting:
                time.sleep(0.02)
                continue
            try:
                raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if raw.startswith("@T "):
                    continue
                # Commander echo format: "PID angle| P: 10.000" or "Limits| volt: 2.000"
                if ":" in raw:
                    val_str = raw.split(":")[-1].strip()
                    try:
                        return float(val_str)
                    except ValueError:
                        pass
            except Exception:
                pass
        return None

    def set_param(self, cmd: str, value: float) -> bool:
        """Set a parameter and verify the echo. Returns True if confirmed."""
        self.drain()
        self.send(f"{cmd}{value:.4f}")
        time.sleep(0.15)
        # Read confirmation
        deadline = time.time() + 0.5
        while time.time() < deadline:
            if not self.ser or not self.ser.in_waiting:
                time.sleep(0.02)
                continue
            try:
                raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if raw.startswith("@T "):
                    continue
                if ":" in raw:
                    val_str = raw.split(":")[-1].strip()
                    try:
                        confirmed = float(val_str)
                        if abs(confirmed - value) < 0.01:
                            return True
                    except ValueError:
                        pass
            except Exception:
                pass
        return False

    def send_target(self, angle_deg: float):
        """Send T<deg> target command."""
        self.send(f"T{angle_deg:.2f}")

    def observe(self, target_deg: float,
                min_s: float = EVAL_MIN_S,
                max_s: float = EVAL_TIMEOUT_S) -> Tuple[List[Obs], bool, Optional[float]]:
        """Move to target, observe until settled or timeout.

        Returns: (observations, settled, settle_time_s)
        """
        self.drain()
        self.send_target(target_deg)
        start = time.time()

        observations: List[Obs] = []
        consec_ok = 0
        settle_time: Optional[float] = None

        while True:
            elapsed = time.time() - start
            if elapsed >= max_s:
                break

            obs = self._poll_obs()
            if obs is not None:
                observations.append(obs)
                if obs.settled:
                    consec_ok += 1
                    if settle_time is None:
                        settle_time = elapsed
                    if consec_ok >= SETTLE_CONSEC and elapsed >= min_s:
                        break
                else:
                    consec_ok = 0
                    settle_time = None
            else:
                time.sleep(0.02)

        settled = consec_ok >= SETTLE_CONSEC
        return observations, settled, settle_time

    def _poll_obs(self) -> Optional[Obs]:
        if not self.ser or not self.ser.in_waiting:
            return None
        try:
            raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
            if not raw.startswith("@T "):
                return None
            parts = raw[3:].split(",")
            if len(parts) < 6:
                return None
            return Obs(
                device_ms=int(parts[0]),
                target=float(parts[1]),
                actual=float(parts[2]),
                error=float(parts[3]),
                variance=float(parts[4]),
                settled=parts[5].strip() == "1",
                host_t=time.time(),
            )
        except (ValueError, IndexError, UnicodeDecodeError):
            return None


# ===================================================================
# COST FUNCTION
# ===================================================================

def evaluate(link: DeviceLink, positions: List[float] = EVAL_POSITIONS,
             label: str = "") -> Tuple[float, Dict]:
    """Run positions, compute weighted cost.

    Homes motor to 0° first to avoid transient contamination from PID changes.
    Returns: (cost, detail_dict)
    """
    # Home to 0° and wait for settle before evaluation
    link.drain()
    link.send_target(0.0)
    time.sleep(0.5)
    # Wait for device to report settled (max 3s)
    deadline = time.time() + 3.0
    while time.time() < deadline:
        obs = link._poll_obs()
        if obs and obs.settled:
            break
        time.sleep(0.02)

    n_settled = 0
    errors_deg = []
    settle_times = []
    variances_deg2 = []
    overshoots_deg = []

    for pos in positions:
        obs_list, settled, settle_t = link.observe(pos)

        if not obs_list:
            overshoots_deg.append(20.0)  # penalty
            continue

        # Compute overshoot: peak |error| AFTER first approach (error < 10°)
        # This excludes the initial ramp-down phase
        approached = False
        overshoot = 0.0
        for o in obs_list:
            err_abs = abs(math.degrees(o.error))
            if not approached:
                if err_abs < 10.0:
                    approached = True
            else:
                overshoot = max(overshoot, err_abs)
        overshoots_deg.append(overshoot)

        if settled:
            n_settled += 1
            if settle_t is not None:
                settle_times.append(settle_t)

        # Use last N observations for error/variance (whether settled or not)
        # This gives continuous gradient signal — better than binary penalty
        tail = obs_list[-10:] if len(obs_list) >= 10 else obs_list
        if tail:
            mean_err = sum(abs(math.degrees(o.error)) for o in tail) / len(tail)
            # Convert variance from rad² to deg²: multiply by (180/π)²
            mean_var = sum(o.variance * (180.0/math.pi)**2 for o in tail) / len(tail)
            errors_deg.append(mean_err)
            variances_deg2.append(mean_var)

    n = len(positions)
    detail = {
        "unsettled_frac": 1.0 - n_settled / n if n > 0 else 1.0,
        "mean_error_deg": sum(errors_deg) / len(errors_deg) if errors_deg else 20.0,
        "settle_time_s": sum(settle_times) / len(settle_times) if settle_times else EVAL_TIMEOUT_S,
        "variance_deg2": sum(variances_deg2) / len(variances_deg2) if variances_deg2 else 5.0,
        "overshoot_deg": max(overshoots_deg) if overshoots_deg else 20.0,
    }

    cost = sum(COST_WEIGHTS[k] * detail[k] for k in COST_WEIGHTS)
    detail["cost"] = cost

    if label:
        arrow = "+" if "+" in label else ("-" if "-" in label else "=")
        log(f"  {label:30s} cost={cost:7.2f}  "
            f"settled={n_settled}/{n}  "
            f"err={detail['mean_error_deg']:.2f}°  "
            f"t={detail['settle_time_s']:.2f}s  "
            f"overshoot={detail['overshoot_deg']:.1f}°")

    return cost, detail


# ===================================================================
# OPTIMIZER CORE
# ===================================================================

def read_device_params(link: DeviceLink, params: List[Param]) -> List[Param]:
    """Read current parameter values from device, clamp to bounds."""
    log("Reading current parameters from device...")
    for p in params:
        val = link.query_param(p.cmd)
        if val is not None:
            clamped = p.clamp(val)
            if abs(clamped - val) > 0.001:
                log(f"  {p.name:12s} ({p.cmd}) = {val:.4f} → clamped to {clamped:.4f}")
                p.value = clamped
            else:
                p.value = val
                log(f"  {p.name:12s} ({p.cmd}) = {val:.4f}")
        else:
            log(f"  {p.name:12s} ({p.cmd}) = {p.value:.4f} (fallback)")
    return params


def apply_params(link: DeviceLink, params: List[Param]):
    """Push all parameter values to device via Commander."""
    for p in params:
        ok = link.set_param(p.cmd, p.value)
        if not ok:
            log(f"  WARNING: Could not confirm {p.cmd}{p.value:.4f}")


def optimize(link: DeviceLink, params: List[Param],
             max_rounds: int = 15, patience: int = 3) -> List[Param]:
    """Coordinate descent optimization.

    Returns optimized parameter list.
    """
    # Baseline evaluation
    log("\n=== BASELINE EVALUATION ===")
    apply_params(link, params)
    time.sleep(0.3)
    best_cost, best_detail = evaluate(link, label="baseline")
    best_params = copy.deepcopy(params)

    no_improve_rounds = 0
    history = [{"round": 0, "cost": best_cost, "detail": best_detail,
                "params": {p.name: p.value for p in params}}]

    for rnd in range(1, max_rounds + 1):
        log(f"\n{'='*60}")
        log(f"=== ROUND {rnd}/{max_rounds}  "
            f"best_cost={best_cost:.2f}  "
            f"steps=[{', '.join(f'{p.step:.4f}' for p in params)}]")
        log(f"{'='*60}")

        round_improved = False

        for i, p in enumerate(params):
            if p.step < p.min_step:
                continue  # converged for this param

            original_value = p.value

            # Try +step
            up_value = p.clamp(p.value + p.step)
            if abs(up_value - p.value) > 1e-6:
                link.set_param(p.cmd, up_value)
                time.sleep(0.2)
                up_cost, up_detail = evaluate(link, label=f"{p.name} +step ({up_value:.4f})")
            else:
                up_cost = best_cost + 1  # skip, at boundary

            # Try -step
            dn_value = p.clamp(p.value - p.step)
            if abs(dn_value - p.value) > 1e-6:
                link.set_param(p.cmd, dn_value)
                time.sleep(0.2)
                dn_cost, dn_detail = evaluate(link, label=f"{p.name} -step ({dn_value:.4f})")
            else:
                dn_cost = best_cost + 1

            # Pick best of {current, +step, -step}
            candidates = [
                (best_cost, original_value, "keep"),
                (up_cost, up_value, "+step"),
                (dn_cost, dn_value, "-step"),
            ]
            winner_cost, winner_value, winner_label = min(candidates, key=lambda x: x[0])

            if winner_cost < best_cost - 0.01:
                log(f"  >>> {p.name}: {original_value:.4f} → {winner_value:.4f} "
                    f"({winner_label}) cost {best_cost:.2f} → {winner_cost:.2f}")
                p.value = winner_value
                best_cost = winner_cost
                best_params = copy.deepcopy(params)
                round_improved = True
            else:
                # Revert
                p.value = original_value
                link.set_param(p.cmd, original_value)
                time.sleep(0.05)

        # Round summary
        log(f"\n  Round {rnd} summary: cost={best_cost:.2f}  "
            f"improved={'YES' if round_improved else 'no'}")
        log(f"  Params: {' '.join(f'{p.name}={p.value:.4f}' for p in params)}")

        history.append({
            "round": rnd,
            "cost": best_cost,
            "params": {p.name: p.value for p in params},
            "improved": round_improved,
        })

        if not round_improved:
            no_improve_rounds += 1
            # Halve all step sizes
            for p in params:
                p.step = max(p.min_step, p.step / 2.0)
            log(f"  No improvement — halving steps (patience {no_improve_rounds}/{patience})")

            if no_improve_rounds >= patience:
                log(f"\n*** CONVERGED after {rnd} rounds (patience exhausted)")
                break
        else:
            no_improve_rounds = 0

    # Ensure best params are applied
    for i, p in enumerate(params):
        p.value = best_params[i].value
    apply_params(link, params)

    return params, best_cost, history


# ===================================================================
# REPORTING
# ===================================================================

def print_report(params: List[Param], cost: float, history: list):
    """Print final results and pid_config.h snippet."""
    log(f"\n{'='*60}")
    log("=== OPTIMIZATION COMPLETE")
    log(f"{'='*60}")
    log(f"Final cost: {cost:.2f}")
    log(f"Rounds: {len(history) - 1}")
    log("")

    # Map param names to pid_config.h macros
    macro_map = {
        "angle_P":   "MOTOR0_PID_P",
        "angle_I":   "MOTOR0_PID_I",
        "angle_D":   "MOTOR0_PID_D",
        "vel_P":     "MOTOR0_VELOCITY_P",
        "vel_I":     "MOTOR0_VELOCITY_I",
        "angle_lim": "MOTOR0_VELOCITY_LIMIT",
        "lpf_Tf":    "MOTOR0_LPF_ANGLE_TF",
    }

    log("Optimized parameters:")
    for p in params:
        macro = macro_map.get(p.name, p.name)
        log(f"  {macro:30s} = {p.value:.4f}f")

    log("\npid_config.h snippet:")
    log("// --- Optimizer output (paste into pid_config.h) ---")
    for p in params:
        macro = macro_map.get(p.name, p.name)
        log(f"#define {macro:30s} {p.value:.4f}f")

    log("\nCost history:")
    for h in history:
        improved = h.get("improved", "")
        tag = " *" if improved else ""
        log(f"  Round {h['round']:2d}: cost={h['cost']:7.2f}{tag}")


# ===================================================================
# MAIN
# ===================================================================

def log(msg: str = ""):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def main():
    parser = argparse.ArgumentParser(description="PID Optimizer")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port")
    parser.add_argument("--rounds", type=int, default=15, help="Max rounds")
    parser.add_argument("--patience", type=int, default=3, help="Rounds without improvement before stop")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    parser.add_argument("--json", type=str, help="Export results to JSON file")
    args = parser.parse_args()

    params = default_params()

    if args.dry_run:
        log("=== DRY RUN — Optimization Plan ===")
        log(f"Port: {args.port}")
        log(f"Max rounds: {args.rounds}, patience: {args.patience}")
        log(f"Eval positions: {EVAL_POSITIONS}")
        log(f"Timeout per position: {EVAL_TIMEOUT_S}s")
        log(f"\nParameters to optimize:")
        for p in params:
            log(f"  {p.name:12s} ({p.cmd})  "
                f"start={p.value:.4f}  step={p.step:.4f}  "
                f"bounds=[{p.lo}, {p.hi}]")
        log(f"\nCost weights: {COST_WEIGHTS}")
        log(f"\nEstimated time: ~{args.rounds * len(params) * 2 * (sum([EVAL_TIMEOUT_S]*4)/4 + 0.5):.0f}s worst case")
        return

    log("=== PID Optimizer — Coordinate Descent ===")
    log(f"Port: {args.port}, max_rounds: {args.rounds}, patience: {args.patience}")

    link = DeviceLink(args.port)
    if not link.connect():
        sys.exit(1)

    try:
        # Apply default (best-known) values — don't read device's degraded values
        log("Applying starting parameters to device...")
        apply_params(link, params)
        time.sleep(0.5)
        # Verify by reading back
        params = read_device_params(link, params)

        # Run optimization
        params, best_cost, history = optimize(link, params, args.rounds, args.patience)

        # Report
        print_report(params, best_cost, history)

        # Final validation run
        log("\n=== FINAL VALIDATION ===")
        final_cost, final_detail = evaluate(link, label="final")
        log(f"Validation cost: {final_cost:.2f}")
        for k, v in final_detail.items():
            log(f"  {k}: {v}")

        # Export JSON
        if args.json:
            result = {
                "timestamp": datetime.now().isoformat(),
                "params": {p.name: {"value": p.value, "cmd": p.cmd} for p in params},
                "cost": best_cost,
                "validation_cost": final_cost,
                "validation_detail": final_detail,
                "history": history,
                "weights": COST_WEIGHTS,
            }
            with open(args.json, "w") as f:
                json.dump(result, f, indent=2)
            log(f"Results exported to {args.json}")

    finally:
        link.close()


if __name__ == "__main__":
    main()
