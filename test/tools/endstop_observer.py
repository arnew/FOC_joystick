#!/usr/bin/env python3
"""
Guided endstop test — structured stages with target angles.

Each stage tells the human where to turn the motor, waits for arrival
and settling, records the result, then moves on.

Usage: python3 test/tools/endstop_observer.py [--log FILE] [--port DEV]
"""

import serial
import time
import argparse
import re
import sys

PORT = '/dev/ttyACM0'
BAUD = 115200
RAD2DEG = 180.0 / 3.14159265

# ---------- Test plan ----------
# Each stage: (name, instruction, target_snap, settle_s, timeout_s)
#   target_snap: expected snap angle after stage (None = just observe)
#   settle_s:    how long motor must be within ±5° of target_snap
#   timeout_s:   max wait before declaring TIMEOUT
STAGES = [
    ("idle",          "Don't touch — observing idle",             None,  3,  8),
    ("mid-range",     "Turn to ~90° (middle)",                     90,   3, 20),
    ("toward-180",    "Turn to ~180° (far endstop)",              180,   3, 20),
    ("push-past-180", "Push HARD past 180° — let go immediately", 180,   5, 30),
    ("recovery",      "Wait — motor should return to 180°",       180,   5, 30),
    ("back-to-90",    "Turn back to ~90° (middle)",                90,   3, 20),
    ("toward-0",      "Turn to ~0° (near endstop)",                 0,   3, 20),
    ("push-past-0",   "Push HARD past 0° — let go immediately",    0,   5, 30),
    ("recovery-0",    "Wait — motor should return to 0°",           0,   5, 30),
    ("back-to-90b",   "Turn back to ~90° again",                   90,   3, 20),
]


def parse_haptic_diag(line):
    """Parse HAPTIC_DIAG key=value pairs."""
    fields = {}
    for m in re.finditer(r'(\w+)=([-\d.]+)', line):
        fields[m.group(1)] = float(m.group(2))
    return fields if fields else None


def parse_telemetry(payload):
    """Parse @T ms,target,actual,error,variance,settled"""
    parts = payload.split(',')
    if len(parts) != 6:
        return None
    try:
        return {
            'ms': int(parts[0]),
            'target': float(parts[1]),
            'actual': float(parts[2]),
            'error': float(parts[3]),
            'variance': float(parts[4]),
            'settled': int(parts[5]),
        }
    except ValueError:
        return None


def drain_serial(ser, logfile, last_diag, verbose=True):
    """Read all buffered lines, return latest HAPTIC_DIAG and @T."""
    latest_diag = last_diag
    latest_t = None
    while ser.in_waiting:
        try:
            line = ser.readline().decode('utf-8', errors='replace').strip()
        except Exception:
            continue
        if not line:
            continue
        if logfile:
            logfile.write(f"{time.time():.3f} {line}\n")
            logfile.flush()
        if line.startswith('HAPTIC_DIAG '):
            d = parse_haptic_diag(line)
            if d:
                latest_diag = d
                if verbose:
                    det = int(d.get('det', -1))
                    det_mark = ""
                    if last_diag and int(last_diag.get('det', -1)) != det:
                        det_mark = f"  <<< det {int(last_diag.get('det',-1))}->{det}"
                    print(f"    motor={d.get('motor',0):6.1f}  "
                          f"clamped={d.get('clamped',0):6.1f}  "
                          f"snap={d.get('snap',0):6.1f}  "
                          f"det={det:2d}  "
                          f"vel={d.get('vel',0):7.1f}"
                          f"{det_mark}")
                    last_diag = latest_diag
        elif line.startswith('@T '):
            latest_t = parse_telemetry(line[3:])
    return latest_diag, latest_t


def wait_for_target(ser, logfile, target_snap, settle_s, timeout_s,
                    last_diag, verbose=True):
    """
    Wait until snap target is within ±5° of target_snap for settle_s seconds.
    Returns (success, final_diag, elapsed).
    If target_snap is None, just wait timeout_s seconds observing.
    """
    start = time.time()
    settled_since = None
    tolerance = 5.0  # degrees

    while True:
        elapsed = time.time() - start
        last_diag, latest_t = drain_serial(ser, logfile, last_diag, verbose)

        if target_snap is None:
            # Just observe for timeout_s
            if elapsed >= timeout_s:
                return True, last_diag, elapsed
        else:
            snap_now = last_diag.get('snap', -999) if last_diag else -999
            if abs(snap_now - target_snap) <= tolerance:
                if settled_since is None:
                    settled_since = time.time()
                elif (time.time() - settled_since) >= settle_s:
                    return True, last_diag, elapsed
            else:
                settled_since = None

            if elapsed >= timeout_s:
                return False, last_diag, elapsed

        time.sleep(0.05)


def main():
    parser = argparse.ArgumentParser(description="Guided endstop test")
    parser.add_argument('--log', type=str, default=None)
    parser.add_argument('--port', type=str, default=PORT)
    args = parser.parse_args()

    ser = serial.Serial(args.port, BAUD, timeout=0.1)
    time.sleep(2)
    ser.reset_input_buffer()

    logfile = open(args.log, 'w') if args.log else None

    print("=" * 70)
    print("  GUIDED ENDSTOP TEST — Approach 2")
    print("=" * 70)
    print()
    print(f"  {len(STAGES)} stages.  Follow the instructions.")
    print(f"  Range: 0°..180°, 18 detents (10° steps)")
    print()

    # Query initial config
    ser.write(b'W\n')
    time.sleep(0.5)

    results = []
    last_diag = {}

    for i, (name, instruction, target, settle_s, timeout_s) in enumerate(STAGES):
        print("-" * 70)
        target_str = f"{target}°" if target is not None else "observe"
        print(f"  STAGE {i+1}/{len(STAGES)}: {name}")
        print(f"  >>> {instruction}")
        if target is not None:
            print(f"  Target snap: {target}°  (settle {settle_s}s within ±5°)")
        print()

        if logfile:
            logfile.write(f"\n### STAGE {i+1}: {name} — target={target_str}\n")

        input("  Press ENTER when ready...")
        print()

        ok, last_diag, elapsed = wait_for_target(
            ser, logfile, target, settle_s, timeout_s, last_diag)

        snap_now = last_diag.get('snap', '?') if last_diag else '?'
        det_now = int(last_diag.get('det', -1)) if last_diag else -1
        status = "PASS" if ok else "FAIL"

        result = {
            'stage': name,
            'target': target,
            'snap': snap_now,
            'det': det_now,
            'elapsed': round(elapsed, 1),
            'status': status,
        }
        results.append(result)

        color = "\033[92m" if ok else "\033[91m"
        reset = "\033[0m"
        print()
        print(f"  {color}[{status}]{reset} snap={snap_now}° det={det_now} "
              f"(took {elapsed:.1f}s)")
        print()

    # Summary
    print("=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)
    passes = sum(1 for r in results if r['status'] == 'PASS')
    print(f"  {passes}/{len(results)} stages passed\n")
    print(f"  {'Stage':<20s} {'Target':>7s} {'Snap':>7s} {'Det':>4s} "
          f"{'Time':>6s} {'Status':>6s}")
    print(f"  {'-'*20} {'-'*7} {'-'*7} {'-'*4} {'-'*6} {'-'*6}")
    for r in results:
        tgt = f"{r['target']}°" if r['target'] is not None else "obs"
        snap = f"{r['snap']}°" if isinstance(r['snap'], (int, float)) else r['snap']
        color = "\033[92m" if r['status'] == 'PASS' else "\033[91m"
        reset = "\033[0m"
        print(f"  {r['stage']:<20s} {tgt:>7s} {snap:>7s} {r['det']:4d} "
              f"{r['elapsed']:5.1f}s {color}{r['status']:>6s}{reset}")
    print()

    if logfile:
        logfile.close()
    ser.close()


if __name__ == '__main__':
    main()
