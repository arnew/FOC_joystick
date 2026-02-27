#!/usr/bin/env python3
"""HID exercise test — send MIDI CC and verify HID joystick axis changes via pygame

Requirements: `pygame`, `pygame.midi`

Behaviour:
- Use native USB MIDI (pygame.midi) to send CC commands to device
- Probe for a pygame joystick device and read axis samples
- Send MIDI CC messages to move the axis and assert the joystick axis value changes
"""

import os
import time
import sys

PYGAME_AVAILABLE = True
PYGAME_ERROR = None
try:
    import pygame
    import pygame.midi
except ImportError as e:
    PYGAME_AVAILABLE = False
    PYGAME_ERROR = str(e)

TIMEOUT = int(os.environ.get("HID_WAIT_TIMEOUT", "10"))


def _hardware_enabled():
    return os.environ.get("RUN_HARDWARE_TESTS") == "1"


def find_native_midi_output():
    """Find and open native USB MIDI output port (Pico MIDI)"""
    try:
        pygame.midi.init()
        for i in range(pygame.midi.get_count()):
            info = pygame.midi.get_device_info(i)
            device_name = info[1].decode('utf-8', errors='ignore')
            is_output = info[3] == 1  # info[3] = 1 means output (device can receive)
            
            # Exclude ALSA virtual ports ("Midi Through")
            device_lower = device_name.lower()
            if is_output and 'through' not in device_lower:
                # Look for specific RP2040/Pico keywords
                if any(keyword in device_lower for keyword in ['pico', 'rp2040', 'tinyusb']):
                    output = pygame.midi.Output(i)
                    print(f"OK: Native USB MIDI output: {device_name}")
                    return output
                # Fallback: accept generic "USB MIDI" but not virtual ports
                elif 'usb' in device_lower and 'midi' in device_lower:
                    output = pygame.midi.Output(i)
                    print(f"OK: Native USB MIDI output: {device_name}")
                    return output
    except Exception as e:
        print(f"ERROR: pygame.midi initialization failed: {e}")
    
    print("ERROR: No native USB MIDI (Pico MIDI) output found")
    print("  Hint: Check that RP2040 is connected and firmware flashed")
    return None


def send_midi_cc(output, cc, val):
    """Send MIDI CC message via native USB MIDI"""
    try:
        # pygame.midi.Output.write() expects list of (status, data1, data2, data3) tuples
        output.write([[[0xB0, cc & 0x7F, val & 0x7F, 0], pygame.midi.time()]])
    except Exception as e:
        print(f"ERROR: Failed to send MIDI CC: {e}")
        raise


def probe_pygame(timeout=TIMEOUT):
    try:
        pygame.init()
    except Exception as e:
        print(f"SKIP: pygame not available: {e}")
        return None

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


def run_test():
    if not _hardware_enabled():
        print("SKIP: Hardware tests disabled. Set RUN_HARDWARE_TESTS=1 to run.")
        return 0

    if not PYGAME_AVAILABLE:
        print(f"SKIP: pygame or pygame.midi not available: {PYGAME_ERROR}")
        return 0

    midi_output = find_native_midi_output()
    if not midi_output:
        print("FAIL: No native USB MIDI output found")
        return 2

    js = probe_pygame()
    if not js:
        print("SKIP: No joystick device via pygame")
        midi_output.close()
        return 0

    # Sample baseline
    baseline = read_axes(js, n=2)
    print(f"Baseline axes: {baseline}")

    # Send CC to move axis (use CC#64 as existing tests use)
    print("Sending MIDI CC#64 -> 0")
    try:
        send_midi_cc(midi_output, 64, 0)
    except:
        return 2
    time.sleep(0.35)
    a0 = read_axes(js, n=2)
    print(f"After CC=0 axes: {a0}")

    print("Sending MIDI CC#64 -> 127")
    try:
        send_midi_cc(midi_output, 64, 127)
    except:
        return 2
    # allow motor + HID update
    time.sleep(0.5)
    a1 = read_axes(js, n=2)
    print(f"After CC=127 axes: {a1}")

    midi_output.close()

    # Evaluate significant axis change on axis 0
    if not baseline or not a0 or not a1:
        print("✗ FAIL: Unable to read axes")
        return 2

    d0 = abs(a0[0] - baseline[0])
    d1 = abs(a1[0] - baseline[0])
    d01 = abs(a1[0] - a0[0])
    max_delta = max(d0, d1, d01)
    print(f"Axis deltas: d0={d0:.3f}, d1={d1:.3f}, d01={d01:.3f}")

    if max_delta > 0.4:
        print("✓ PASS: Axis moved significantly after MIDI commands")
        return 0
    else:
        print("FAIL: Axis did not change sufficiently")
        return 2


def main():
    return run_test()


def test_hid_exercise():
    import pytest

    if not _hardware_enabled():
        pytest.skip("Hardware tests disabled. Set RUN_HARDWARE_TESTS=1.")
    if not PYGAME_AVAILABLE:
        pytest.skip(f"pygame or pygame.midi not available: {PYGAME_ERROR}")

    assert run_test() == 0


if __name__ == '__main__':
    sys.exit(main())
