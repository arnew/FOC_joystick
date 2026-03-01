#!/usr/bin/env python3
"""
Profile Monitor — set a profile and watch debug telemetry + joystick live.

Usage:
    python3 test/tools/profile_monitor.py                  # monitor current profile
    python3 test/tools/profile_monitor.py 5                 # switch to profile 5
    python3 test/tools/profile_monitor.py --serial-only     # skip joystick
    python3 test/tools/profile_monitor.py --joy-only        # skip serial telemetry
    python3 test/tools/profile_monitor.py --fix-deadzone    # clear Linux flat/fuzz
    python3 test/tools/profile_monitor.py --set-flat 100    # set flat to 100

Linux applies flat=range/16 and fuzz=range/256 as dead zone to joystick
axes.  Use --fix-deadzone to zero them out (calls evdev-joystick, no root).
Windows DirectInput has no automatic dead zone — this is Linux-specific.

Serial shows @T telemetry (target/actual/error/settled) plus all [PROFILE]
and [CMD] messages.  Joystick shows axis values from /dev/input/js0 (Linux
joystick API — no pip dependencies).

Ctrl+C to exit.
"""

import argparse
import glob
import os
import select
import serial
import struct
import subprocess
import sys
import threading
import time

# ── Profile table (mirrors config.h) ────────────────────────────────

PROFILES = {
    0: "Cessna Trim",      1: "Cessna Throttle",
    2: "Cessna Flaps",     3: "172RG Gear",
    4: "A320 Trim",        5: "A320 Throttle",
    6: "A320 Flaps",       7: "A320 Spoilers",
    8: "Glider Trim",      9: "Glider Spoiler",
}

# ── Helpers ──────────────────────────────────────────────────────────

def find_serial_port():
    """First /dev/ttyACM* is the CDC debug port."""
    ports = sorted(glob.glob("/dev/ttyACM*"))
    return ports[0] if ports else None

def find_joystick():
    """Return path to /dev/input/js* for a FOC device, or first js*."""
    for js in sorted(glob.glob("/dev/input/js*")):
        try:
            with open(js, "rb") as f:
                # JSIOCGNAME(128)
                import fcntl, array
                buf = array.array("B", [0] * 128)
                fcntl.ioctl(f, 0x80806A13, buf)
                name = buf.tobytes().split(b"\x00")[0].decode()
                if "FOC" in name or "Joystick" in name:
                    return js, name
        except Exception:
            pass
    # Fallback: first js device
    devs = sorted(glob.glob("/dev/input/js*"))
    if devs:
        return devs[0], "(unknown)"
    return None, None


def find_evdev_for_foc():
    """Return /dev/input/eventN path for the FOC joystick (for evdev-joystick)."""
    try:
        with open("/proc/bus/input/devices") as f:
            text = f.read()
        for block in text.split("\n\n"):
            if "FOC" not in block:
                continue
            for line in block.splitlines():
                if line.startswith("H: Handlers="):
                    # Tokens: "H:", "Handlers=event18", "js0", ...
                    for tok in line.replace("=", " ").split():
                        if tok.startswith("event"):
                            return f"/dev/input/{tok}"
    except Exception:
        pass
    return None


def apply_deadzone(flat=0, fuzz=0):
    """Set flat/fuzz on FOC joystick via evdev-joystick (no root needed)."""
    evdev = find_evdev_for_foc()
    if not evdev:
        print("  [deadzone] FOC event device not found — skipping")
        return False
    ok = True
    for param, val in [("deadzone", flat), ("fuzz", fuzz)]:
        try:
            r = subprocess.run(
                ["evdev-joystick", "--evdev", evdev, f"--{param}", str(val)],
                capture_output=True, text=True, timeout=5)
            for line in r.stdout.strip().splitlines():
                print(f"  [deadzone] {line}")
            if r.returncode != 0:
                print(f"  [deadzone] evdev-joystick --{param} failed: {r.stderr.strip()}")
                ok = False
        except FileNotFoundError:
            print("  [deadzone] evdev-joystick not installed (apt install joystick)")
            return False
    return ok

# ── Serial monitor thread ────────────────────────────────────────────

class SerialMonitor(threading.Thread):
    """Read serial and print @T lines as a formatted table + other lines."""

    def __init__(self, port, baud=115200):
        super().__init__(daemon=True)
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self._stop = threading.Event()
        self.last_telemetry = {}          # latest parsed @T fields
        self.port = port

    def stop(self):
        self._stop.set()

    def send(self, cmd: str):
        self.ser.write((cmd.strip() + "\n").encode())
        self.ser.flush()

    def run(self):
        hdr_printed = False
        while not self._stop.is_set():
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                if line.startswith("@T"):
                    parts = line[3:].split(",")
                    if len(parts) >= 7:
                        ms, tgt, act, err = parts[0], parts[1], parts[2], parts[3]
                        rms, var_, settled = parts[4], parts[5], parts[6]
                        self.last_telemetry = {
                            "target": float(tgt), "actual": float(act),
                            "error": float(err), "rms": float(rms),
                            "variance": float(var_), "settled": settled.strip() == "1",
                        }
                        if not hdr_printed:
                            print(fmt_hdr())
                            hdr_printed = True
                        print(fmt_telemetry(ms, tgt, act, err, rms, settled))
                else:
                    # Print non-telemetry lines (profile switch acks, etc.)
                    print(f"  >> {line}")
            except serial.SerialException:
                break
            except Exception as e:
                print(f"  [serial err] {e}")

    def close(self):
        self.stop()
        time.sleep(0.15)
        self.ser.close()


def fmt_hdr():
    return (
        "\n  ┌────────┬─────────┬─────────┬────────┬───────┬────────┐\n"
        "  │  ms    │ target° │ actual° │ error° │  rms  │ settl? │\n"
        "  ├────────┼─────────┼─────────┼────────┼───────┼────────┤"
    )

def fmt_telemetry(ms, tgt, act, err, rms, settled):
    s = "  YES" if settled.strip() == "1" else "   no"
    return (
        f"  │{ms:>7s} │{tgt:>8s} │{act:>8s} │{err:>7s} │{rms:>6s} │{s}  │"
    )


# ── Joystick monitor thread ──────────────────────────────────────────

JS_EVENT_FMT = "IhBB"       # time(u32) value(s16) type(u8) number(u8)
JS_EVENT_SIZE = struct.calcsize(JS_EVENT_FMT)
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80

class JoystickMonitor(threading.Thread):
    """Read Linux /dev/input/js* events and print axis changes."""

    def __init__(self, path, name):
        super().__init__(daemon=True)
        self.path = path
        self.name = name
        self._stop = threading.Event()
        self.axes = {}            # axis_num → raw value (-32767..32767)

    def stop(self):
        self._stop.set()

    def run(self):
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as e:
            print(f"  [joystick] cannot open {self.path}: {e}")
            return

        print(f"  [joystick] {self.name}  ({self.path})")
        try:
            while not self._stop.is_set():
                r, _, _ = select.select([fd], [], [], 0.2)
                if not r:
                    continue
                data = os.read(fd, JS_EVENT_SIZE * 16)
                for off in range(0, len(data), JS_EVENT_SIZE):
                    chunk = data[off:off + JS_EVENT_SIZE]
                    if len(chunk) < JS_EVENT_SIZE:
                        break
                    ts, value, typ, number = struct.unpack(JS_EVENT_FMT, chunk)
                    if typ & JS_EVENT_AXIS:
                        self.axes[number] = value
                        # Convert -32767..32767 → 0..65535 (matches HID descriptor)
                        val = int((value + 32767) / 65534 * 65535)
                        pct = val / 65535 * 100
                        bar = "█" * int(pct / 2.5) + "░" * (40 - int(pct / 2.5))
                        init = " (init)" if typ & JS_EVENT_INIT else ""
                        print(
                            f"  [axis {number}] {val:5d}/65535 "
                            f"({pct:5.1f}%) {bar}{init}"
                        )
        except OSError:
            pass
        finally:
            os.close(fd)


# ── Main ──────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Set profile & monitor telemetry + joystick")
    ap.add_argument("profile", nargs="?", type=int, default=None,
                    help="Profile number 0-9 (omit to keep current)")
    ap.add_argument("--serial-only", action="store_true",
                    help="Skip joystick, serial telemetry only")
    ap.add_argument("--joy-only", action="store_true",
                    help="Skip serial, joystick only")
    ap.add_argument("--port", default=None,
                    help="Serial port (default: first /dev/ttyACM*)")
    ap.add_argument("--list", action="store_true",
                    help="List profiles and exit")
    ap.add_argument("--fix-deadzone", action="store_true",
                    help="Set flat=0 fuzz=0 on FOC joystick (Linux dead zone fix)")
    ap.add_argument("--set-flat", type=int, default=None, metavar="N",
                    help="Set joystick flat (dead zone) to N (default: 0 with --fix-deadzone)")
    ap.add_argument("--set-fuzz", type=int, default=None, metavar="N",
                    help="Set joystick fuzz (noise filter) to N (default: 0 with --fix-deadzone)")
    args = ap.parse_args()

    if args.list:
        print("Profiles (send A<n> via serial):")
        for k, v in sorted(PROFILES.items()):
            print(f"  {k}: {v}")
        return

    # ── Serial ────────────────────────────────────────────────────
    ser_mon = None
    if not args.joy_only:
        port = args.port or find_serial_port()
        if not port:
            print("✗ No serial port found. Use --joy-only or --port.")
            sys.exit(1)
        ser_mon = SerialMonitor(port)
        print(f"✓ Serial: {port}")

        # Switch profile if requested
        if args.profile is not None:
            pid = args.profile
            name = PROFILES.get(pid, "?")
            print(f"→ Switching to profile {pid} ({name}) …")
            ser_mon.start()
            time.sleep(0.3)
            ser_mon.send(f"A{pid}")
            # Profile switch triggers USB re-enum + reboot.
            # Give the device time to come back.
            print("  (device may reboot for USB identity change)")
            time.sleep(4)
            # Re-open serial after reboot
            ser_mon.close()
            # Port may change after reboot; re-detect
            port = args.port or find_serial_port()
            if not port:
                print("✗ Serial port not found after reboot.")
                sys.exit(1)
            ser_mon = SerialMonitor(port)
            print(f"✓ Serial reconnected: {port}")
        ser_mon.start()

    # ── Dead zone fix ──────────────────────────────────────────────
    if args.fix_deadzone or args.set_flat is not None or args.set_fuzz is not None:
        flat = args.set_flat if args.set_flat is not None else 0
        fuzz = args.set_fuzz if args.set_fuzz is not None else 0
        apply_deadzone(flat=flat, fuzz=fuzz)

    # ── Joystick ──────────────────────────────────────────────────
    joy_mon = None
    if not args.serial_only:
        # Small delay for USB re-enum if profile was just switched
        if args.profile is not None and ser_mon:
            time.sleep(1)
        js_path, js_name = find_joystick()
        if js_path:
            joy_mon = JoystickMonitor(js_path, js_name)
            joy_mon.start()
        else:
            print("  [joystick] no /dev/input/js* found — skipping")

    # ── Run until Ctrl+C ──────────────────────────────────────────
    if not ser_mon and not joy_mon:
        print("Nothing to monitor.")
        sys.exit(1)

    profile_label = ""
    if args.profile is not None:
        profile_label = f"profile {args.profile} ({PROFILES.get(args.profile, '?')})"
    else:
        profile_label = "current profile"

    print(f"\nMonitoring {profile_label}  —  Ctrl+C to exit\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n✓ Exit")
    finally:
        if ser_mon:
            ser_mon.close()
        if joy_mon:
            joy_mon.stop()


if __name__ == "__main__":
    main()
