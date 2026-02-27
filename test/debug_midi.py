#!/usr/bin/env python3
"""
Minimalistic MIDI Debug Tool
Send individual MIDI CC commands to the device
"""

import serial
import time
import sys
import glob


def find_midi_port():
    """Find RP2040 MIDI serial port (usually /dev/ttyACM1)"""
    ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
    if len(ports) >= 2:
        return ports[1]  # Prefer second port for MIDI
    return ports[0] if ports else None


def send_cc(ser, cc_num, cc_val):
    """Send MIDI CC message"""
    # MIDI CC: 0xBn (status), CC# (controller), value
    msg = bytes([0xB0, cc_num & 0x7F, cc_val & 0x7F])
    ser.write(msg)
    ser.flush()


def main():
    """Interactive MIDI sender"""
    port = find_midi_port()
    if not port:
        print("✗ No serial port found")
        sys.exit(1)
    
    try:
        ser = serial.Serial(port, 31250, timeout=1)
        print(f"✓ Connected to {port} @ 31250 baud")
        print("\nUsage:")
        print("  cc <num> <val>   - Send CC (e.g., cc 64 100)")
        print("  sweep <cc> [min] [max] [step] - Send CC sweep")
        print("  exit             - Quit\n")
        
        while True:
            try:
                cmd = input("> ").strip().lower()
                
                if cmd == "exit":
                    break
                
                elif cmd.startswith("cc "):
                    parts = cmd[3:].split()
                    if len(parts) >= 2:
                        cc_num = int(parts[0])
                        cc_val = int(parts[1])
                        if 0 <= cc_num <= 127 and 0 <= cc_val <= 127:
                            send_cc(ser, cc_num, cc_val)
                            print(f"  → Sent CC#{cc_num} = {cc_val}")
                        else:
                            print("  ✗ CC# and value must be 0-127")
                    else:
                        print("  Usage: cc <num> <val>")
                
                elif cmd.startswith("sweep "):
                    parts = cmd[6:].split()
                    if len(parts) >= 1:
                        cc_num = int(parts[0])
                        cc_min = int(parts[1]) if len(parts) > 1 else 0
                        cc_max = int(parts[2]) if len(parts) > 2 else 127
                        cc_step = int(parts[3]) if len(parts) > 3 else 10
                        
                        print(f"  → Sweeping CC#{cc_num}: {cc_min} to {cc_max} (step {cc_step})")
                        for cc_val in range(cc_min, cc_max + 1, cc_step):
                            send_cc(ser, cc_num, cc_val)
                            print(f"     CC#{cc_num} = {cc_val}")
                            time.sleep(0.1)
                    else:
                        print("  Usage: sweep <cc_num> [min] [max] [step]")
                
                else:
                    print("  ✗ Unknown command")
            
            except ValueError:
                print("  ✗ Invalid input")
            except KeyboardInterrupt:
                break
        
        print("\n✓ Exit")
    
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
        sys.exit(1)
    finally:
        ser.close()


if __name__ == "__main__":
    main()
