#!/usr/bin/env python3
"""Test aircraft profile switching via serial A command"""

import serial
import time
import re

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
time.sleep(0.5)

print("Testing A command (Aircraft profile switching)")
print("=" * 60)

try:
    # Test 1: Just show current profile (A with no argument)
    print("\n[1] Show current profile (A):")
    ser.write(b'A\r\n')
    time.sleep(0.3)
    
    for _ in range(10):
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if '[PROFILES]' in line or 'Aircraft' in line or 'A3 20' in line or 'Cessna' in line or 'Glider' in line:
                print(f"  {line}")
        time.sleep(0.05)
    
    # Test 2: Switch to A320 (A0)  
    print("\n[2] Switch to A320 (A0):")
    ser.write(b'A0\r\n')
    time.sleep(0.3)
    
    for _ in range(5):
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if '[PROFILES]' in line:
                print(f"  {line}")
        time.sleep(0.05)
    
    # Test 3: Switch to Ceena (A1)
    print("\n[3] Switch to Cessna (A1):")
    ser.write(b'A1\r\n')
    time.sleep(0.3)
    
    for _ in range(5):
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if '[PROFILES]' in line:
                print(f"  {line}")
        time.sleep(0.05)
    
    # Test 4: Invalid profile (A9)  
    print("\n[4] Test invalid profile (A9):")
    ser.write(b'A9\r\n')
    time.sleep(0.3)
    
    for _ in range(5):
        if ser.in_waiting:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if '[PROFILES]' in line:
                print(f"  {line}")
        time.sleep(0.05)
    
    print("\n" + "=" * 60)
    print("Profile switching test complete")

finally:
    ser.close()
