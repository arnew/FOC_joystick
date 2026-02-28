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
        
        # Step 1: Get initial angle
        log("Step 1: Read initial motor angle")
        angle1, telem1 = wait_for_telemetry(ser)
        if angle1 is None:
            log("✗ FAIL: Could not read initial angle")
            return False
        log(f"  Initial: {telem1}")
        log(f"  Angle: {angle1:.3f} rad")
        log("")
        
        # Step 2: Set target to 3.14 radians (180°)
        log("Step 2: Command motor to 3.14 rad (180°)")
        log("  Sending: T3.14 (direct command)")
        response = send_command(ser, "T3.14")
        for line in response:
            log(f"  Response: {line}")
        
        # Wait a moment for motor to start moving
        time.sleep(1.0)
        
        # Step 3: Check angle after command
        log("Step 3: Verify motor is moving toward target")
        angle2, telem2 = wait_for_telemetry(ser)
        if angle2 is None:
            log("✗ FAIL: Could not read angle after command")
            return False
        log(f"  After cmd: {telem2}")
        log(f"  Angle: {angle2:.3f} rad")
        log("")
        
        # Step 4: Wait for motor to reach target
        log("Step 4: Wait for motor to reach target (max 5s)")
        attempts = 0
        reached = False
        last_measurement = angle2
        
        for i in range(50):  # 5 seconds max
            angle, telem = wait_for_telemetry(ser, timeout=0.5)
            if angle is not None:
                attempts += 1
                
                # Check if close to target (within 0.2 rad ≈ 11°)
                error = abs(angle - 3.14)
                if error < 0.2:
                    log(f"  [{attempts}] {telem} - ✓ Target reached!")
                    reached = True
                    last_measurement = angle
                    break
                
                # Log progress every 5 attempts
                if attempts % 5 == 0:
                    log(f"  [{attempts}] A={angle:.3f} (error={error:.3f})")
                
                last_measurement = angle
        
        log("")
        
        # Step 5: Evaluate results
        log("Step 5: Evaluate movement")
        movement = abs(last_measurement - angle1)
        log(f"  Initial angle: {angle1:.3f} rad")
        log(f"  Final angle:   {last_measurement:.3f} rad")
        log(f"  Movement:      {movement:.3f} rad ({movement * 57.3:.1f}°)")
        log(f"  Target:        3.14 rad (180°)")
        log("")
        
        # Success criteria
        if movement < 0.1:
            log("✗ FAIL: Motor did not move significantly")
            log("  Motor may be stuck or not receiving commands")
            return False
        
        if reached:
            log("✓ PASS: Motor reached target position!")
            return True
        else:
            final_error = abs(last_measurement - 3.14)
            if final_error < 0.5:  # Within 0.5 rad ≈ 29°
                log(f"⚠ WARNING: Motor moved but didn't reach target (error={final_error:.3f})")
                log("  This may be acceptable depending on PID tuning")
                log("✓ PASS: Motor IS responsive (moved significantly)")
                return True
            else:
                log(f"✗ FAIL: Motor moved but far from target (error={final_error:.3f})")
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
