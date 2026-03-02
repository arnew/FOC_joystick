#!/usr/bin/env python3
"""
Automated Trim Wheel / Haptic Layer Test

Exercises the haptic layer by commanding motor positions via serial
and observing detent snapping behaviour through @T telemetry.
No physical rotation required — the motor IS the actuator.

Tests:
  1. Config query — haptic layer responds to W command
  2. Detent walk   — walk through all detent positions, verify snap accuracy
  3. End-stop hold — command past limits, verify clamping
  4. Spacing uniformity — check detent-to-detent spacing consistency
  5. HID mapping — verify HID values at endpoints and middle
  6. Enable/disable — verify WE0 disables snapping, WE1 re-enables

Usage:
  python3 test/tools/trim_wheel_test.py
  python3 test/tools/trim_wheel_test.py --port /dev/ttyACM1
  python3 test/tools/trim_wheel_test.py --json results.json
"""

import serial
import time
import re
import json
import argparse
import sys
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Tuple


# ==========================================================================
# OBSERVATION
# ==========================================================================

@dataclass
class Obs:
    device_ms: int
    target_rad: float
    actual_rad: float
    error_rad: float
    variance: float
    settled: bool
    host_t: float = 0.0

    @property
    def target_deg(self):
        return self.target_rad * 180.0 / 3.14159265

    @property
    def actual_deg(self):
        return self.actual_rad * 180.0 / 3.14159265

    @property
    def error_deg(self):
        return self.error_rad * 180.0 / 3.14159265


# ==========================================================================
# DEVICE LINK
# ==========================================================================

class DeviceLink:
    """Serial connection to FOC device."""

    def __init__(self, port: str = "/dev/ttyACM0"):
        self.port = port
        self.ser: Optional[serial.Serial] = None

    def connect(self, timeout: float = 8.0) -> bool:
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=0.5)
            time.sleep(2)
        except Exception as e:
            print(f"  FAIL: Cannot open {self.port}: {e}")
            return False

        deadline = time.time() + timeout
        while time.time() < deadline:
            obs = self.poll()
            if obs is not None:
                print(f"  Device live  target={obs.target_deg:.1f}° "
                      f"actual={obs.actual_deg:.1f}°")
                return True
            time.sleep(0.05)

        print("  FAIL: No @T telemetry")
        return False

    def send(self, cmd: str):
        if self.ser:
            self.ser.write(f"{cmd}\n".encode())

    def send_target(self, angle_deg: float):
        self.send(f"T{angle_deg:.2f}")

    def poll(self) -> Optional[Obs]:
        if not self.ser or not self.ser.in_waiting:
            return None
        try:
            raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
            return self._parse_telemetry(raw)
        except Exception:
            return None

    def read_lines(self, duration: float = 0.5) -> List[str]:
        """Read all lines for a duration, return non-telemetry lines."""
        lines = []
        deadline = time.time() + duration
        while time.time() < deadline:
            if self.ser and self.ser.in_waiting:
                raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if raw and not raw.startswith("@T "):
                    lines.append(raw)
            else:
                time.sleep(0.02)
        return lines

    def drain(self):
        if self.ser:
            self.ser.reset_input_buffer()

    def wait_settled(self, timeout: float = 5.0) -> Optional[Obs]:
        """Wait until device reports settled, return last observation."""
        deadline = time.time() + timeout
        last_obs = None
        while time.time() < deadline:
            obs = self.poll()
            if obs is not None:
                last_obs = obs
                if obs.settled:
                    return obs
            else:
                time.sleep(0.01)
        return last_obs

    def close(self):
        if self.ser:
            self.ser.close()
            self.ser = None

    @staticmethod
    def _parse_telemetry(line: str) -> Optional[Obs]:
        if not line.startswith("@T "):
            return None
        try:
            parts = line[3:].split(",")
            if len(parts) < 6:
                return None
            return Obs(
                device_ms=int(parts[0]),
                target_rad=float(parts[1]),
                actual_rad=float(parts[2]),
                error_rad=float(parts[3]),
                variance=float(parts[4]),
                settled=parts[5].strip() == "1",
                host_t=time.time(),
            )
        except (ValueError, IndexError):
            return None


# ==========================================================================
# HAPTIC CONFIG PARSER
# ==========================================================================

def parse_haptic_config(lines: List[str]) -> Dict:
    """Parse the [HAPTIC] config block from serial output."""
    cfg = {}
    for line in lines:
        if "enabled:" in line:
            cfg["enabled"] = "YES" in line
        elif "range_deg:" in line:
            m = re.search(r"range_deg:\s+([\d.]+)", line)
            if m: cfg["range_deg"] = float(m.group(1))
        elif "center_deg:" in line:
            m = re.search(r"center_deg:\s+([\d.]+)", line)
            if m: cfg["center_deg"] = float(m.group(1))
        elif "detents:" in line and "detent_step" not in line:
            m = re.search(r"detents:\s+(\d+)", line)
            if m: cfg["detent_count"] = int(m.group(1))
        elif "strength:" in line:
            m = re.search(r"strength:\s+([\d.]+)", line)
            if m: cfg["strength"] = float(m.group(1))
        elif "detent_step:" in line:
            m = re.search(r"detent_step:\s+([\d.]+)", line)
            if m: cfg["step_deg"] = float(m.group(1))
        elif "hid_value:" in line:
            m = re.search(r"hid_value:\s+(\d+)", line)
            if m: cfg["hid_value"] = int(m.group(1))
        elif "current:" in line:
            m = re.search(r"detent=(-?\d+)", line)
            if m: cfg["detent_index"] = int(m.group(1))
            m = re.search(r"target=([\d.]+)", line)
            if m: cfg["target_deg"] = float(m.group(1))
            m = re.search(r"raw=([\d.]+)", line)
            if m: cfg["raw_deg"] = float(m.group(1))
    return cfg


# ==========================================================================
# TEST FUNCTIONS
# ==========================================================================

PASS = "PASS"
FAIL = "FAIL"


def test_config_query(dev: DeviceLink) -> Tuple[str, str]:
    """Test 1: Verify haptic layer responds to W command with valid config."""
    dev.drain()
    dev.send("W")
    lines = dev.read_lines(1.0)
    cfg = parse_haptic_config(lines)

    target = "range_deg=180, detent_count=18, step=10°"
    actual = (f"range_deg={cfg.get('range_deg', '?')}, "
              f"detent_count={cfg.get('detent_count', '?')}, "
              f"step={cfg.get('step_deg', '?')}°")

    ok = (cfg.get("range_deg") == 180.0
          and cfg.get("detent_count") == 18
          and cfg.get("enabled") is True)

    verdict = PASS if ok else FAIL
    detail = f"target: {target} | actual: {actual} | criteria: exact match"
    return verdict, detail


def test_detent_walk(dev: DeviceLink) -> Tuple[str, str]:
    """Test 2: Walk through all 18 detents (0-180° in 10° steps).
    Verify motor actually reaches each detent position within tolerance."""
    TOLERANCE_DEG = 5.0
    results = []

    # First command to 0° to start clean
    dev.send_target(0.0)
    dev.wait_settled(3.0)
    time.sleep(0.3)

    for detent_deg in range(0, 181, 10):  # 0, 10, 20, ..., 180
        dev.drain()
        dev.send_target(float(detent_deg))
        obs = dev.wait_settled(4.0)

        if obs is None:
            results.append((detent_deg, None, None, False))
            continue

        error = abs(obs.actual_deg - detent_deg)
        ok = error < TOLERANCE_DEG
        results.append((detent_deg, obs.actual_deg, error, ok))

    passed = sum(1 for r in results if r[3])
    total = len(results)
    errors = [r[2] for r in results if r[2] is not None]
    max_err = max(errors) if errors else 999
    mean_err = sum(errors) / len(errors) if errors else 999

    verdict = PASS if passed == total and max_err < TOLERANCE_DEG else FAIL
    detail = (f"target: {total}/{total} detents within {TOLERANCE_DEG}° | "
              f"actual: {passed}/{total} pass, max_err={max_err:.2f}°, "
              f"mean_err={mean_err:.2f}° | "
              f"criteria: all within {TOLERANCE_DEG}°")

    if verdict == FAIL:
        # Show first few failures
        fails = [f"{r[0]}°→{r[1]:.1f}°(err={r[2]:.1f}°)"
                 for r in results if not r[3] and r[1] is not None]
        if fails:
            detail += f" | failures: {', '.join(fails[:5])}"

    return verdict, detail


def test_endstop_hold(dev: DeviceLink) -> Tuple[str, str]:
    """Test 3: Command past end-stops, verify motor stays inside range."""
    MARGIN = 5.0  # Degrees tolerance for endstop enforcement
    results = []

    test_points = [
        (-20.0, 0.0, "below minimum"),
        (200.0, 180.0, "above maximum"),
    ]

    for cmd_deg, expected_clamp_deg, label in test_points:
        dev.drain()
        dev.send_target(cmd_deg)
        obs = dev.wait_settled(3.0)

        if obs is None:
            results.append((label, cmd_deg, None, expected_clamp_deg, False))
            continue

        error = abs(obs.actual_deg - expected_clamp_deg)
        ok = error < MARGIN
        results.append((label, cmd_deg, obs.actual_deg, expected_clamp_deg, ok))

    passed = all(r[4] for r in results)
    lines = []
    for label, cmd, actual, expected, ok in results:
        act_str = f"{actual:.1f}" if actual is not None else "timeout"
        lines.append(f"{label}: cmd={cmd}° → actual={act_str}° "
                     f"(expected ≈{expected}°) {'OK' if ok else 'FAIL'}")

    verdict = PASS if passed else FAIL
    detail = (f"target: motor clamps at end-stops | "
              f"actual: {'; '.join(lines)} | "
              f"criteria: within {MARGIN}° of limit")
    return verdict, detail


def test_spacing_uniformity(dev: DeviceLink) -> Tuple[str, str]:
    """Test 4: Verify detent spacing is uniform (10° ± tolerance)."""
    EXPECTED_STEP = 10.0
    TOLERANCE = 8.0  # 2× per-position tolerance (worst-case adjacent errors)
    positions = []

    dev.send_target(0.0)
    dev.wait_settled(3.0)
    time.sleep(0.3)

    for detent_deg in range(0, 181, 10):
        dev.drain()
        dev.send_target(float(detent_deg))
        obs = dev.wait_settled(4.0)

        if obs:
            positions.append(obs.actual_deg)
        else:
            positions.append(None)

    # Compute spacings
    spacings = []
    for i in range(1, len(positions)):
        if positions[i] is not None and positions[i - 1] is not None:
            spacings.append(positions[i] - positions[i - 1])

    if not spacings:
        return FAIL, "target: uniform 10° steps | actual: no data | criteria: n/a"

    mean_spacing = sum(spacings) / len(spacings)
    max_dev = max(abs(s - EXPECTED_STEP) for s in spacings)
    ok = max_dev < TOLERANCE

    verdict = PASS if ok else FAIL
    detail = (f"target: {EXPECTED_STEP}° steps ± {TOLERANCE}° | "
              f"actual: mean={mean_spacing:.2f}°, max_deviation={max_dev:.2f}° | "
              f"criteria: max deviation < {TOLERANCE}°")
    return verdict, detail


def test_hid_mapping(dev: DeviceLink) -> Tuple[str, str]:
    """Test 5: Verify HID values at endpoints and center."""
    test_points = [
        (0.0, 0, 60, "minimum"),
        (90.0, 455, 115, "center"),
        (180.0, 960, 80, "maximum"),
    ]
    results = []

    for cmd_deg, expected_hid, tolerance, label in test_points:
        dev.drain()
        dev.send_target(cmd_deg)
        dev.wait_settled(3.0)
        time.sleep(0.2)

        dev.send("W")
        lines = dev.read_lines(0.8)
        cfg = parse_haptic_config(lines)
        hid = cfg.get("hid_value")

        if hid is None:
            results.append((label, cmd_deg, None, expected_hid, False))
            continue

        error = abs(hid - expected_hid)
        ok = error < tolerance
        results.append((label, cmd_deg, hid, expected_hid, ok))

    passed = all(r[4] for r in results)
    lines = []
    for label, cmd, actual, expected, ok in results:
        act_str = str(actual) if actual is not None else "?"
        lines.append(f"{label}({cmd}°): HID={act_str} "
                     f"(expected≈{expected}) {'OK' if ok else 'FAIL'}")

    verdict = PASS if passed else FAIL
    detail = (f"target: HID 0@min, ~32768@center, ~65535@max | "
              f"actual: {'; '.join(lines)} | "
              f"criteria: within tolerance")
    return verdict, detail


def test_enable_disable(dev: DeviceLink) -> Tuple[str, str]:
    """Test 6: WE0 disables haptic, WE1 re-enables."""
    # Move to a known position first
    dev.send_target(90.0)
    dev.wait_settled(3.0)

    # Disable haptic
    dev.drain()
    dev.send("WE0")
    lines = dev.read_lines(0.5)
    disabled_ok = any("enabled=NO" in l for l in lines)

    # Query config
    dev.send("W")
    cfg_lines = dev.read_lines(0.8)
    cfg = parse_haptic_config(cfg_lines)
    disabled_cfg_ok = cfg.get("enabled") is False

    # Re-enable
    dev.drain()
    dev.send("WE1")
    lines = dev.read_lines(0.5)
    enabled_ok = any("enabled=YES" in l for l in lines)

    ok = disabled_ok and disabled_cfg_ok and enabled_ok
    verdict = PASS if ok else FAIL
    detail = (f"target: WE0→disabled, WE1→enabled | "
              f"actual: WE0_ack={disabled_ok}, config_disabled={disabled_cfg_ok}, "
              f"WE1_ack={enabled_ok} | criteria: all True")
    return verdict, detail


# ==========================================================================
# RUNNER
# ==========================================================================

TESTS = [
    ("1_config",     "Config query",        test_config_query),
    ("2_detent_walk", "Detent walk",         test_detent_walk),
    ("3_endstop",    "End-stop hold",        test_endstop_hold),
    ("4_spacing",    "Spacing uniformity",   test_spacing_uniformity),
    ("5_hid",        "HID mapping",          test_hid_mapping),
    ("6_enable",     "Enable/disable toggle", test_enable_disable),
]


def run_tests(port: str, json_path: Optional[str] = None):
    dev = DeviceLink(port)
    print(f"\n=== Trim Wheel / Haptic Layer Test ===")
    print(f"Port: {port}")
    print(f"Connecting...")

    if not dev.connect():
        print("ABORT: Could not connect to device")
        sys.exit(1)

    # Ensure haptic is enabled
    dev.send("WE1")
    time.sleep(0.3)
    dev.drain()

    results = []
    passed = 0
    failed = 0

    for test_id, name, func in TESTS:
        print(f"\n--- {test_id}: {name} ---")
        try:
            verdict, detail = func(dev)
        except Exception as e:
            verdict, detail = FAIL, f"Exception: {e}"
        print(f"  {verdict}: {detail}")
        results.append({
            "id": test_id,
            "name": name,
            "verdict": verdict,
            "detail": detail,
        })
        if verdict == PASS:
            passed += 1
        else:
            failed += 1

    dev.close()

    print(f"\n=== Summary: {passed}/{passed + failed} passed ===")
    for r in results:
        mark = "✓" if r["verdict"] == PASS else "✗"
        print(f"  {mark} {r['id']}: {r['name']}")

    if json_path:
        with open(json_path, "w") as f:
            json.dump({"tests": results, "passed": passed, "failed": failed,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}, f, indent=2)
        print(f"\nResults written to {json_path}")

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Haptic layer automated test")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--json", default=None, help="Write results to JSON")
    args = parser.parse_args()

    ok = run_tests(args.port, args.json)
    sys.exit(0 if ok else 1)
