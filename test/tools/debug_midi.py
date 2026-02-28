#!/usr/bin/env python3
"""
Minimalistic MIDI Debug Tool
Send individual MIDI CC commands to the device
"""

import serial
import time
import sys
import glob

SWEEP_DEFAULT_DELAY_S = 1.5


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
        print(f"  sweep <cc> [min] [max] [step] [delay_s] - Send CC sweep (default delay {SWEEP_DEFAULT_DELAY_S:.1f}s)")
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
                        if cc_step <= 0:
                            print("  ✗ step must be > 0")
                            continue
                        delay_s = float(parts[4]) if len(parts) > 4 else SWEEP_DEFAULT_DELAY_S
                        if delay_s < 0.0:
                            print("  ✗ delay_s must be >= 0")
                            continue
                        step_count = ((cc_max - cc_min) // cc_step) + 1
                        start = time.time()
                        
                        print(f"  → Sweeping CC#{cc_num}: {cc_min} to {cc_max} (step {cc_step}, delay {delay_s:.2f}s)")
                        for idx, cc_val in enumerate(range(cc_min, cc_max + 1, cc_step), start=1):
                            send_cc(ser, cc_num, cc_val)
                            elapsed = time.time() - start
                            print(f"     [{idx:02d}/{step_count:02d}] t={elapsed:5.1f}s  CC#{cc_num} = {cc_val}")
                            time.sleep(delay_s)
                    else:
                        print("  Usage: sweep <cc_num> [min] [max] [step] [delay_s]")
                
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
