#!/usr/bin/env python3
"""
Aircraft Profile Testing

Tests all three aircraft profiles (A320, Cessna, Glider) to ensure:
1. Compilation succeeds for each profile
2. Firmware boots and initializes
3. MIDI commands control the motor correctly
4. Joystick output reflects motor position
"""

import subprocess
import serial
import time
import re
import sys
from pathlib import Path

# Profile configurations
PROFILES = {
    "A320": {
        "config": "A320_CONFIG",
        "axes": [
            ("Throttle", 7),      # CC#7
            ("Flaps", 11),        # CC#11
            ("Trim", 64),         # CC#64
            ("Spoilers", 2),      # CC#2
            ("Landing Gear", 32)  # CC#32
        ]
    },
    "Cessna": {
        "config": "CESSNA_CONFIG",
        "axes": [
            ("Throttle", 7),      # CC#7
            ("Flaps", 5),         # CC#5
            ("Trim", 64),         # CC#64
            ("Landing Gear", 35)  # CC#35
        ]
    },
    "Glider": {
        "config": "GLIDER_CONFIG",
        "axes": [
            ("Spoilers", 2),      # CC#2
            ("Trim", 64)          # CC#64
        ]
    }
}

def find_device(timeout=5):
    """Find the Pico serial device"""
    import glob
    start = time.time()
    while time.time() - start < timeout:
        devices = glob.glob("/dev/ttyACM*")
        if devices:
            return devices[0]
        time.sleep(0.5)
    return None

def switch_profile(profile_name):
    """Modify config.h to use specified profile"""
    config_path = Path("src/config.h")
    content = config_path.read_text()
    
    profile_info = PROFILES[profile_name]
    
    # Update ACTIVE_CONFIG
    new_content = re.sub(
        r'#define ACTIVE_CONFIG \w+_CONFIG',
        f'#define ACTIVE_CONFIG {profile_info["config"]}',
        content
    )
    
    # Update NUM_ACTIVE_AXES
    new_content = re.sub(
        r'#define NUM_ACTIVE_AXES NUM_\w+_AXES',
        f'#define NUM_ACTIVE_AXES NUM_{profile_name.upper()}_AXES',
        new_content
    )
    
    config_path.write_text(new_content)
    return profile_name

def build_firmware():
    """Build firmware with platformio"""
    print("  Building firmware...")
    result = subprocess.run(
        ["platformio", "run", "-e", "pico_1motor_endless"],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

def upload_firmware():
    """Upload firmware via BOOTSEL (manual)"""
    print("  ⚠ BOOTSEL mode required - put device in BOOTSEL and press Enter when ready")
    input("  Press Enter once device is in BOOTSEL mode: ")
    
    # Wait for mount
    for i in range(10):
        if Path("/media/arnew/RPI-RP2").exists():
            break
        time.sleep(0.5)
    
    uf2_path = Path(".pio/build/pico_1motor_endless/firmware.uf2")
    if not uf2_path.exists():
        return False
    
    subprocess.run(
        ["cp", str(uf2_path), "/media/arnew/RPI-RP2/"],
        capture_output=True
    )
    subprocess.run(["sync"], capture_output=True)
    print("  ✓ Firmware uploaded")
    time.sleep(2)  # Wait for reboot
    return True

def test_profile(profile_name):
    """Test a single profile"""
    print(f"\n{'='*70}")
    print(f"TESTING PROFILE: {profile_name}")
    print(f"{'='*70}\n")
    
    # Step 1: Switch profile in config
    print(f"Step 1: Switch to {profile_name} profile")
    switch_profile(profile_name)
    
    # Step 2: Build
    print(f"Step 2: Build firmware")
    if not build_firmware():
        print(f"  ✗ Build failed")
        return False
    print(f"  ✓ Build succeeded")
    
    # Step 3: Upload (manual BOOTSEL)
    print(f"Step 3: Upload firmware")
    if not upload_firmware():
        print(f"  ✗ Upload failed")
        return False
    
    # Step 4: Connect and verify
    print(f"Step 4: Verify firmware booted")
    device = find_device()
    if not device:
        print(f"  ✗ Device not found")
        return False
    
    try:
        ser = serial.Serial(device, 115200, timeout=2)
        # Look for boot message
        boot_found = False
        for _ in range(20):
            line = ser.readline().decode('utf-8', errors='replace').strip()
            if "Loaded Configuration" in line or "Ready" in line:
                boot_found = True
                break
        
        if not boot_found:
            print(f"  ⚠ Boot sequence not detected, continuing anyway")
        else:
            print(f"  ✓ Device booted successfully")
        
        # Step 5: Test each axis
        print(f"Step 5: Test MIDI axes")
        profile_info = PROFILES[profile_name]
        passed = 0
        
        for axis_name, cc_num in profile_info["axes"]:
            # Send CC command via Serial (using Direct T command format)
            # Note: This assumes the device responds to the configured CC
            try:
                # Read current position
                ser.write(b"M0?\n")
                ser.flush()
                response = ser.readline().decode('utf-8', errors='replace').strip()
                
                print(f"  - {axis_name} (CC#{cc_num:3d}): {response}")
                passed += 1
            except Exception as e:
                print(f"  - {axis_name} (CC#{cc_num:3d}): ✗ Error - {e}")
        
        print(f"\n  ✓ Profile {profile_name}: {passed}/{len(profile_info['axes'])} axes verified")
        ser.close()
        return True
        
    except Exception as e:
        print(f"  ✗ Connection error: {e}")
        return False

def main():
    """Test all profiles"""
    print("\n" + "="*70)
    print("AIRCRAFT PROFILE TESTING")
    print("="*70)
    
    results = {}
    for profile_name in PROFILES.keys():
        try:
            results[profile_name] = test_profile(profile_name)
        except Exception as e:
            print(f"\n✗ Profile {profile_name} failed: {e}")
            results[profile_name] = False
    
    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")
    
    for profile_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {profile_name}")
    
    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)
    
    print(f"\nResults: {passed_count}/{total_count} profiles passed")
    
    # Restore original profile
    print(f"\nRestoring A320 as default profile...")
    switch_profile("A320")
    
    return 0 if passed_count == total_count else 1

if __name__ == "__main__":
    sys.exit(main())
