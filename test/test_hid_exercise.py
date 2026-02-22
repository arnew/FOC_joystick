#!/usr/bin/env python3
"""HID exercise test — send MIDI CC and verify HID joystick axis changes via pygame

Requirements: `pygame`, `pyserial`

Behaviour:
- Use `MIDI_PORT` env var if set, otherwise auto-detect a serial port
- Probe for a pygame joystick device and read axis samples
- Send MIDI CC messages to move the axis and assert the joystick axis value changes
"""

import os
import time
import sys
import serial
from serial.tools import list_ports

TIMEOUT = int(os.environ.get("HID_WAIT_TIMEOUT", "10"))
MIDI_BAUD = 31250


def find_midi_port():
    env = os.environ.get("MIDI_PORT")
    if env:
        return env
    ports = list_ports.comports()
    # prefer ACM ports
    candidates = [p.device for p in ports if p.device.startswith('/dev/ttyACM') or p.device.startswith('/dev/ttyUSB')]
    return candidates[0] if candidates else None


def open_midi(port):
    try:
        ser = serial.Serial(port, MIDI_BAUD, timeout=0.1)
        # give firmware a moment
        time.sleep(0.05)
        return ser
    except Exception as e:
        print(f"ERROR: could not open MIDI port {port}: {e}")
        return None


def send_midi_cc(ser, cc, val):
    msg = bytes([0xB0, cc & 0x7F, val & 0x7F])
    ser.write(msg)
    ser.flush()


def probe_pygame(timeout=TIMEOUT):
    try:
        import pygame
    except Exception as e:
        print(f"SKIP: pygame not available: {e}")
        return None

    pygame.init()
    pygame.joystick.init()
    end = time.time() + timeout
    while time.time() < end:
        count = pygame.joystick.get_count()
        if count > 0:
            js = pygame.joystick.Joystick(0)
            js.init()
            print(f"OK: pygame joystick found: {js.get_name()} axes={js.get_numaxes()}")
            return js
        time.sleep(0.2)
    print("SKIP: No pygame joystick detected within timeout")
    return None


def read_axes(js, n=2):
    # Pump events and sample axes
    try:
        import pygame
        pygame.event.pump()
    except Exception:
        pass
    vals = []
    for i in range(min(n, js.get_numaxes())):
        vals.append(js.get_axis(i))
    return vals


def main():
    midi_port = find_midi_port()
    if not midi_port:
        print("✗ FAIL: No MIDI serial port found (set MIDI_PORT env var)")
        sys.exit(2)

    ser = open_midi(midi_port)
    if not ser:
        sys.exit(2)

    js = probe_pygame()
    if not js:
        print("✗ SKIP: No joystick device via pygame")
        ser.close()
        sys.exit(0)

    # Sample baseline
    baseline = read_axes(js, n=2)
    print(f"Baseline axes: {baseline}")

    # Send CC to move axis (use CC#64 as existing tests use)
    print("Sending MIDI CC#64 -> 0")
    send_midi_cc(ser, 64, 0)
    time.sleep(0.35)
    a0 = read_axes(js, n=2)
    print(f"After CC=0 axes: {a0}")

    print("Sending MIDI CC#64 -> 127")
    send_midi_cc(ser, 64, 127)
    # allow motor + HID update
    time.sleep(0.5)
    a1 = read_axes(js, n=2)
    print(f"After CC=127 axes: {a1}")

    ser.close()

    # Evaluate significant axis change on axis 0
    if not baseline or not a1:
        print("✗ FAIL: Unable to read axes")
        sys.exit(2)

    delta = abs(a1[0] - baseline[0])
    print(f"Axis0 delta: {delta:.3f}")
    if delta > 0.4:
        print("✓ PASS: Axis moved significantly after MIDI commands")
        sys.exit(0)
    else:
        print("✗ FAIL: Axis did not change sufficiently")
        sys.exit(2)


if __name__ == '__main__':
    main()
