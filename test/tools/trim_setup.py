#!/usr/bin/env python3
"""
Interactive Haptic Setup Tool — Live trim wheel feel tuning

Terminal UI for adjusting haptic layer parameters in real time.
Shows live motor position, detent index, and HID value.

Controls:
  r/R  — Decrease/Increase range (°)
  c/C  — Decrease/Increase center (°)
  n/N  — Fewer/More detents
  s/S  — Decrease/Increase detent strength
  m/M  — Decrease/Increase endstop margin
  e    — Toggle enable/disable
  0-9  — Jump to detent position (0=min, 9=max)
  ?    — Query full config from device
  d    — Reset to defaults
  q    — Quit

Usage:
  python3 test/tools/trim_setup.py
  python3 test/tools/trim_setup.py --port /dev/ttyACM1
"""

import serial
import time
import sys
import os
import re
import select
import termios
import tty
from dataclasses import dataclass
from typing import Optional, Dict


# ==========================================================================
# CONFIG SNAPSHOT
# ==========================================================================

@dataclass
class HapticState:
    enabled: bool = True
    range_deg: float = 180.0
    center_deg: float = 90.0
    detent_count: int = 18
    strength: float = 1.0
    endstop_margin: float = 2.0
    step_deg: float = 10.0
    detent_index: int = 0
    target_deg: float = 0.0
    raw_deg: float = 0.0
    hid_value: int = 0

    # telemetry
    actual_deg: float = 0.0
    error_deg: float = 0.0
    settled: bool = False


# ==========================================================================
# DEVICE LINK
# ==========================================================================

class DeviceLink:
    def __init__(self, port: str):
        self.ser = serial.Serial(port, 115200, timeout=0.05)
        time.sleep(2)
        self.ser.reset_input_buffer()

    def send(self, cmd: str):
        self.ser.write(f"{cmd}\n".encode())

    def read_all_lines(self) -> list:
        lines = []
        while self.ser.in_waiting:
            try:
                raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if raw:
                    lines.append(raw)
            except Exception:
                break
        return lines

    def close(self):
        self.ser.close()


# ==========================================================================
# PARSING
# ==========================================================================

def parse_telemetry(line: str, state: HapticState):
    """Parse @T ms,target,actual,error,variance,settled."""
    if not line.startswith("@T "):
        return False
    try:
        parts = line[3:].split(",")
        if len(parts) >= 6:
            state.target_deg = float(parts[1]) * 180.0 / 3.14159265
            state.actual_deg = float(parts[2]) * 180.0 / 3.14159265
            state.error_deg = float(parts[3]) * 180.0 / 3.14159265
            state.settled = parts[5].strip() == "1"
            return True
    except (ValueError, IndexError):
        pass
    return False


def parse_haptic_line(line: str, state: HapticState):
    """Parse individual [HAPTIC] response lines."""
    if "enabled:" in line:
        state.enabled = "YES" in line
    elif "range_deg:" in line:
        m = re.search(r"range_deg:\s+([\d.]+)", line)
        if m: state.range_deg = float(m.group(1))
    elif "center_deg:" in line:
        m = re.search(r"center_deg:\s+([\d.]+)", line)
        if m: state.center_deg = float(m.group(1))
    elif "detents:" in line and "detent_step" not in line:
        m = re.search(r"detents:\s+(\d+)", line)
        if m: state.detent_count = int(m.group(1))
    elif "strength:" in line:
        m = re.search(r"strength:\s+([\d.]+)", line)
        if m: state.strength = float(m.group(1))
    elif "endstop_margin:" in line:
        m = re.search(r"endstop_margin:\s+([\d.]+)", line)
        if m: state.endstop_margin = float(m.group(1))
    elif "detent_step:" in line:
        m = re.search(r"detent_step:\s+([\d.]+)", line)
        if m: state.step_deg = float(m.group(1))
    elif "hid_value:" in line:
        m = re.search(r"hid_value:\s+(\d+)", line)
        if m: state.hid_value = int(m.group(1))
    elif "current:" in line:
        m = re.search(r"detent=(-?\d+)", line)
        if m: state.detent_index = int(m.group(1))
        m = re.search(r"target=([\d.]+)", line)
        if m: state.target_deg = float(m.group(1))
        m = re.search(r"raw=([\d.]+)", line)
        if m: state.raw_deg = float(m.group(1))


# ==========================================================================
# DISPLAY
# ==========================================================================

def render(state: HapticState):
    """Render the live dashboard (overwrites terminal)."""
    # Move cursor to top-left (ANSI escape)
    sys.stdout.write("\033[H\033[J")

    lo = state.center_deg - state.range_deg / 2.0
    hi = state.center_deg + state.range_deg / 2.0

    bar_width = 60
    if state.range_deg > 0:
        frac = (state.actual_deg - lo) / state.range_deg
    else:
        frac = 0.5
    frac = max(0.0, min(1.0, frac))
    bar_pos = int(frac * (bar_width - 1))

    bar = list("─" * bar_width)
    # Mark detent positions
    if state.detent_count > 0:
        for i in range(state.detent_count + 1):
            idx = int((i / state.detent_count) * (bar_width - 1))
            if 0 <= idx < bar_width:
                bar[idx] = "│"
    # Mark current position
    if 0 <= bar_pos < bar_width:
        bar[bar_pos] = "●"

    status = "ON " if state.enabled else "OFF"
    settled = "✓" if state.settled else "~"

    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║            HAPTIC LAYER — INTERACTIVE SETUP                    ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Status:  [{status}]   Settled: [{settled}]"
          f"   Error: {state.error_deg:+.2f}°".ljust(67) + "║")
    print("║" + " " * 66 + "║")
    print(f"║  Range:  {state.range_deg:6.1f}°  ({lo:.0f}° — {hi:.0f}°)"
          .ljust(67) + "║")
    print(f"║  Center: {state.center_deg:6.1f}°".ljust(67) + "║")
    print(f"║  Detents: {state.detent_count:4d}    Step: {state.step_deg:.1f}°"
          .ljust(67) + "║")
    print(f"║  Strength: {state.strength:.2f}  Margin: {state.endstop_margin:.1f}°"
          .ljust(67) + "║")
    print("║" + " " * 66 + "║")
    print(f"║  Position: {state.actual_deg:6.1f}°   Detent #{state.detent_index:2d}"
          f"   HID: {state.hid_value:4d}".ljust(67) + "║")
    print("║" + " " * 66 + "║")
    print(f"║  {lo:5.0f}° {''.join(bar)} {hi:5.0f}°  ".ljust(67) + "║")
    print("║" + " " * 66 + "║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  r/R range   n/N detents   s/S strength   e toggle   ? query  ║")
    print("║  c/C center  m/M margin    0-9 jump       d default  q quit   ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    sys.stdout.flush()


# ==========================================================================
# KEY HANDLING
# ==========================================================================

def handle_key(key: str, dev: DeviceLink, state: HapticState):
    """Process one keypress, send Commander command if needed."""

    if key == 'r':
        state.range_deg = max(10, state.range_deg - 10)
        dev.send(f"WR{state.range_deg:.0f}")
    elif key == 'R':
        state.range_deg = min(360, state.range_deg + 10)
        dev.send(f"WR{state.range_deg:.0f}")
    elif key == 'c':
        state.center_deg -= 10
        dev.send(f"WC{state.center_deg:.0f}")
    elif key == 'C':
        state.center_deg += 10
        dev.send(f"WC{state.center_deg:.0f}")
    elif key == 'n':
        state.detent_count = max(0, state.detent_count - 1)
        dev.send(f"WN{state.detent_count}")
    elif key == 'N':
        state.detent_count += 1
        dev.send(f"WN{state.detent_count}")
    elif key == 's':
        state.strength = max(0.0, state.strength - 0.1)
        dev.send(f"WS{state.strength:.2f}")
    elif key == 'S':
        state.strength = min(1.0, state.strength + 0.1)
        dev.send(f"WS{state.strength:.2f}")
    elif key == 'm':
        state.endstop_margin = max(0, state.endstop_margin - 1)
        dev.send(f"WM{state.endstop_margin:.0f}")
    elif key == 'M':
        state.endstop_margin += 1
        dev.send(f"WM{state.endstop_margin:.0f}")
    elif key == 'e':
        state.enabled = not state.enabled
        dev.send(f"WE{1 if state.enabled else 0}")
    elif key == '?':
        dev.send("W")
    elif key == 'd':
        dev.send("WR180")
        dev.send("WC90")
        dev.send("WN18")
        dev.send("WS1.0")
        dev.send("WM2")
        dev.send("WE1")
        state.range_deg = 180
        state.center_deg = 90
        state.detent_count = 18
        state.strength = 1.0
        state.endstop_margin = 2.0
        state.enabled = True
    elif key in "0123456789":
        # Jump to detent position: 0=min, 9=max
        lo = state.center_deg - state.range_deg / 2.0
        hi = state.center_deg + state.range_deg / 2.0
        frac = int(key) / 9.0
        target = lo + frac * (hi - lo)
        dev.send(f"T{target:.1f}")
    elif key == 'q':
        return False

    return True


# ==========================================================================
# MAIN LOOP
# ==========================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Interactive haptic setup tool")
    parser.add_argument("--port", default="/dev/ttyACM0")
    args = parser.parse_args()

    print(f"Connecting to {args.port}...")
    dev = DeviceLink(args.port)

    state = HapticState()

    # Query initial config
    dev.send("W")
    time.sleep(0.5)

    # Set terminal to raw mode for single-keypress input
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())

        last_query = time.time()
        last_render = 0

        while True:
            # Read serial data
            lines = dev.read_all_lines()
            for line in lines:
                if not parse_telemetry(line, state):
                    parse_haptic_line(line, state)

            # Re-render at ~10 Hz
            now = time.time()
            if now - last_render > 0.1:
                render(state)
                last_render = now

            # Periodically query haptic config (every 2s)
            if now - last_query > 2.0:
                dev.send("W")
                last_query = now

            # Check for keypress (non-blocking)
            if select.select([sys.stdin], [], [], 0.02)[0]:
                key = sys.stdin.read(1)
                if not handle_key(key, dev, state):
                    break

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        dev.close()
        print("\nBye.")


if __name__ == "__main__":
    main()
