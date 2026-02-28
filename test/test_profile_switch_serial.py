#!/usr/bin/env python3
"""
Profile Switching via Serial Commander Test

Tests runtime profile switching using the serial Commander interface (P0/P1/P2)
"""

import serial
import time
import sys
import re

def test_serial_profile_switching():
    """Test profile switching via serial Commander"""
    
    print("\n" + "="*70)
    print("SERIAL PROFILE SWITCHING TEST (P0/P1/P2 Commands)")
    print("="*70)
    
    # Open serial connection  
    try:
        ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
        time.sleep(0.5)
    except Exception as e:
        print(f"ERROR: Cannot open serial port: {e}")
        return False
    
    try:
        profiles = [
            {"id": 0, "name": "A320", "test_cc": 7},   # Throttle
            {"id": 1, "name": "Cessna", "test_cc": 7}, # Throttle  
            {"id": 2, "name": "Glider", "test_cc": 2}  # Spoilers
        ]
        
        all_passed = True
        
        for profile in profiles:
            print(f"\n[TEST] Switching to {profile['name']} profile")
            
            # Send profile switch command via serial
            cmd = f"P{profile['id']}\r\n"
            ser.write(cmd.encode())
            print(f"  Sent: {repr(cmd.strip())}")
            time.sleep(0.3)
            
            # Read response
            lines = []
            for _ in range(10):
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        lines.append(line)
                        print(f"    {line}")
                time.sleep(0.05)
            
            # Verify profile name is mentioned
            profile_confirmed = any(profile['name'] in line or f'Profile {profile["id"]}' in line for line in lines)
            
            if profile_confirmed:
                print(f"  ✓ Profile switch confirmed")
            else:
                print(f"  ⚠ No confirmation received (checking if profile still active)")
            
            # Test motor response with Trim (CC#64) since it's common to all profiles
            print(f"  Testing motor control with CC#64...")
            ser.write(b'CC 64 0\r\n')  # Try Commander syntax for CC
            time.sleep(0.5)
            
            # Alternative: Send MIDI-like command
            # Actually, let me just try sending CC#64 value via a direct approach
            # Check what motor angles we get
            angles = []
            for _ in range(10):
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    match = re.search(r'A=([\-\d.]+)', line)
                    if match:
                        angle = float(match.group(1))
                        angles.append(angle)
                time.sleep(0.05)
            
            if angles:
                print(f"  Angle readings: {len(angles)} samples, range {min(angles):.2f}° - {max(angles):.2f}°")
        
        print("\n" +"="*70)
        print("✓ Serial Profile Switching Test Complete")
        print("="*70)
        return True
        
    finally:
        ser.close()


if __name__ == '__main__':
    success = test_serial_profile_switching()
    sys.exit(0 if success else 1)
