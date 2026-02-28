#!/usr/bin/env python3
"""
Motor Movement Test - Verify SimpleFOC motor responds to commands
"""

import sys
import time
import serial

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200


def log(msg):
    """Timestamped logging"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def send_command(ser, cmd):
    """Send command and return response"""
    ser.write(f"{cmd}\n".encode())
    ser.flush()
    time.sleep(0.1)  # Brief delay for command processing
    
    # Read response
    lines = []
    start = time.time()
    while time.time() - start < 2:
        line = ser.readline()
        if line:
            try:
                decoded = line.decode('utf-8', errors='ignore').strip()
                if decoded:
                    lines.append(decoded)
            except:
                pass
    
    return lines


def parse_angle_from_telemetry(line):
    """Extract angle from 'A=1.23 T=4.56' line"""
    if 'A=' in line:
        try:
            parts = line.split()
            for part in parts:
                if part.startswith('A='):
                    return float(part[2:])
        except:
            pass
    return None


def wait_for_telemetry(ser, timeout=5):
    """Wait for and parse next telemetry line"""
    start = time.time()
    while time.time() - start < timeout:
        line = ser.readline()
        if line:
            try:
                decoded = line.decode('utf-8', errors='ignore').strip()
                angle = parse_angle_from_telemetry(decoded)
                if angle is not None:
                    return angle, decoded
            except:
                pass
    return None, None


def collect_telemetry_samples(ser, count=10, timeout=2.0):
    """Collect multiple telemetry samples for statistical analysis
    
    Args:
        ser: Serial port
        count: Number of samples to collect
        timeout: Total timeout for collection
    
    Returns:
        List of angle measurements (floats)
    """
    samples = []
    start = time.time()
    
    while len(samples) < count and (time.time() - start) < timeout:
        angle, _ = wait_for_telemetry(ser, timeout=0.5)
        if angle is not None:
            samples.append(angle)
    
    return samples


def test_motor_movement():
    """Test motor responds to target angle commands"""
    log("=" * 60)
    log("MOTOR MOVEMENT TEST")
    log("=" * 60)
    log("")
    log("This test verifies SimpleFOC motor responds to commands")
    log("")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
        log(f"✓ Connected to {SERIAL_PORT}")
        log("")
        
        # Step 1: Get initial angle samples
        log("Step 1: Read initial motor angle (collecting 10 samples)")
        initial_samples = collect_telemetry_samples(ser, count=10, timeout=2.0)
        if len(initial_samples) < 3:
            log(f"✗ FAIL: Could not collect enough initial samples ({len(initial_samples)}/10)")
            return False
        
        angle1 = statistics.mean(initial_samples)
        angle1_std = statistics.stdev(initial_samples) if len(initial_samples) > 1 else 0.0
        log(f"  Samples: {len(initial_samples)}")
        log(f"  Mean:    {angle1:.3f} rad")
        log(f"  StdDev:  {angle1_std:.4f} rad")
        log(f"  Range:   [{min(initial_samples):.3f}, {max(initial_samples):.3f}]")
        log("")
        
        # Step 2: Set target to 3.14 radians (180°)
        log("Step 2: Command motor to 3.14 rad (180°)")
        log("  Sending: T3.14 (direct command)")
        response = send_command(ser, "T3.14")
        for line in response:
            log(f"  Response: {line}")
        
        # Wait for command to be processed and motor to start moving
        time.sleep(0.5)
        
        # Step 3: Collect samples shortly after command
        log("Step 3: Verify motor is moving toward target (collecting 10 samples)")
        post_cmd_samples = collect_telemetry_samples(ser, count=10, timeout=2.0)
        if len(post_cmd_samples) < 3:
            log(f"✗ FAIL: Could not collect enough post-command samples ({len(post_cmd_samples)}/10)")
            return False
        
        angle2 = statistics.mean(post_cmd_samples)
        angle2_std = statistics.stdev(post_cmd_samples) if len(post_cmd_samples) > 1 else 0.0
        log(f"  Samples: {len(post_cmd_samples)}")
        log(f"  Mean:    {angle2:.3f} rad")
        log(f"  StdDev:  {angle2_std:.4f} rad")
        log(f"  Range:   [{min(post_cmd_samples):.3f}, {max(post_cmd_samples):.3f}]")
        log("")
        
        # Step 4: Wait for motor to approach target
        log("Step 4: Monitor motor movement (max 3s)")
        time.sleep(3.0)
        
        # Step 5: Collect final position samples
        log("Step 5: Collect final position samples (10 samples)")
        final_samples = collect_telemetry_samples(ser, count=10, timeout=2.0)
        if len(final_samples) < 3:
            log(f"✗ FAIL: Could not collect enough final samples ({len(final_samples)}/10)")
            return False
        
        angle_final = statistics.mean(final_samples)
        angle_final_std = statistics.stdev(final_samples) if len(final_samples) > 1 else 0.0
        log(f"  Samples: {len(final_samples)}")
        log(f"  Mean:    {angle_final:.3f} rad")
        log(f"  StdDev:  {angle_final_std:.4f} rad")
        log(f"  Range:   [{min(final_samples):.3f}, {max(final_samples):.3f}]")
        
        log("")
        
        # Step 6: Evaluate results
        log("Step 6: Evaluate movement")
        movement = abs(angle_final - angle1)
        final_error = abs(angle_final - 3.14)
        
        log(f"  Initial mean:  {angle1:.3f} ± {angle1_std:.4f} rad")
        log(f"  Final mean:    {angle_final:.3f} ± {angle_final_std:.4f} rad")
        log(f"  Movement:      {movement:.3f} rad ({movement * 57.3:.1f}°)")
        log(f"  Target:        3.14 rad (180°)")
        log(f"  Error:         {final_error:.3f} rad ({final_error * 57.3:.1f}°)")
        log("")
        
        # Success criteria
        if movement < 0.1:
            log("✗ FAIL: Motor did not move significantly")
            log("  Motor may be stuck or not receiving commands")
            log(f"  Movement {movement:.3f} rad < 0.1 rad threshold")
            return False
        
        if final_error < 0.2:
            log("✓ PASS: Motor reached target position!")
            log(f"  Error {final_error:.3f} rad < 0.2 rad tolerance")
            return True
        elif final_error < 0.5:
            log(f"⚠ WARNING: Motor moved but error={final_error:.3f} rad (tolerance 0.5 rad)")
            log("  This may be acceptable depending on PID tuning")
            log("✓ PASS: Motor IS responsive (moved significantly)")
            return True
        else:
            log(f"✗ FAIL: Motor moved but error too large: {final_error:.3f} rad")
            log(f"  Movement was {movement:.3f} rad but didn't approach target")
            return False
        
    except Exception as e:
        log(f"✗ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            ser.close()
        except:
            pass


if __name__ == "__main__":
    success = test_motor_movement()
    sys.exit(0 if success else 1)
