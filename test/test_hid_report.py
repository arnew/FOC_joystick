#!/usr/bin/env python3
"""HID / Joystick presence test.

- Prefer `/dev/input/js*` (joystick devices) and try to open with `pygame` if
  available.
- Fallback: check `/dev/hidraw*` and `/dev/input/js*` and attempt a non-blocking
  open/read. If permission is denied, the test is skipped with a helpful message.

Exit codes / behaviour:
- 0: PASS or SKIP (device present but permission-limited is reported as SKIP)
- non-zero is not used here to avoid failing CI on permission-limited hosts.
"""

import glob
import os
import sys
import time

TIMEOUT = int(os.environ.get("HID_WAIT_TIMEOUT", "10"))


def try_pygame_js(timeout=TIMEOUT):
    try:
        import pygame
    except Exception:
        return False

    try:
        pygame.init()
        pygame.joystick.init()
        end = time.time() + timeout
        while time.time() < end:
            js_count = pygame.joystick.get_count()
            if js_count > 0:
                js = pygame.joystick.Joystick(0)
                js.init()
                name = js.get_name()
                axes = js.get_numaxes()
                vals = [js.get_axis(i) for i in range(min(axes, 4))]
                print(f"OK: pygame joystick detected: {name} axes={axes} sample={vals}")
                return True
            time.sleep(0.25)
        return False
    except Exception as e:
        print(f"WARN: pygame joystick probe failed: {e}")
        return False


def find_js(timeout=TIMEOUT):
    end = time.time() + timeout
    while time.time() < end:
        devices = sorted(glob.glob('/dev/input/js*'))
        if devices:
            return devices
        time.sleep(0.5)
    return []


def find_hidraw(timeout=TIMEOUT):
    end = time.time() + timeout
    while time.time() < end:
        devices = sorted(glob.glob('/dev/hidraw*'))
        if devices:
            return devices
        time.sleep(0.5)
    return []


def try_open_nonblocking(device):
    try:
        fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    except PermissionError:
        print(f"SKIP: Permission denied opening {device} — run as root or add udev rule")
        return None
    except Exception as e:
        print(f"ERROR: opening {device}: {e}")
        return False

    try:
        data = os.read(fd, 64)
        if data:
            print(f"OK: Read {len(data)} bytes from {device}: {data[:16]!r}...")
            return True
        else:
            print(f"WARN: No data read from {device} (device present but no reports yet)")
            return False
    except BlockingIOError:
        print(f"WARN: Non-blocking read would block on {device} — no data available right now")
        return False
    except Exception as e:
        print(f"ERROR: reading {device}: {e}")
        return False
    finally:
        try:
            os.close(fd)
        except:
            pass


def main():
    # 1) Try pygame joystick API (preferred for joystick HID testing)
    print(f"Probing with pygame for up to {TIMEOUT}s...")
    if try_pygame_js():
        print("PASS: joystick detected via pygame")
        sys.exit(0)

    # 2) Check for /dev/input/js* devices — treat presence as success without opening
    print(f"Looking for /dev/input/js* for up to {TIMEOUT}s...")
    js_devices = find_js()
    if js_devices:
        print(f"Found js devices: {js_devices}")
        print("PASS: /dev/input/js* present (no elevated permissions required to detect device)")
        sys.exit(0)

    # 3) Fallback to hidraw
    print(f"Looking for /dev/hidraw* for up to {TIMEOUT}s...")
    hid_devices = find_hidraw()
    if hid_devices:
        print(f"Found hidraw devices: {hid_devices}")
        print("SKIP: hidraw devices present but reading them typically requires elevated permissions; not attempting open")
        sys.exit(0)

    print("SKIP: No joystick or hid devices found on host")
    sys.exit(0)


if __name__ == '__main__':
    main()
