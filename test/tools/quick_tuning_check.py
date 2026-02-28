#!/usr/bin/env python3
"""Quick manual test to verify PID tuning improvement"""

import serial
import time
import sys

def test_position(ser, target_deg, timeout=3.0):
    """Test if motor reaches target within tolerance"""
    # Send target
    cmd = f"0T{target_deg}\n"
    ser.write(cmd.encode())
    
    start = time.time()
    positions = []
    
    # Collect samples for timeout duration
    while time.time() - start < timeout:
        time.sleep(0.05)
        positions.append(read_position(ser))
    
    # Check last 10 samples (0.5s)
    recent = positions[-10:] if len(positions) >= 10 else positions
    avg = sum(recent) / len(recent) if recent else 360
    error = abs(avg - target_deg)
    if error > 180:
        error = 360 - error
    
    variance = max(recent) - min(recent) if len(recent) > 1 else 0
    
    settled = error <= 1.0 and variance <= 1.0
    
    return settled, error, variance

def read_position(ser):
    """Read current angle"""
    ser.write(b"0A\n")
    time.sleep(0.02)
    resp = ser.read_all().decode('ascii', errors='ignore')
    
    # Parse "A=123.45 T=..." format
    for line in resp.split('\n'):
        if 'A=' in line:
            try:
                angle_str = line.split('A=')[1].split()[0]
                return float(angle_str)
            except:
                pass
    return 0.0

def main():
    print("✓ Connecting to /dev/ttyACM0")
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=0.5)
    time.sleep(1.0)
    ser.read_all()  # Clear buffer
    
    test_positions = [0, 45, 90, 135, 180, 225, 270, 315]
    
    print("\n=== Testing with 3s settle time ===")
    settled_count = 0
    errors = []
    
    for pos in test_positions:
        print(f"  Target: {pos}° ... ", end='', flush=True)
        settled, error, variance = test_position(ser, pos, timeout=3.0)
        errors.append(error)
        
        if settled:
            settled_count += 1
            print(f"✓ {error:.2f}° ± {variance:.2f}°")
        else:
            print(f"✗ {error:.2f}° ± {variance:.2f}°")
    
    avg_error = sum(errors) / len(errors)
    pass_rate = (settled_count / len(test_positions)) * 100
    
    print(f"\n=== Results ===")
    print(f"  Settled: {settled_count}/{len(test_positions)} ({pass_rate:.0f}%)")
    print(f"  Avg error: {avg_error:.2f}°")
    
    if pass_rate >= 90:
        print("  ✓ Target achieved!")
    elif pass_rate >= 75:
        print("  ⏳ Good progress, close to target")
    elif pass_rate >= 50:
        print("  ⏳ Improvement seen, needs more tuning")
    else:
        print("  ✗ Significant tuning needed")
    
    ser.close()
    return 0 if pass_rate >= 90 else 1

if __name__ == '__main__':
    sys.exit(main())
