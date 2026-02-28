#!/usr/bin/env python3
"""Simple direct test of motor movement"""

import serial
import time

def send_and_read(ser, cmd, delay=0.2):
    """Send command and read response"""
    ser.write((cmd + '\n').encode())
    time.sleep(delay)
    resp = ser.read_all().decode('ascii', errors='ignore')
    return resp.strip()

def main():
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    time.sleep(1)
    ser.read_all()
    
    print("=== Direct SimpleFOC Commands Test ===\n")
    
    # Query current position
    print("1. Current position:")
    resp = send_and_read(ser, "0A")
    print(f"   {resp}\n")
    
    # Move to 45°
    print("2. Move to 45°:")
    resp = send_and_read(ser, "0T45", delay=2.0)
    print(f"   Command: {resp}")
    resp = send_and_read(ser, "0A")
    print(f"   Position: {resp}\n")
    
    # Move to 135°
    print("3. Move to 135°:")
    resp = send_and_read(ser, "0T135", delay=2.0)
    print(f"   Command: {resp}")
    resp = send_and_read(ser, "0A")
    print(f"   Position: {resp}\n")
    
    # Move to 225°
    print("4. Move to 225°:")
    resp = send_and_read(ser, "0T225", delay=2.0)
    print(f"   Command: {resp}")
    resp = send_and_read(ser, "0A")
    print(f"   Position: {resp}\n")
    
    # Check motor status
    print("5. Motor status:")
    resp = send_and_read(ser, "0?")
    print(f"   {resp}\n")
    
    # Query PID values
    print("6. PID configuration:")
    for cmd in ['0AP', '0AI', '0AD']:
        resp = send_and_read(ser, cmd)
        print(f"   {cmd}: {resp}")
    
    ser.close()

if __name__ == '__main__':
    main()
