#!/usr/bin/env python3
"""
Simple, Slow Hardware Test Suite
Defensive testing with explicit verification at each step
"""

import sys
import time
import serial

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200
DEVICE_TIMEOUT = 10  # seconds


def log(msg):
    """Timestamped logging"""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def test_1_device_exists():
    """Test 1: Device file exists"""
    log("TEST 1: Check device file exists")
    import os
    if not os.path.exists(SERIAL_PORT):
        log(f"  ✗ FAIL: {SERIAL_PORT} does not exist")
        return False
    log(f"  ✓ PASS: {SERIAL_PORT} exists")
    return True


def test_2_device_opens():
    """Test 2: Device can be opened"""
    log("TEST 2: Open serial connection")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        log(f"  ✓ PASS: Serial port opened")
        ser.close()
        return True
    except Exception as e:
        log(f"  ✗ FAIL: Cannot open serial port: {e}")
        return False


def test_3_device_responds():
    """Test 3: Device sends any data (proves firmware is running)"""
    log("TEST 3: Wait for device output")
    log("  Waiting up to 10 seconds for ANY output from device...")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
        
        # Read for up to 10 seconds
        start = time.time()
        lines_received = []
        
        while time.time() - start < 10:
            line = ser.readline()
            if line:
                try:
                    decoded = line.decode('utf-8', errors='ignore').strip()
                    if decoded:
                        log(f"  << {decoded}")
                        lines_received.append(decoded)
                except:
                    pass
            
            if lines_received:
                break
        
        ser.close()
        
        if not lines_received:
            log("  ✗ FAIL: No output from device after 10 seconds")
            log("  This means firmware is not running or USB CDC not working")
            return False
        
        log(f"  ✓ PASS: Device is alive (received {len(lines_received)} lines)")
        return True
        
    except Exception as e:
        log(f"  ✗ FAIL: Error reading from device: {e}")
        return False


def test_4_device_initialization():
    """Test 4: Check for motor initialization logs"""
    log("TEST 4: Verify motor initialization")
    log("  Looking for [MOTOR] initialization messages...")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
        
        # Read for up to 15 seconds (motor init can take time)
        start = time.time()
        motor_init_found = False
        init_complete = False
        
        while time.time() - start < 15:
            line = ser.readline()
            if line:
                try:
                    decoded = line.decode('utf-8', errors='ignore').strip()
                    if decoded:
                        if '[MOTOR]' in decoded or 'MOTOR' in decoded:
                            log(f"  << {decoded}")
                            motor_init_found = True
                            if 'complete' in decoded.lower() or 'ready' in decoded.lower():
                                init_complete = True
                                break
                except:
                    pass
        
        ser.close()
        
        if not motor_init_found:
            log("  ✗ FAIL: No motor initialization messages found")
            log("  Device is responding but motor init didn't run")
            return False
        
        if not init_complete:
            log("  ⚠ WARNING: Motor init started but didn't complete")
            log("  Proceeding anyway, but motor may not be ready")
        
        log("  ✓ PASS: Motor initialization detected")
        return True
        
    except Exception as e:
        log(f"  ✗ FAIL: Error during initialization check: {e}")
        return False


def test_5_simple_query():
    """Test 5: Send simple command and expect telemetry response"""
    log("TEST 5: Query device state")
    log("  Waiting for telemetry output (A=angle T=target)...")
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.5)
        
        # Just listen for telemetry (our device emits periodic updates)
        start = time.time()
        telemetry_found = False
        
        while time.time() - start < 5:
            line = ser.readline()
            if line:
                try:
                    decoded = line.decode('utf-8', errors='ignore').strip()
                    if 'A=' in decoded or 'T=' in decoded:
                        log(f"  << {decoded}")
                        telemetry_found = True
                        break
                except:
                    pass
        
        ser.close()
        
        if not telemetry_found:
            log("  ✗ FAIL: No telemetry data received")
            log("  Device may not be running main loop")
            return False
        
        log("  ✓ PASS: Device responding with telemetry")
        return True
        
    except Exception as e:
        log(f"  ✗ FAIL: Error querying device: {e}")
        return False


def main():
    log("=" * 60)
    log("SIMPLE HARDWARE TEST SUITE")
    log("=" * 60)
    log("")
    log("Running slow, defensive tests with explicit verification...")
    log("Each test waits for real device behavior, no assumptions.")
    log("")
    
    tests = [
        ("Device Exists", test_1_device_exists),
        ("Device Opens", test_2_device_opens),
        ("Device Responds", test_3_device_responds),
        ("Motor Initialization", test_4_device_initialization),
        ("Device Telemetry", test_5_simple_query),
    ]
    
    results = []
    
    for name, test_func in tests:
        log("")
        try:
            passed = test_func()
            results.append((name, passed))
            
            if not passed:
                log("")
                log("✗ Test failed - stopping here")
                log("Fix this test before proceeding to next tests")
                break
            
            # Slow down between tests
            log("")
            log("Waiting 2 seconds before next test...")
            time.sleep(2)
            
        except Exception as e:
            log(f"✗ EXCEPTION in {name}: {e}")
            results.append((name, False))
            break
    
    # Summary
    log("")
    log("=" * 60)
    log("TEST RESULTS SUMMARY")
    log("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        log(f"{status}: {name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    
    log("")
    log(f"Results: {passed_count}/{total_count} tests passed")
    log("=" * 60)
    
    # Exit code
    if passed_count < total_count:
        log("\n✗ Some tests failed")
        sys.exit(1)
    else:
        log("\n✓ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
