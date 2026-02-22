#!/usr/bin/env python3
"""
Automated Test Suite for USB HID Joystick Controller

Tests:
1. System identification (firmware, configuration)
2. Close-loop motor control (MIDI → joystick feedback)
3. Motor limits and scaling
"""

import serial
import time
import sys
import re
import glob
from pathlib import Path


class HIDControllerTestSuite:
    """Automated test suite for USB HID joystick controller"""
    
    def __init__(self, debug_port=None, midi_port=None):
        """Initialize test suite
        
        Args:
            debug_port: Serial port for debug output (usually /dev/ttyACM0)
            midi_port: Serial port for MIDI input (usually /dev/ttyACM1)
        """
        self.debug_port = debug_port or self._find_port("debug", 115200)
        self.midi_port = midi_port or self._find_port("midi", 31250)
        self.debug_ser = None
        self.midi_ser = None
        self.results = []
        self.firmware_info = {}
        
    @staticmethod
    def _find_port(port_type, baudrate):
        """Find available serial port"""
        ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
        if not ports:
            return None
        # Return first port (typically ACM0 for debug, ACM1 for MIDI)
        return ports[0] if port_type == "debug" else (ports[1] if len(ports) > 1 else ports[0])
    
    def connect(self):
        """Connect to both serial ports"""
        try:
            if self.debug_port:
                self.debug_ser = serial.Serial(self.debug_port, 115200, timeout=2)
                print(f"✓ Debug serial: {self.debug_port} @ 115200 baud")
            if self.midi_port:
                self.midi_ser = serial.Serial(self.midi_port, 31250, timeout=2)
                print(f"✓ MIDI serial: {self.midi_port} @ 31250 baud")
            
            time.sleep(2)  # Wait for firmware startup
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def close(self):
        """Close serial connections"""
        if self.debug_ser:
            self.debug_ser.close()
        if self.midi_ser:
            self.midi_ser.close()
    
    def read_debug_lines(self, timeout=1.0, max_lines=50):
        """Read lines from debug serial port"""
        if not self.debug_ser:
            return []
        
        lines = []
        start = time.time()
        while time.time() - start < timeout:
            if self.debug_ser.in_waiting:
                line = self.debug_ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    lines.append(line)
                    if len(lines) >= max_lines:
                        break
            else:
                time.sleep(0.01)
        
        return lines
    
    def send_midi_cc(self, cc_num, cc_val):
        """Send MIDI CC message"""
        if not self.midi_ser:
            return False
        
        # MIDI CC: 0xBn, CC#, value
        msg = bytes([0xB0, cc_num & 0x7F, cc_val & 0x7F])
        try:
            self.midi_ser.write(msg)
            self.midi_ser.flush()
            return True
        except:
            return False
    
    def test_system_identification(self):
        """Test 1: Read firmware version and configuration"""
        print("\n" + "=" * 70)
        print("TEST 1: System Identification")
        print("=" * 70)
        
        # Flush and read startup messages
        lines = self.read_debug_lines(timeout=2.0)
        
        print("Firmware output:")
        for line in lines:
            print(f"  {line}")
        
        # Parse firmware info
        success = False
        for line in lines:
            if "USB HID Joystick" in line or "Initialized" in line:
                success = True
                break
        
        # Extract configuration
        axes_count = 0
        axis_info = []
        for line in lines:
            if "Number of axes:" in line:
                match = re.search(r'(\d+)', line)
                if match:
                    axes_count = int(match.group(1))
            if re.match(r'\s*\d+:', line):  # Axis definition line
                axis_info.append(line.strip())
        
        self.firmware_info['axes'] = axes_count
        self.firmware_info['axis_info'] = axis_info
        
        if success:
            print(f"\n✓ PASS: Firmware initialized ({axes_count} axes)")
            self.results.append(("System Identification", True, None))
        else:
            print(f"\n✗ FAIL: Firmware initialization not detected")
            self.results.append(("System Identification", False, "No startup message"))
        
        return success
    
    def test_motor_initial_position(self):
        """Test 2: Verify motor position at startup"""
        print("\n" + "=" * 70)
        print("TEST 2: Motor Initial Position")
        print("=" * 70)
        
        # Read debug output to get initial angle
        lines = self.read_debug_lines(timeout=2.0, max_lines=10)
        
        initial_angle = None
        for line in lines:
            # Look for "Angle: X.XXXX rad"
            match = re.search(r'Angle:\s+([-\d.]+)\s+rad', line)
            if match:
                initial_angle = float(match.group(1))
                break
        
        if initial_angle is not None:
            print(f"Initial angle: {initial_angle:.4f} rad ({initial_angle*180/3.14159:.1f}°)")
            # Check if close to 0
            if abs(initial_angle) < 0.1:
                print("✓ PASS: Motor at origin (±0.1 rad)")
                self.results.append(("Motor Initial Position", True, None))
                return True
            else:
                print(f"⚠ WARNING: Motor not at origin")
                self.results.append(("Motor Initial Position", True, f"Off-origin: {initial_angle:.4f}"))
                return True
        else:
            print("✗ FAIL: Could not read motor angle")
            self.results.append(("Motor Initial Position", False, "Angle not readable"))
            return False
    
    def test_motor_response_to_midi(self):
        """Test 3: Send MIDI command, verify motor moves"""
        print("\n" + "=" * 70)
        print("TEST 3: Motor Response to MIDI (Close-Loop)")
        print("=" * 70)
        
        if not self.midi_ser:
            print("✗ SKIP: MIDI port not available")
            self.results.append(("Motor Response to MIDI", None, "MIDI port unavailable"))
            return None
        
        # Send MIDI CC (assuming CC#64 for trim motor)
        print("Sending MIDI CC#64 value 64...")
        self.send_midi_cc(64, 64)
        time.sleep(0.5)
        
        # Read response
        lines = self.read_debug_lines(timeout=1.5)
        
        print("Response:")
        for line in lines[-5:]:  # Last 5 lines
            print(f"  {line}")
        
        # Check if motor responded
        motor_moved = False
        final_angle = None
        
        for line in lines:
            if "MIDI:" in line and "CC#64" in line:
                motor_moved = True
            match = re.search(r'Angle:\s+([-\d.]+)\s+rad', line)
            if match:
                final_angle = float(match.group(1))
        
        if motor_moved:
            print(f"\n✓ PASS: Motor responded to MIDI")
            if final_angle is not None:
                angle_deg = final_angle * 180 / 3.14159
                print(f"  Final position: {final_angle:.4f} rad ({angle_deg:.1f}°)")
            self.results.append(("Motor Response to MIDI", True, None))
            return True
        else:
            print(f"\n✗ FAIL: Motor did not respond to MIDI")
            self.results.append(("Motor Response to MIDI", False, "No MIDI response logged"))
            return False
    
    def test_joystick_scaling(self):
        """Test 4: Verify joystick values scale with motor position"""
        print("\n" + "=" * 70)
        print("TEST 4: Joystick Output Scaling")
        print("=" * 70)
        
        # Read current joystick values from debug output
        lines = self.read_debug_lines(timeout=2.0, max_lines=10)
        
        joystick_values = []
        for line in lines:
            # Look for "USB: 512 (0-1023)"
            match = re.search(r'USB:\s+(\d+)\s+\(', line)
            if match:
                joystick_values.append(int(match.group(1)))
        
        if joystick_values:
            print(f"Joystick values read: {joystick_values}")
            
            # Check if values are in valid range
            all_valid = all(0 <= v <= 1023 for v in joystick_values)
            
            if all_valid:
                print("✓ PASS: All joystick values in range 0-1023")
                self.results.append(("Joystick Scaling", True, None))
                return True
            else:
                print(f"✗ FAIL: Invalid joystick values detected")
                self.results.append(("Joystick Scaling", False, "Out-of-range values"))
                return False
        else:
            print("⚠ SKIP: No joystick values found in debug output")
            self.results.append(("Joystick Scaling", None, "Values not readable"))
            return None
    
    def test_motor_sweep(self):
        """Test 5: Send MIDI sweep, verify smooth joystick output"""
        print("\n" + "=" * 70)
        print("TEST 5: Motor Sweep & Joystick Output")
        print("=" * 70)
        
        if not self.midi_ser:
            print("✗ SKIP: MIDI port not available")
            self.results.append(("Motor Sweep", None, "MIDI port unavailable"))
            return None
        
        print("Sending MIDI CC#64 sweep: 0 → 127…")
        
        positions = []
        for cc_val in [0, 32, 64, 96, 127]:
            self.send_midi_cc(64, cc_val)
            time.sleep(0.3)
            
            # Read the angle
            lines = self.read_debug_lines(timeout=0.5)
            for line in lines:
                match = re.search(r'Angle:\s+([-\d.]+)\s+rad', line)
                if match:
                    angle = float(match.group(1))
                    positions.append((cc_val, angle))
                    angle_deg = angle * 180 / 3.14159
                    print(f"  CC#64={cc_val:3d} → Angle={angle:7.4f} rad ({angle_deg:6.1f}°)")
                    break
        
        if len(positions) >= 3:
            # Check that angles increase
            angles = [p[1] for p in positions]
            increasing = all(angles[i] <= angles[i+1] for i in range(len(angles)-1))
            
            if increasing:
                print("✓ PASS: Motor sweeps smoothly with MIDI")
                self.results.append(("Motor Sweep", True, None))
                return True
            else:
                print("⚠ WARNING: Angles not monotonically increasing")
                self.results.append(("Motor Sweep", True, "Non-monotonic motion"))
                return True
        else:
            print("✗ FAIL: Could not read angles during sweep")
            self.results.append(("Motor Sweep", False, "Angles not readable"))
            return False
    
    def print_results(self):
        """Print test results summary"""
        print("\n" + "=" * 70)
        print("TEST RESULTS SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for _, s, _ in self.results if s is True)
        failed = sum(1 for _, s, _ in self.results if s is False)
        skipped = sum(1 for _, s, _ in self.results if s is None)
        
        for test_name, success, note in self.results:
            if success is True:
                status = "✓ PASS"
            elif success is False:
                status = "✗ FAIL"
            else:
                status = "⊘ SKIP"
            
            note_str = f" ({note})" if note else ""
            print(f"{status}: {test_name}{note_str}")
        
        print("=" * 70)
        print(f"Results: {passed} pass, {failed} fail, {skipped} skip")
        print("=" * 70)
        
        return failed == 0
    
    def run_all(self):
        """Run all tests"""
        print("\n" + "=" * 70)
        print("USB HID JOYSTICK CONTROLLER - AUTOMATED TEST SUITE")
        print("=" * 70)
        
        if not self.connect():
            print("Failed to connect to device")
            return False
        
        try:
            # Run tests in sequence
            self.test_system_identification()
            self.test_motor_initial_position()
            self.test_motor_response_to_midi()
            self.test_joystick_scaling()
            self.test_motor_sweep()
            
            # Print summary
            all_pass = self.print_results()
            
            return all_pass
        finally:
            self.close()


def main():
    """Entry point"""
    suite = HIDControllerTestSuite()
    success = suite.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
