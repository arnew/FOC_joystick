#!/usr/bin/env python3
"""
MIDI Profile Switching Test (CC#121)

Tests runtime profile switching via MIDI Control Change #121:
- Value 0 = A320 profile
- Value 1 = Cessna profile  
- Value 2 = Glider profile

Verifies that profile switching works and doesn't break MIDI axis control.
"""

import serial
import time
import sys
import re

def send_midi_cc(ser, cc_number, cc_value):
    """Send a MIDI Control Change message via USB"""
    # MIDI CC format: 0xB0 (Control Change status, channel 0) + CC# + Value
    midi_msg = bytes([0xB0, cc_number & 0x7F, cc_value & 0x7F])
    ser.write(midi_msg)


def read_telemetry(ser, timeout=3.0):
    """Read telemetry line from device"""
    start_time = time.time()
    buffer = ""
    
    while time.time() - start_time < timeout:
        if ser.in_waiting:
            byte = ser.read(1).decode('utf-8', errors='ignore')
            
            if byte == '\n':
                return buffer.strip()
            else:
                buffer += byte
    
    return None


def parse_angle(line):
    """Extract angle from telemetry line: 'A=angle T=target JS=x,y'"""
    match = re.search(r'A=([-\d.]+)', line)
    if match:
        return float(match.group(1))
    return None


def test_midi_profile_switching():
    """Test MIDI CC#121 profile switching"""
    
    print("\n" + "="*70)
    print("MIDI PROFILE SWITCHING TEST (CC#121)")
    print("="*70)
    
    # Open serial connection to device
    try:
        ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
        time.sleep(0.5)
    except Exception as e:
        print(f"ERROR: Cannot open serial port: {e}")
        return False
    
    # Profile definitions
    profiles = [
        {
            "id": 0,
            "name": "A320",
            "test_cc": 7,  # Throttle
            "test_value": 100,
            "expected_range": (20, 150)  # Expected motor movement range
        },
        {
            "id": 1,
            "name": "Cessna",
            "test_cc": 7,  # Throttle (same axis in Cessna)
            "test_value": 100,
            "expected_range": (20, 150)
        },
        {
            "id": 2,
            "name": "Glider",
            "test_cc": 2,  # Spoilers (different axis)
            "test_value": 64,
            "expected_range": (10, 100)
        }
    ]
    
    all_passed = True
    
    try:
        for profile in profiles:
            print(f"\n[TEST] Switching to {profile['name']} profile (CC#121={profile['id']})")
            
            # Send profile switch command
            send_midi_cc(ser, 121, profile['id'])
            time.sleep(0.3)
            
            # Read several telemetry lines to see profile switch message
            print("  Waiting for profile switch confirmation...")
            found_switch = False
            for _ in range(10):
                line = read_telemetry(ser, timeout=1.0)
                if line and '[MIDI]' in line and 'Profile' in line:
                    print(f"    {line}")
                    found_switch = True
                    break
                elif line:
                    print(f"    {line}")
            
            if not found_switch:
                print("    WARNING: No profile switch confirmation message received")
            
            # Wait a bit for profile to fully activate
            time.sleep(0.3)
            
            # Now test that axis control still works
            print(f"  Testing profile-specific axis: CC#{profile['test_cc']}={profile['test_value']}")
            send_midi_cc(ser, profile['test_cc'], profile['test_value'])
            time.sleep(0.2)
            
            # Read motor response
            angles = []
            for i in range(15):
                line = read_telemetry(ser, timeout=0.5)
                if line:
                    angle = parse_angle(line)
                    if angle is not None:
                        angles.append(angle)
                        if i < 5:  # Print first few
                            print(f"    Angle: {angle:.2f}°")
            
            # Check if motor moved
            if len(angles) >= 2:
                angle_min = min(angles)
                angle_max = max(angles)
                angle_range = angle_max - angle_min
                
                print(f"  Motor response: {angle_min:.2f}° → {angle_max:.2f}° (range: {angle_range:.2f}°)")
                
                if angle_range > 5:  # More than 5 degrees movement indicates working axis
                    print(f"  ✓ PASS: {profile['name']} profile axis working")
                else:
                    print(f"  ✗ FAIL: {profile['name']} profile axis not responding (range < 5°)")
                    all_passed = False
            else:
                print(f"  ✗ FAIL: Could not read motor angles")
                all_passed = False
            
            time.sleep(0.5)
        
        # Final test: Verify we're back to A320 after sequence
        print(f"\n[TEST] Verify final state by switching back to A320")
        send_midi_cc(ser, 121, 0)
        time.sleep(0.3)
        
        # Read confirmation
        for _ in range(5):
            line = read_telemetry(ser, timeout=1.0)
            if line:
                print(f"  {line}")
                if 'A320' in line:
                    print("  ✓ Successfully returned to A320")
                    break
        
    finally:
        ser.close()
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ PASS: MIDI Profile Switching Test Complete")
        print("="*70)
        return True
    else:
        print("✗ FAIL: Some tests failed")
        print("="*70)
        return False


if __name__ == '__main__':
    success = test_midi_profile_switching()
    sys.exit(0 if success else 1)
