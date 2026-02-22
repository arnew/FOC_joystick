#!/usr/bin/env python3
"""Quick MIDI protocol test"""
import serial
import time
import sys

port = "/dev/ttyACM0"
ser = serial.Serial(port, 115200, timeout=2)
time.sleep(1)

print("="*60)
print("MIDI PROTOCOL DEBUG TEST")
print("="*60)
print(f"Connected to {port}")
print("\nSending test commands and watching for [MIDI RX] responses\n")

# Clear buffer
ser.reset_input_buffer()
time.sleep(0.5)

# Test commands (format: [MCC,VAL])
tests = [
    "[M64,0]",      # CC#64 value 0
    "[M64,64]",     # CC#64 value 64
    "[M64,127]",    # CC#64 value 127
    "[M7,100]",     # CC#7 value 100
]

for cmd in tests:
    print(f"→ Sending: {cmd}")
    ser.write(cmd.encode())
    ser.flush()
    time.sleep(0.2)
    
    # Read response
    found_midi = False
    while ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if '[MIDI RX]' in line:
            print(f"  ✓ {line}")
            found_midi = True
        elif 'MIDI:' in line:
            print(f"  ✓ {line}")
            found_midi = True
        elif 'angle:' in line.lower():
            print(f"  → {line}")
    
    if not found_midi:
        print(f"  ✗ No MIDI response detected")
    print()

print("Test complete. Check if all commands received MIDI responses.")
ser.close()
