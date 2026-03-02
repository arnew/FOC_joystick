#!/usr/bin/env python3
"""
Interactive Haptic Setup Tool — Live trim wheel feel tuning (curses TUI)

Adjust haptic layer parameters in real time via serial Commander 'W'
commands.  Shows live motor position, detent index, and HID value.

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
  p    — Export as C profile struct (for config.h)
  j    — Save JSON preset to file
  J    — Load JSON preset from file
  q    — Quit

Usage:
  python3 test/tools/trim_setup.py
  python3 test/tools/trim_setup.py --port /dev/ttyACM1
  python3 test/tools/trim_setup.py --preset my_trim.json
  python3 test/tools/trim_setup.py --name "My Trim Wheel"
"""

import curses
import serial
import time
import sys
import os
import re
import json
import argparse
from dataclasses import dataclass
from datetime import datetime


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
# EXPORT / PRESET
# ==========================================================================

def export_c_profile(state: HapticState, name: str = "Custom") -> str:
    """Generate a C ControlProfile struct line for config.h."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    pad = max(1, 18 - len(name))
    return "\n".join([
        f"// Generated by trim_setup.py — {ts}",
        f"// Paste into ALL_PROFILES[] in config.h, add enum entry",
        f"",
        f'    {{ "{name}",{" " * pad} 0, false, '
        f'{state.range_deg:.1f}f, {state.center_deg:.1f}f, '
        f'{state.endstop_margin:.1f}f,',
        f'      {state.detent_count}, {state.strength:.2f}f, '
        f'nullptr, 0, false, 0.0f,',
        f'      0xFF01, "FOC - {name}" }},',
    ])


def save_preset(state: HapticState, path: str) -> str:
    """Save haptic parameters as JSON preset."""
    data = {
        "tool": "trim_setup",
        "timestamp": datetime.now().isoformat(),
        "range_deg": state.range_deg,
        "center_deg": state.center_deg,
        "detent_count": state.detent_count,
        "strength": state.strength,
        "endstop_margin": state.endstop_margin,
        "enabled": state.enabled,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def load_preset(path: str, state: HapticState, dev: DeviceLink) -> bool:
    """Load JSON preset and push all values to device."""
    if not os.path.exists(path):
        return False
    with open(path) as f:
        data = json.load(f)
    state.range_deg = data.get("range_deg", state.range_deg)
    state.center_deg = data.get("center_deg", state.center_deg)
    state.detent_count = data.get("detent_count", state.detent_count)
    state.strength = data.get("strength", state.strength)
    state.endstop_margin = data.get("endstop_margin", state.endstop_margin)
    state.enabled = data.get("enabled", state.enabled)

    dev.send(f"WR{state.range_deg:.0f}")
    dev.send(f"WC{state.center_deg:.0f}")
    dev.send(f"WN{state.detent_count}")
    dev.send(f"WS{state.strength:.2f}")
    dev.send(f"WM{state.endstop_margin:.0f}")
    dev.send(f"WE{1 if state.enabled else 0}")
    return True


# ==========================================================================
# CURSES RENDERING
# ==========================================================================

# Color pair IDs
C_HEADER = 1
C_OK     = 2
C_WARN   = 3
C_ERROR  = 4
C_DIM    = 5
C_POS    = 6


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_HEADER, curses.COLOR_CYAN,   -1)
    curses.init_pair(C_OK,     curses.COLOR_GREEN,  -1)
    curses.init_pair(C_WARN,   curses.COLOR_YELLOW, -1)
    curses.init_pair(C_ERROR,  curses.COLOR_RED,    -1)
    curses.init_pair(C_DIM,    curses.COLOR_WHITE,  -1)
    curses.init_pair(C_POS,    curses.COLOR_YELLOW, -1)


def safe_addstr(win, y, x, text, attr=0):
    """addstr that silently clips at terminal edges."""
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    try:
        win.addnstr(y, x, text, max(0, w - x), attr)
    except curses.error:
        pass


def render(stdscr, state, status_msg=""):
    """Draw the full dashboard."""
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    lo = state.center_deg - state.range_deg / 2.0
    hi = state.center_deg + state.range_deg / 2.0

    # Adaptive bar width
    bar_width = min(max(40, w - 24), 80)
    frac = ((state.actual_deg - lo) / state.range_deg
            if state.range_deg > 0 else 0.5)
    frac = max(0.0, min(1.0, frac))
    bar_pos = int(frac * (bar_width - 1))

    # Build bar with detent marks
    bar_chars = list("─" * bar_width)
    if state.detent_count > 0:
        for i in range(state.detent_count + 1):
            idx = int((i / state.detent_count) * (bar_width - 1))
            if 0 <= idx < bar_width:
                bar_chars[idx] = "│"

    row = 0

    # ── Title ──
    safe_addstr(stdscr, row, 2, "HAPTIC LAYER — INTERACTIVE SETUP",
                curses.color_pair(C_HEADER) | curses.A_BOLD)
    row += 1
    safe_addstr(stdscr, row, 0, "─" * min(w, 68))
    row += 2

    # ── Status ──
    on_txt = "ON " if state.enabled else "OFF"
    on_clr = C_OK if state.enabled else C_ERROR
    ok_txt = " ✓ " if state.settled else " ~ "
    ok_clr = C_OK if state.settled else C_WARN

    safe_addstr(stdscr, row, 2, "Status: ")
    safe_addstr(stdscr, row, 10, f"[{on_txt}]",
                curses.color_pair(on_clr) | curses.A_BOLD)
    safe_addstr(stdscr, row, 17, "  Settled: ")
    safe_addstr(stdscr, row, 28, f"[{ok_txt}]",
                curses.color_pair(ok_clr))
    safe_addstr(stdscr, row, 35, f"  Error: {state.error_deg:+.2f}°")
    row += 2

    # ── Parameters ──
    safe_addstr(stdscr, row, 2,
                f"Range:    {state.range_deg:7.1f}°  "
                f"({lo:.0f}° — {hi:.0f}°)")
    row += 1
    safe_addstr(stdscr, row, 2,
                f"Center:   {state.center_deg:7.1f}°")
    row += 1
    safe_addstr(stdscr, row, 2,
                f"Detents:  {state.detent_count:5d}      "
                f"Step: {state.step_deg:.1f}°")
    row += 1
    safe_addstr(stdscr, row, 2,
                f"Strength:  {state.strength:5.2f}    "
                f"Margin: {state.endstop_margin:.1f}°")
    row += 2

    # ── Live position ──
    safe_addstr(stdscr, row, 2,
                f"Position: {state.actual_deg:7.1f}°   "
                f"Detent #{state.detent_index:2d}   "
                f"HID: {state.hid_value:5d}")
    row += 2

    # ── Position bar ──
    safe_addstr(stdscr, row, 2, f"{lo:5.0f}° ")
    bx = 9
    for i, ch in enumerate(bar_chars):
        if i == bar_pos:
            safe_addstr(stdscr, row, bx + i, "●",
                        curses.color_pair(C_POS) | curses.A_BOLD)
        else:
            safe_addstr(stdscr, row, bx + i, ch)
    safe_addstr(stdscr, row, bx + bar_width + 1, f"{hi:.0f}°")
    row += 2

    # ── Separator + controls ──
    safe_addstr(stdscr, row, 0, "─" * min(w, 68))
    row += 1
    ctrl = curses.color_pair(C_DIM)
    safe_addstr(stdscr, row, 2,
                "r/R range   n/N detents   s/S strength  "
                " e toggle   ? query", ctrl)
    row += 1
    safe_addstr(stdscr, row, 2,
                "c/C center  m/M margin    0-9 jump      "
                " d default  q quit", ctrl)
    row += 1
    safe_addstr(stdscr, row, 2,
                "p export C  j save JSON   J load JSON", ctrl)
    row += 2

    # ── Status message (set by save/load, fades after 3 s) ──
    if status_msg:
        safe_addstr(stdscr, row, 2, status_msg,
                    curses.color_pair(C_OK) | curses.A_BOLD)

    stdscr.noutrefresh()
    curses.doupdate()


# ==========================================================================
# KEY HANDLING
# ==========================================================================

def handle_key(ch, dev, state):
    """Process one key character.  Returns (keep_running, action_name)."""
    if ch == 'r':
        state.range_deg = max(10, state.range_deg - 10)
        dev.send(f"WR{state.range_deg:.0f}")
    elif ch == 'R':
        state.range_deg += 10
        dev.send(f"WR{state.range_deg:.0f}")
    elif ch == 'c':
        state.center_deg -= 10
        dev.send(f"WC{state.center_deg:.0f}")
    elif ch == 'C':
        state.center_deg += 10
        dev.send(f"WC{state.center_deg:.0f}")
    elif ch == 'n':
        state.detent_count = max(0, state.detent_count - 1)
        dev.send(f"WN{state.detent_count}")
    elif ch == 'N':
        state.detent_count += 1
        dev.send(f"WN{state.detent_count}")
    elif ch == 's':
        state.strength = max(0.0, round(state.strength - 0.1, 2))
        dev.send(f"WS{state.strength:.2f}")
    elif ch == 'S':
        state.strength = min(1.0, round(state.strength + 0.1, 2))
        dev.send(f"WS{state.strength:.2f}")
    elif ch == 'm':
        state.endstop_margin = max(0, state.endstop_margin - 1)
        dev.send(f"WM{state.endstop_margin:.0f}")
    elif ch == 'M':
        state.endstop_margin += 1
        dev.send(f"WM{state.endstop_margin:.0f}")
    elif ch == 'e':
        state.enabled = not state.enabled
        dev.send(f"WE{1 if state.enabled else 0}")
    elif ch == '?':
        dev.send("W")
    elif ch == 'd':
        for cmd in ["WR180", "WC90", "WN18", "WS1.0", "WM2", "WE1"]:
            dev.send(cmd)
        state.range_deg = 180
        state.center_deg = 90
        state.detent_count = 18
        state.strength = 1.0
        state.endstop_margin = 2.0
        state.enabled = True
    elif ch in "0123456789":
        lo = state.center_deg - state.range_deg / 2.0
        hi = state.center_deg + state.range_deg / 2.0
        target = lo + (int(ch) / 9.0) * (hi - lo)
        dev.send(f"T{target:.1f}")
    elif ch == 'p':
        return (True, 'export')
    elif ch == 'j':
        return (True, 'save_json')
    elif ch == 'J':
        return (True, 'load_json')
    elif ch == 'q':
        return (False, 'quit')

    return (True, None)


# ==========================================================================
# MAIN LOOP
# ==========================================================================

def tui_loop(stdscr, dev, state, preset_path):
    """Curses main loop.  Returns (action, state)."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(50)       # 50 ms getch → ~20 Hz render
    init_colors()

    # Request initial config from device
    dev.send("W")
    time.sleep(0.3)

    last_query = time.time()
    status_msg = ""
    status_ttl = 0

    while True:
        # ── Read serial ──
        for line in dev.read_all_lines():
            if not parse_telemetry(line, state):
                parse_haptic_line(line, state)

        # Clear expired status message
        if status_msg and time.time() > status_ttl:
            status_msg = ""

        # ── Render ──
        render(stdscr, state, status_msg)

        # ── Periodic config refresh ──
        now = time.time()
        if now - last_query > 2.0:
            dev.send("W")
            last_query = now

        # ── Key input ──
        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            stdscr.clear()
            continue
        if key == -1 or not (0 < key < 256):
            continue

        ch = chr(key)
        keep, action = handle_key(ch, dev, state)

        if action == 'export':
            return ('export', state)
        elif action == 'save_json':
            save_preset(state, preset_path)
            status_msg = f"✓ Saved → {preset_path}"
            status_ttl = time.time() + 3.0
        elif action == 'load_json':
            if load_preset(preset_path, state, dev):
                status_msg = f"✓ Loaded ← {preset_path}"
            else:
                status_msg = f"✗ Not found: {preset_path}"
            status_ttl = time.time() + 3.0
        elif not keep:
            return ('quit', state)


# ==========================================================================
# ENTRY POINT
# ==========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Interactive haptic setup tool (curses TUI)")
    parser.add_argument("--port", default="/dev/ttyACM0",
                        help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--preset", default="haptic_preset.json",
                        help="JSON preset file for j/J save/load")
    parser.add_argument("--name", default="Custom",
                        help="Profile name used in C export (p key)")
    args = parser.parse_args()

    print(f"Connecting to {args.port}...")
    dev = DeviceLink(args.port)
    state = HapticState()

    try:
        action, final = curses.wrapper(tui_loop, dev, state, args.preset)
    finally:
        dev.close()

    if action == 'export':
        print()
        print(export_c_profile(final, args.name))
        print()

    print("Bye.")  # 🛩️


if __name__ == "__main__":
    main()
