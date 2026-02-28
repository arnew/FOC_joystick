#!/usr/bin/env python3
"""
Automated firmware upload using RB (reboot-to-bootloader) command.
This eliminates the need for manual BOOTSEL button presses.
"""

import serial
import time
import subprocess
import sys
from pathlib import Path

def upload_firmware_via_rb(device="/dev/ttyACM0", timeout=30):
    """
    Upload firmware using RB command:
    1. Connect to device
    2. Send 'RB' command to reboot to BOOTSEL
    3. Wait for BOOTSEL mount
    4. Run platformio upload
    """
    
    print("=== Automated Firmware Upload via RB ===\n")
    
    # Step 1: Connect to device
    print(f"1. Connecting to {device}...")
    try:
        ser = serial.Serial(device, 115200, timeout=1)
        time.sleep(0.5)
        ser.read_all()
        print("   ✓ Connected\n")
    except Exception as e:
        print(f"   ✗ Failed to connect: {e}")
        return False
    
    # Step 2: Send RB command
    print("2. Sending RB (reboot to bootloader)...")
    ser.write(b'RB\n')
    time.sleep(0.5)
    response = ser.read_all().decode('utf-8', errors='ignore')
    ser.close()
    
    if 'BOOTLOADER' in response:
        print(f"   ✓ Bootloader command acknowledged\n")
    else:
        print(f"   ℹ Response: {response[:100]}\n")
    
    # Step 3: Wait for BOOTSEL mount
    print("3. Waiting for BOOTSEL mount (30s timeout)...")
    for i in range(30):
        if Path("/media").exists():
            for user in Path("/media").iterdir():
                if (user / "RPI-RP2").exists():
                    print(f"   ✓ BOOTSEL detected at {user}/RPI-RP2\n")
                    time.sleep(1)
                    break
            else:
                continue
            break
        
        time.sleep(1)
        if i % 5 == 0:
            print(f"   ... ({i}s)")
    else:
        print("   ✗ BOOTSEL mount timeout")
        return False
    
    # Step 4: Run platformio upload
    print("4. Running PlatformIO upload...")
    result = subprocess.run(
        ["platformio", "run", "--environment", "pico_1motor_endless", "--target", "upload"],
        cwd=Path(__file__).parent.parent
    )
    
    if result.returncode == 0:
        print("\n   ✓ Upload successful!\n")
        return True
    else:
        print("\n   ✗ Upload failed")
        return False

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Automated firmware upload via RB command')
    parser.add_argument('--device', default='/dev/ttyACM0', help='Serial device path')
    parser.add_argument('--timeout', type=int, default=30, help='Timeout in seconds')
    args = parser.parse_args()
    
    success = upload_firmware_via_rb(args.device, args.timeout)
    sys.exit(0 if success else 1)
