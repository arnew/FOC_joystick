#!/usr/bin/env python3
"""
Minimalistic Joystick Monitor
Displays motor angle and joystick output from debug serial port
"""

import serial
import time
import sys
import glob


def find_debug_port():
    """Find RP2040 debug serial port"""
    ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    return ports[0] if ports else None


def monitor():
    """Monitor joystick values"""
    port = find_debug_port()
    if not port:
        print("✗ No serial port found")
        sys.exit(1)
    
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        print(f"✓ Connected to {port} @ 115200 baud (Ctrl+C to exit)\n")
        print("  Motor Angle      USB Value   Status")
        print("-" * 50)
        
        while True:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                # Look for debug output with angle and USB value
                if "Angle:" in line and "USB:" in line:
                    # Parse: "Angle: X.XXXX rad (X.X°) | Target: X.XXXX | USB: XXX (0-1023)"
                    try:
                        import re
                        angle_m = re.search(r'Angle:\s+([-\d.]+)', line)
                        usb_m = re.search(r'USB:\s+(\d+)', line)
                        
                        if angle_m and usb_m:
                            angle = float(angle_m.group(1))
                            usb_val = int(usb_m.group(1))
                            angle_deg = angle * 180 / 3.14159
                            
                            bar_len = int(usb_val / 1023 * 40)
                            bar = "█" * bar_len + "░" * (40 - bar_len)
                            
                            print(f"  {angle:7.4f} rad  {usb_val:4d}    {bar}")
                    except:
                        pass
    
    except KeyboardInterrupt:
        print("\n✓ Exit")
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
        sys.exit(1)
    finally:
        ser.close()


if __name__ == "__main__":
    monitor()
