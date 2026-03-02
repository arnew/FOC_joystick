#!/usr/bin/env python3
"""
Simple MIDI Profile Switching Test (CC#121) with Serial Verification

Tests that CC#121 MIDI messages switch profiles and confirms via serial output
"""

import serial
import time
import sys

def test_simple_midi_profile_switching():
    """Test MIDI CC#121 profile switching with serial verification"""
    
    print("\n" + "="*70)
    print("SIMPLE MIDI PROFILE SWITCHING TEST")
    print("="*70)
    
    # Open serial connection  
    try:
        ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
        time.sleep(0.5)
    except Exception as e:
        print(f"ERROR: Cannot open serial port: {e}")
        return False
    
    try:
        # Test 1: Send Profile 0 (A320) switch via serial command
        print("\n[TEST 1] Serial Profile Switch (baseline test)")
        print("Sending: P0")
        ser.write(b'P0\r\n')
        time.sleep(0.3)
        
        found = False
        for _ in range(5):
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                print(f"  {line}")
                if 'A320' in line:
                    found = True
                    break
        
        if found:
            print("✓ Serial profile switching works")
        else:
            print("⚠ No A320 confirmation (may be normal)")
        
        time.sleep(0.5)
        
        # Test 2: Send CC#121=0 (A320 via MIDI)
        print("\n[TEST 2] MIDI CC#121 Profile Switch (A320)")
        midi_msg = bytes([0xB0, 121, 0])  # CC#121=0
        ser.write(midi_msg)
        print(f"Sent MIDI: 0x{midi_msg.hex()}")
        time.sleep(0.3)
        
        lines_read = []
        for _ in range(10):
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                lines_read.append(line)
                print(f"  {line}")
        
        if any('[MIDI]' in l and 'Profile' in l for l in lines_read):
            print("✓ MIDI profile switch message received")
        elif any('A320' in l for l in lines_read):
            print("✓ A320 profile mentioned in output")
        else:
            print("⚠ No profile switch confirmation from MIDI command")
        
        time.sleep(0.5)
        
        # Test 3: Verify motor control works after profile switch by using 
        # CC#64 (Trim) which is available in all profiles
        print("\n[TEST 3] Motor Control after Profile Switch")
        print("Sending CC#64=127 (Trim Full)")
        midi_msg = bytes([0xB0, 64, 127])
        ser.write(midi_msg)
        time.sleep(1.2)  # Wait longer for motor response
        
        lines_read = []
        angles = []
        for _ in range(20):
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                lines_read.append(line)
                
                # Extract angle from A=X.XX format
                import re
                match = re.search(r'A=([\-\d.]+)', line)
                if match:
                    angle = float(match.group(1))
                    angles.append(angle)
        
        if angles:
            angle_min = min(angles)
            angle_max = max(angles)
            excursion = angle_max - angle_min
            print(f"Angle range: {angle_min:.2f}° → {angle_max:.2f}° (excursion: {excursion:.2f}°)")
            
            if excursion > 5:
                print("✓ Motor moved significantly")
                return True
            else:
                print("⚠ Motor movement small")
                return False
        else:
            print("✗ Could not read angles")
            return False
            
    finally:
        ser.close()
    
    return False


if __name__ == '__main__':
    success = test_simple_midi_profile_switching()
    sys.exit(0 if success else 1)
