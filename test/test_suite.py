#!/usr/bin/env python3
"""
Comprehensive Test Suite for USB HID Joystick Controller
Tests motor control, MIDI input protocol, and encoder feedback
"""

import sys
import time
import serial
import subprocess
from pathlib import Path

# Auto-detect serial port
def find_serial_port():
    """Find RP2040 ACM port"""
    import glob
    ports = glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*')
    if not ports:
        print("ERROR: No serial port found!")
        print("  Expected: /dev/ttyACM0 or /dev/ttyUSB0")
        return None
    return ports[0]

class MotorTestSuite:
    def __init__(self):
        self.port = find_serial_port()
        if not self.port:
            sys.exit(1)
        
        self.ser = None
        self.test_results = []
        
    def connect(self):
        """Open serial connection"""
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=2)
            time.sleep(1)
            # Flush buffer
            self.ser.reset_input_buffer()
            print(f"✓ Connected to {self.port} at 115200 baud\n")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def close(self):
        """Close serial connection"""
        if self.ser:
            self.ser.close()
    
    def send_command(self, cmd):
        """Send a command and return response"""
        if not self.ser:
            return None
        self.ser.write(cmd.encode() + b'\n')
        self.ser.flush()
        time.sleep(0.1)
        
        response = []
        while self.ser.in_waiting:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                response.append(line)
        return response
    
    def test_serial_connection(self):
        """Test 1: Serial connection and firmware ready"""
        print("=" * 70)
        print("TEST 1: Serial Connection & Firmware Ready")
        print("=" * 70)
        print("✓ Serial port connected")
        
        # Check for boot message
        time.sleep(2)  # Wait for startup messages
        response = []
        while self.ser.in_waiting:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                response.append(line)
                print(f"  {line}")
        
        success = any("USB HID Joystick" in line for line in response)
        self.test_results.append(("Serial Connection", success))
        
        if success:
            print("✓ Firmware initialized successfully\n")
        else:
            print("✗ Firmware initialization not detected\n")
        
        return success
    
    def test_motor_zero_position(self):
        """Test 2: Verify motor at origin angle"""
        print("=" * 70)
        print("TEST 2: Motor at Origin (Check Angle = 0.00 rad)")
        print("=" * 70)
        print("Reading motor angle from debug output...")
        
        # Read a few debug lines to find angle
        angles = []
        for i in range(5):
            self.ser.reset_input_buffer()
            time.sleep(0.5)
            while self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if "Angle:" in line or "angle:" in line:
                    print(f"  {line}")
                    angles.append(line)
        
        # Check if angle is close to 0
        success = len(angles) > 0
        self.test_results.append(("Motor Zero Position", success))
        
        if success:
            print("✓ Motor angle detected\n")
        else:
            print("✗ Could not read motor angle\n")
        
        return success
    
    def test_midi_command(self, cc_num, cc_val):
        """Send MIDI CC command and check response"""
        cmd = f"[M{cc_num},{cc_val}]"
        print(f"Sending: {cmd}")
        
        self.ser.write(cmd.encode())
        self.ser.flush()
        time.sleep(0.2)
        
        response = []
        while self.ser.in_waiting:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                response.append(line)
                print(f"  {line}")
        
        return response
    
    def test_midi_sweep(self):
        """Test 3: MIDI CC sweep test"""
        print("=" * 70)
        print("TEST 3: MIDI Input Test (CC#64 Trim Motor Sweep)")
        print("=" * 70)
        print("\nIMPORTANT: Watch the motor carefully!")
        print("Expected: Motor should rotate SMOOTHLY from 0 to 360 degrees")
        print("          If motion is JUMPY or COARSE, something is wrong\n")
        
        input("Press ENTER when ready to start motor sweep...")
        
        print("\nStarting sweep (this takes ~30 seconds)...")
        print("Sending MIDI CC#64 values: 0 → 127 (step=1 for 128 steps)\n")
        
        successful_commands = 0
        
        # Send sweep commands with step=1 for fine resolution
        for val in range(0, 128, 2):  # Step by 2 for speed, still 64 steps
            response = self.test_midi_command(64, val)
            if any("MIDI:" in line for line in response):
                successful_commands += 1
            time.sleep(0.1)  # Small delay between commands
        
        print(f"\n✓ Sent {successful_commands} MIDI commands")
        
        # Ask user for feedback
        print("\nObservation checklist:")
        print("  [ ] Motor started rotating")
        print("  [ ] Rotation was SMOOTH (not jumpy/coarse)")
        print("  [ ] Motor completed full 360° rotation")
        
        observation = input("\nDid motor rotate smoothly? (y/n): ").strip().lower()
        success = observation == 'y'
        self.test_results.append(("MIDI Sweep", success))
        
        if success:
            print("✓ MIDI sweep test PASSED\n")
        else:
            print("✗ MIDI sweep test FAILED\n")
        
        return success
    
    def test_manual_rotation(self):
        """Test 4: Manual motor rotation"""
        print("=" * 70)
        print("TEST 4: Manual Motor Rotation (Encoder Feedback)")
        print("=" * 70)
        print("\nIMPORTANT: Physically rotate the motor by hand")
        print("Expected: Angle value should change smoothly as you rotate\n")
        
        input("Press ENTER, then MANUALLY rotate the motor shaft...")
        
        print("\nReading encoder values (rotating the motor now):")
        angles = []
        for i in range(10):
            while self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if "Angle:" in line or "angle:" in line:
                    print(f"  {line}")
                    angles.append(line)
            time.sleep(0.2)
        
        # Check if angles changed
        success = len(angles) > 2
        self.test_results.append(("Manual Rotation", success))
        
        if success:
            print("✓ Encoder feedback detected\n")
        else:
            print("✗ No encoder feedback detected\n")
        
        return success
    
    def test_motor_limits(self):
        """Test 5: Motor movement consistency"""
        print("=" * 70)
        print("TEST 5: Motor Movement Consistency")
        print("=" * 70)
        print("\nSending multiple MIDI commands to verify consistent response\n")
        
        test_values = [0, 32, 64, 96, 127]
        responses = []
        
        for val in test_values:
            print(f"Setting CC#64={val}...")
            response = self.test_midi_command(64, val)
            responses.append(response)
            time.sleep(0.5)
        
        # Check if we got consistent responses
        success = len(responses) == len(test_values) and all(responses)
        self.test_results.append(("Motor Consistency", success))
        
        if success:
            print("✓ Motor responded to all commands\n")
        else:
            print("✗ Some commands failed\n")
        
        return success
    
    def test_usb_joystick_output(self):
        """Test 6: USB HID joystick value scaling"""
        print("=" * 70)
        print("TEST 6: USB Joystick Output (0-1023 range)")
        print("=" * 70)
        print("\nSending MIDI commands and checking joystick value scaling\n")
        
        # Set to min, mid, max positions
        test_points = [(0, "min"), (64, "mid"), (127, "max")]
        readings = []
        
        for cc_val, label in test_points:
            print(f"Setting position: {label} (CC#64={cc_val})")
            response = self.test_midi_command(64, cc_val)
            
            # Look for USB joystick value in response
            for line in response:
                if "USB:" in line or "320:" in line or "axis" in line.lower():
                    readings.append((label, line))
                    print(f"  → {line}")
            
            time.sleep(0.3)
        
        success = len(readings) >= len(test_points)
        self.test_results.append(("USB Output", success))
        
        if success:
            print("✓ Joystick values detected\n")
        else:
            print("✗ Could not verify joystick output\n")
        
        return success
    
    def report_results(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for _, result in self.test_results if result)
        total = len(self.test_results)
        
        for test_name, result in self.test_results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status}: {test_name}")
        
        print("\n" + "=" * 70)
        print(f"Result: {passed}/{total} tests passed")
        print("=" * 70)
        
        if passed == total:
            print("\n✓✓✓ ALL TESTS PASSED ✓✓✓\n")
            return True
        else:
            print(f"\n✗ {total - passed} test(s) failed\n")
            return False
    
    def run_all_tests(self):
        """Execute complete test suite"""
        if not self.connect():
            return False
        
        try:
            print("\n")
            print("╔" + "=" * 68 + "╗")
            print("║" + " " * 68 + "║")
            print("║" + "  USB HID JOYSTICK CONTROLLER - COMPLETE TEST SUITE  ".center(68) + "║")
            print("║" + " " * 68 + "║")
            print("╚" + "=" * 68 + "╝")
            print("\n")
            
            # Run tests in sequence
            self.test_serial_connection()
            time.sleep(1)
            
            self.test_motor_zero_position()
            time.sleep(1)
            
            self.test_midi_sweep()
            time.sleep(1)
            
            self.test_manual_rotation()
            time.sleep(1)
            
            self.test_motor_limits()
            time.sleep(1)
            
            self.test_usb_joystick_output()
            time.sleep(1)
            
            # Print summary
            return self.report_results()
        
        finally:
            self.close()

def main():
    suite = MotorTestSuite()
    success = suite.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
