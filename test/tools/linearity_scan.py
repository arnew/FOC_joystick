#!/usr/bin/env python3
"""
Linearity Scanner — verify motor→detent→HID mapping across the full range.

Reads serial HAPTIC_DIAG telemetry and evdev joystick values simultaneously.
Turn the wheel slowly from endstop to endstop; the tool checks that the
HID axis value tracks the snap position linearly.

Features:
  • Auto-detects range from firmware config (sends "W" command)
  • Live bargraph showing coverage and per-bin linearity error
  • Endstop bounceback measurement (how far HID springs back)
  • Final report with per-bin stats and overall linearity grade

Usage:
    python3 test/tools/linearity_scan.py
    python3 test/tools/linearity_scan.py --bins 60
    python3 test/tools/linearity_scan.py --port /dev/ttyACM0

Ctrl+C to stop and print report.
"""

import argparse
import fcntl
import glob
import math
import os
import re
import select
import serial
import struct
import subprocess
import sys
import termios
import threading
import time
import tty
from dataclasses import dataclass, field


# ── Constants ────────────────────────────────────────────────────────

EV_ABS = 3
ABS_X = 0
EVDEV_FMT = "llHHi"
EVDEV_SIZE = struct.calcsize(EVDEV_FMT)

# ANSI
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"
CLEAR  = "\033[2J\033[H"


# ── Device discovery ─────────────────────────────────────────────────

def find_serial_port():
    ports = sorted(glob.glob("/dev/ttyACM*"))
    return ports[0] if ports else None


def find_foc_evdev():
    """Return evdev path for the FOC joystick."""
    try:
        with open("/proc/bus/input/devices") as f:
            text = f.read()
        for block in text.split("\n\n"):
            if "FOC" not in block:
                continue
            for line in block.splitlines():
                if line.startswith("H: Handlers="):
                    for tok in line.replace("=", " ").split():
                        if tok.startswith("event"):
                            return f"/dev/input/{tok}"
    except Exception:
        pass
    return None


# ── evdev helpers ────────────────────────────────────────────────────

def _eviocgabs(axis):
    """EVIOCGABS(axis) ioctl number — reads struct input_absinfo."""
    # _IOR('E', 0x40+axis, 24)  — 24 = sizeof(struct input_absinfo)
    return (2 << 30) | (24 << 16) | (0x45 << 8) | (0x40 + axis)


def read_absinfo(fd, axis):
    """Read initial absinfo via ioctl.  Returns (value, min, max, fuzz, flat)."""
    buf = bytearray(24)
    fcntl.ioctl(fd, _eviocgabs(axis), buf)
    value, mn, mx, fuzz, flat, _res = struct.unpack("iiiiii", buf)
    return value, mn, mx, fuzz, flat


def fix_evdev_deadzone(evdev_path):
    """Zero fuzz/flat on the evdev device (no root needed)."""
    try:
        for param in ["deadzone", "fuzz"]:
            subprocess.run(
                ["evdev-joystick", "--evdev", evdev_path, f"--{param}", "0"],
                capture_output=True, timeout=5)
        return True
    except FileNotFoundError:
        return False


# ── Data structures ──────────────────────────────────────────────────

@dataclass
class Sample:
    motor_deg: float
    snap_deg:  float
    detent:    int
    hid_value: int
    timestamp: float


@dataclass
class Bin:
    """Accumulator for one range slice."""
    hid_sum:   float = 0.0
    motor_sum: float = 0.0
    snap_sum:  float = 0.0
    count:     int   = 0
    hid_min:   int   = 65535
    hid_max:   int   = 0

    def add(self, s: Sample):
        self.hid_sum   += s.hid_value
        self.motor_sum += s.motor_deg
        self.snap_sum  += s.snap_deg
        self.count     += 1
        self.hid_min    = min(self.hid_min, s.hid_value)
        self.hid_max    = max(self.hid_max, s.hid_value)

    @property
    def mean_hid(self):
        return self.hid_sum / self.count if self.count else None

    @property
    def mean_snap(self):
        return self.snap_sum / self.count if self.count else None


@dataclass
class EndstopEvent:
    """One endstop approach + release observation."""
    hit_hid:     int        # HID value when endstop was reached
    bounce_hid:  int        # HID value after release/settle
    hit_snap:    float
    bounce_snap: float
    timestamp:   float


# ── Main scanner class ───────────────────────────────────────────────

class LinearityScan:

    def __init__(self, num_bins=40, port=None, evdev_path=None):
        self.num_bins   = num_bins
        self.port       = port or find_serial_port()
        self.evdev_path = evdev_path or find_foc_evdev()

        # Firmware config (populated by _query_config)
        self.range_deg  = None   # total travel
        self.center_deg = None
        self.range_min  = None   # center - range/2
        self.range_max  = None   # center + range/2
        self.detent_count = None
        self.profile_name = None

        # Live state (updated by reader threads)
        self.motor_deg = 0.0
        self.snap_deg  = 0.0
        self.detent    = 0
        self.velocity  = 0.0
        self.hid_value = 0
        self._serial_alive = False

        # Bins and samples
        self.bins = [Bin() for _ in range(num_bins)]
        self.sample_count = 0
        self.last_bin_idx = -1

        # Endstop tracking
        self.low_endstop_events  = []
        self.high_endstop_events = []
        self._at_low  = False
        self._at_high = False
        self._endstop_hid  = 0
        self._endstop_snap = 0.0

        # Control
        self._stop  = threading.Event()
        self._ser   = None

    # ── Setup ────────────────────────────────────────────────────

    def _check_prerequisites(self):
        if not self.port:
            print("✗ No serial port found (--port)")
            sys.exit(1)
        if not self.evdev_path:
            print("✗ No evdev device found — is the FOC joystick connected?")
            sys.exit(1)

    def _query_config(self):
        """Send 'W' command and parse haptic config from firmware."""
        ser = serial.Serial(self.port, 115200, timeout=0.5)
        time.sleep(0.3)
        ser.reset_input_buffer()
        ser.write(b"W\n")
        time.sleep(0.5)

        lines = []
        deadline = time.time() + 2.0
        while time.time() < deadline:
            raw = ser.readline()
            if raw:
                lines.append(raw.decode("utf-8", errors="replace").strip())
            else:
                if any("[HAPTIC]" in l for l in lines):
                    break

        ser.close()

        for line in lines:
            m = re.search(r"range_deg:\s+([\d.]+)", line)
            if m:
                self.range_deg = float(m.group(1))
            m = re.search(r"center_deg:\s+([\d.]+)", line)
            if m:
                self.center_deg = float(m.group(1))
            m = re.search(r"detents:\s+(\d+)", line)
            if m:
                self.detent_count = int(m.group(1))
            m = re.search(r"range:\s+([-\d.]+)°\s*\.\.\s*([-\d.]+)°", line)
            if m:
                self.range_min = float(m.group(1))
                self.range_max = float(m.group(2))
            # Also look for profile name in boot messages
            if "Profile" in line and ":" in line:
                self.profile_name = line.split(":", 1)[-1].strip()

        # Derive min/max if we got range + center but not the explicit range line
        if self.range_deg and self.center_deg and self.range_min is None:
            self.range_min = self.center_deg - self.range_deg / 2
            self.range_max = self.center_deg + self.range_deg / 2

        if self.range_min is not None:
            return True

        print("✗ Could not read config from firmware (send 'W' manually to check)")
        return False

    # ── Reader threads ───────────────────────────────────────────

    def _serial_reader(self):
        self._ser = serial.Serial(self.port, 115200, timeout=0.1)
        pattern = re.compile(
            r"HAPTIC_DIAG motor=([-\d.]+) snap=([-\d.]+) "
            r"det=([-\d]+) vel=([-\d.]+)")
        while not self._stop.is_set():
            try:
                raw = self._ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                m = pattern.search(line)
                if m:
                    self.motor_deg = float(m.group(1))
                    self.snap_deg  = float(m.group(2))
                    self.detent    = int(m.group(3))
                    self.velocity  = float(m.group(4))
                    self._serial_alive = True
            except Exception:
                continue
        self._ser.close()

    def _evdev_reader(self):
        try:
            fd = os.open(self.evdev_path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as e:
            print(f"Cannot open {self.evdev_path}: {e}")
            return

        # Read initial absinfo (value + check fuzz/flat)
        try:
            value, mn, mx, fuzz, flat = read_absinfo(fd, ABS_X)
            self.hid_value = value
            if fuzz > 0 or flat > 0:
                os.close(fd)
                print(f"  [evdev] fuzz={fuzz} flat={flat} — fixing...")
                fix_evdev_deadzone(self.evdev_path)
                fd = os.open(self.evdev_path, os.O_RDONLY | os.O_NONBLOCK)
                value, _, _, fuzz, flat = read_absinfo(fd, ABS_X)
                self.hid_value = value
                if fuzz > 0 or flat > 0:
                    print(f"  [evdev] WARNING: fuzz={fuzz}/flat={flat} "
                          f"still nonzero — install 'joystick' package")
        except Exception as e:
            print(f"  [evdev] absinfo read failed: {e}")

        try:
            while not self._stop.is_set():
                r, _, _ = select.select([fd], [], [], 0.2)
                if not r:
                    continue
                data = os.read(fd, EVDEV_SIZE * 16)
                for off in range(0, len(data), EVDEV_SIZE):
                    chunk = data[off:off + EVDEV_SIZE]
                    if len(chunk) < EVDEV_SIZE:
                        break
                    _, _, typ, code, value = struct.unpack(EVDEV_FMT, chunk)
                    if typ == EV_ABS and code == ABS_X:
                        self.hid_value = value
        except OSError:
            pass
        finally:
            os.close(fd)

    # ── Sampling ─────────────────────────────────────────────────

    def _record(self):
        """Place current observation into the correct bin."""
        if self.range_min is None or self.range_max is None:
            return
        span = self.range_max - self.range_min
        if span <= 0:
            return

        s = Sample(
            motor_deg=self.motor_deg,
            snap_deg=self.snap_deg,
            detent=self.detent,
            hid_value=self.hid_value,
            timestamp=time.time(),
        )

        frac = (self.snap_deg - self.range_min) / span
        idx  = max(0, min(int(frac * self.num_bins), self.num_bins - 1))

        # Only record if bin changed or >50ms since last sample in same bin
        if idx != self.last_bin_idx or self.bins[idx].count == 0:
            self.bins[idx].add(s)
            self.sample_count += 1
            self.last_bin_idx = idx

        # ── Endstop bounceback detection ─────────────────────────
        near_lo = (self.snap_deg - self.range_min) < span * 0.01
        near_hi = (self.range_max - self.snap_deg) < span * 0.01
        in_middle = not near_lo and not near_hi

        if near_lo and not self._at_low:
            self._at_low = True
            self._endstop_hid  = self.hid_value
            self._endstop_snap = self.snap_deg

        if near_hi and not self._at_high:
            self._at_high = True
            self._endstop_hid  = self.hid_value
            self._endstop_snap = self.snap_deg

        if self._at_low and in_middle:
            self.low_endstop_events.append(EndstopEvent(
                hit_hid=self._endstop_hid, bounce_hid=self.hid_value,
                hit_snap=self._endstop_snap, bounce_snap=self.snap_deg,
                timestamp=time.time()))
            self._at_low = False

        if self._at_high and in_middle:
            self.high_endstop_events.append(EndstopEvent(
                hit_hid=self._endstop_hid, bounce_hid=self.hid_value,
                hit_snap=self._endstop_snap, bounce_snap=self.snap_deg,
                timestamp=time.time()))
            self._at_high = False

    # ── Expected value (linear model) ────────────────────────────

    def _expected_hid(self, snap_deg):
        span = self.range_max - self.range_min
        if span <= 0:
            return 0
        frac = (snap_deg - self.range_min) / span
        return max(0, min(65535, int(frac * 65535)))

    def _bin_center_snap(self, idx):
        span = self.range_max - self.range_min
        return self.range_min + (idx + 0.5) / self.num_bins * span

    def _bin_error_pct(self, idx):
        """Linearity error for bin idx as % of full scale, or None."""
        b = self.bins[idx]
        if b.count == 0:
            return None
        expected = self._expected_hid(self._bin_center_snap(idx))
        return abs(b.mean_hid - expected) / 65535 * 100

    # ── Display ──────────────────────────────────────────────────

    def _render(self):
        span = self.range_max - self.range_min
        cur_idx = 0
        if span > 0:
            frac = (self.snap_deg - self.range_min) / span
            cur_idx = max(0, min(int(frac * self.num_bins), self.num_bins - 1))

        covered = sum(1 for b in self.bins if b.count > 0)
        coverage_pct = covered / self.num_bins * 100

        pct = self.hid_value / 65535 * 100
        expected = self._expected_hid(self.snap_deg)
        err = abs(self.hid_value - expected)
        err_pct = err / 65535 * 100

        out = []
        name = self.profile_name or "?"
        det_info = f"{self.detent_count} detents" if self.detent_count else "smooth"
        out.append(f"{BOLD}FOC Linearity Scanner{RESET}  —  "
                   f"{name} ({self.range_deg:.0f}°, {det_info})")
        out.append("═" * 66)
        out.append("")

        # Current position
        out.append(
            f"  Motor: {self.motor_deg:8.1f}°   Snap: {self.snap_deg:8.1f}°   "
            f"Det: {self.detent:4d}   Vel: {self.velocity:5.1f}°/s")
        out.append(
            f"  HID:   {self.hid_value:5d}/65535 ({pct:5.1f}%)   "
            f"Expected: {expected:5d}   Error: {err:4d} ({err_pct:.2f}%)")
        out.append("")

        # Coverage bargraph
        bar = ""
        for i in range(self.num_bins):
            if i == cur_idx:
                bar += f"{BOLD}▼{RESET}"
            elif self.bins[i].count > 0:
                e = self._bin_error_pct(i)
                if e is None or e < 0.5:
                    bar += f"{GREEN}█{RESET}"
                elif e < 2.0:
                    bar += f"{YELLOW}▓{RESET}"
                else:
                    bar += f"{RED}▓{RESET}"
            else:
                bar += f"{DIM}░{RESET}"

        out.append(f"  Range: {bar}")
        out.append(f"         {self.range_min:.0f}°"
                   f"{'':>{self.num_bins - 12}}  "
                   f"{self.range_max:.0f}°")
        out.append(f"  Coverage: {covered}/{self.num_bins} bins "
                   f"({coverage_pct:.0f}%)   "
                   f"Samples: {self.sample_count}")
        out.append(f"  {GREEN}█{RESET}<0.5%  "
                   f"{YELLOW}▓{RESET}0.5-2%  "
                   f"{RED}▓{RESET}>2%  "
                   f"{DIM}░{RESET}uncovered  "
                   f"{BOLD}▼{RESET}current")
        out.append("")

        # Worst bins
        errors = [(i, self._bin_error_pct(i))
                  for i in range(self.num_bins)
                  if self._bin_error_pct(i) is not None]
        if errors:
            worst = sorted(errors, key=lambda x: -x[1])[:3]
            if worst[0][1] > 0.5:
                out.append("  Worst bins:")
                for i, e in worst:
                    if e < 0.1:
                        break
                    snap_c = self._bin_center_snap(i)
                    out.append(f"    bin {i:2d} (~{snap_c:6.0f}°): "
                               f"error {e:.2f}%  "
                               f"(HID avg={self.bins[i].mean_hid:.0f} "
                               f"exp={self._expected_hid(snap_c)})")
                out.append("")

        # Endstop summary
        if self.low_endstop_events or self.high_endstop_events:
            out.append("  Endstop bounceback:")
            if self.low_endstop_events:
                ev = self.low_endstop_events[-1]
                delta_hid = abs(ev.bounce_hid - ev.hit_hid)
                delta_deg = abs(ev.bounce_snap - ev.hit_snap)
                out.append(f"    Low:  hit HID={ev.hit_hid:5d}  "
                           f"settled HID={ev.bounce_hid:5d}  "
                           f"bounce={delta_hid} ({delta_deg:.1f}°)")
            if self.high_endstop_events:
                ev = self.high_endstop_events[-1]
                delta_hid = abs(ev.bounce_hid - ev.hit_hid)
                delta_deg = abs(ev.bounce_snap - ev.hit_snap)
                out.append(f"    High: hit HID={ev.hit_hid:5d}  "
                           f"settled HID={ev.bounce_hid:5d}  "
                           f"bounce={delta_hid} ({delta_deg:.1f}°)")
            out.append("")

        out.append("  Keys: 1-9 jump to 0%–100%  |  Turn wheel for coverage  |  Ctrl+C for report")
        print(CLEAR + "\n".join(out), flush=True)

    # ── Report ───────────────────────────────────────────────────

    def _print_report(self):
        span = self.range_max - self.range_min
        covered = sum(1 for b in self.bins if b.count > 0)
        coverage_pct = covered / self.num_bins * 100

        errors = [self._bin_error_pct(i)
                  for i in range(self.num_bins)
                  if self._bin_error_pct(i) is not None]
        mean_err = sum(errors) / len(errors) if errors else 0
        max_err  = max(errors) if errors else 0

        print()
        print("=" * 66)
        name = self.profile_name or "?"
        print(f"  LINEARITY SCAN REPORT  —  {name}")
        print("=" * 66)
        print()
        print(f"  Range:     {self.range_min:.0f}° .. {self.range_max:.0f}° "
              f"({span:.0f}° total)")
        if self.detent_count:
            print(f"  Detents:   {self.detent_count}  "
                  f"(step={span/self.detent_count:.1f}°)")
        print(f"  Bins:      {self.num_bins}  "
              f"({span/self.num_bins:.1f}° each)")
        print(f"  Coverage:  {covered}/{self.num_bins} ({coverage_pct:.0f}%)")
        print(f"  Samples:   {self.sample_count}")
        print()

        # Linearity grade
        if errors:
            grade = "EXCELLENT" if max_err < 0.5 else \
                    "GOOD"      if max_err < 1.0 else \
                    "FAIR"      if max_err < 2.0 else \
                    "POOR"      if max_err < 5.0 else "FAIL"
            color = GREEN if max_err < 1.0 else \
                    YELLOW if max_err < 2.0 else RED
            print(f"  Linearity: {color}{grade}{RESET}  "
                  f"(mean={mean_err:.3f}%  max={max_err:.3f}%)")
        else:
            print(f"  Linearity: {DIM}no data{RESET}")
        print()

        # Per-bin table
        print(f"  {'Bin':>4s}  {'Snap°':>8s}  {'ExpHID':>6s}  "
              f"{'AvgHID':>6s}  {'Err%':>6s}  {'N':>4s}  {'':2s}")
        print(f"  {'─'*4}  {'─'*8}  {'─'*6}  "
              f"{'─'*6}  {'─'*6}  {'─'*4}  {'─'*2}")

        for i in range(self.num_bins):
            b = self.bins[i]
            snap_c  = self._bin_center_snap(i)
            exp_hid = self._expected_hid(snap_c)
            if b.count == 0:
                print(f"  {i:4d}  {snap_c:8.1f}  {exp_hid:6d}  "
                      f"{'─':>6s}  {'─':>6s}  {'─':>4s}  "
                      f"{DIM}░{RESET}")
                continue
            e = self._bin_error_pct(i)
            mark = f"{GREEN}✓{RESET}" if e < 0.5 else \
                   f"{YELLOW}~{RESET}" if e < 2.0 else \
                   f"{RED}✗{RESET}"
            print(f"  {i:4d}  {snap_c:8.1f}  {exp_hid:6d}  "
                  f"{b.mean_hid:6.0f}  {e:5.2f}%  {b.count:4d}  {mark}")

        # Endstop bounceback
        print()
        print("  Endstop Bounceback:")
        if self.low_endstop_events:
            bounces = [abs(e.bounce_hid - e.hit_hid)
                       for e in self.low_endstop_events]
            avg_b = sum(bounces) / len(bounces)
            max_b = max(bounces)
            print(f"    Low  ({len(self.low_endstop_events)} events): "
                  f"avg={avg_b:.0f} HID  max={max_b} HID  "
                  f"({max_b/65535*100:.2f}%)")
        else:
            print(f"    Low:  {DIM}not reached{RESET}")

        if self.high_endstop_events:
            bounces = [abs(e.bounce_hid - e.hit_hid)
                       for e in self.high_endstop_events]
            avg_b = sum(bounces) / len(bounces)
            max_b = max(bounces)
            print(f"    High ({len(self.high_endstop_events)} events): "
                  f"avg={avg_b:.0f} HID  max={max_b} HID  "
                  f"({max_b/65535*100:.2f}%)")
        else:
            print(f"    High: {DIM}not reached{RESET}")

        print()
        print("=" * 66)

    # ── Jump-to-position ─────────────────────────────────────────

    def _jump_to(self, key_num):
        """Jump motor to position for key 1-9 (1=0%, 5=50%, 9=100%)."""
        if self.range_min is None or self.range_max is None:
            return
        frac = (key_num - 1) / 8.0
        target_deg = self.range_min + frac * (self.range_max - self.range_min)
        try:
            self._ser.write(f"T{target_deg:.1f}\n".encode())
        except Exception:
            pass

    # ── Main loop ────────────────────────────────────────────────

    def run(self):
        self._check_prerequisites()

        print(f"Serial: {self.port}")
        print(f"Evdev:  {self.evdev_path}")
        print("Querying firmware config...")

        if not self._query_config():
            sys.exit(1)

        print(f"  range_deg={self.range_deg}  center_deg={self.center_deg}")
        print(f"  angle range: {self.range_min}° .. {self.range_max}°")
        if self.detent_count:
            print(f"  detents={self.detent_count}  "
                  f"step={self.range_deg/self.detent_count:.1f}°")
        print()

        # Start readers
        serial_t = threading.Thread(target=self._serial_reader, daemon=True)
        evdev_t  = threading.Thread(target=self._evdev_reader,  daemon=True)
        serial_t.start()
        evdev_t.start()

        # Wait for first telemetry
        t0 = time.time()
        while not self._serial_alive and time.time() - t0 < 5:
            time.sleep(0.1)
        if not self._serial_alive:
            print("✗ No HAPTIC_DIAG telemetry — is haptic enabled?  (send WE1)")
            self._stop.set()
            sys.exit(1)

        # Set terminal to raw mode for non-blocking keypress reading
        old_termios = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            while not self._stop.is_set():
                # Check for keypress (non-blocking via select)
                r, _, _ = select.select([sys.stdin], [], [], 0.15)
                if r:
                    ch = sys.stdin.read(1)
                    if ch == '\x03':        # Ctrl+C
                        break
                    if ch in '123456789':
                        self._jump_to(int(ch))
                self._record()
                self._render()
        except KeyboardInterrupt:
            pass
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_termios)
            self._stop.set()
            self._print_report()


# ── CLI ──────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Linearity scan — verify motor→detent→HID mapping")
    ap.add_argument("--bins", type=int, default=40,
                    help="Number of range bins (default: 40)")
    ap.add_argument("--port", default=None,
                    help="Serial port (default: first /dev/ttyACM*)")
    ap.add_argument("--evdev", default=None,
                    help="Evdev path (default: auto-detect FOC device)")
    args = ap.parse_args()

    scan = LinearityScan(
        num_bins=args.bins,
        port=args.port,
        evdev_path=args.evdev,
    )
    scan.run()


if __name__ == "__main__":
    main()
