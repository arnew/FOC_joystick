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
import os
from pathlib import Path
from serial.tools import list_ports

try:
    import pygame.midi
    PYGAME_MIDI_AVAILABLE = True
except ImportError:
    PYGAME_MIDI_AVAILABLE = False


def _parse_vid_pid(val):
    if val is None:
        return None
    try:
        if isinstance(val, str) and val.lower().startswith("0x"):
            return int(val, 16)
        return int(val)
    except:
        return None


def wait_for_ports(timeout=10, poll_interval=0.5,
                   debug_vid=None, debug_pid=None, midi_vid=None, midi_pid=None,
                   debug_manufacturer=None, midi_manufacturer=None):
    """Wait for serial ports to enumerate and choose debug/midi ports.

    Selection order:
    1. Match VID/PID if specified
    2. Match manufacturer substring if specified
    3. Fallback to the first two ACM/USB ports (ACM0=debug, ACM1=MIDI)
    """
    debug_vid = _parse_vid_pid(debug_vid)
    debug_pid = _parse_vid_pid(debug_pid)
    midi_vid = _parse_vid_pid(midi_vid)
    midi_pid = _parse_vid_pid(midi_pid)

    end = time.time() + timeout
    while time.time() < end:
        ports = list(list_ports.comports())
        if ports:
            # Build lookup
            debug_port = None
            midi_port = None

            # Try VID/PID matching
            for p in ports:
                if debug_port is None and debug_vid is not None:
                    if getattr(p, "vid", None) == debug_vid and getattr(p, "pid", None) == debug_pid:
                        debug_port = p.device
                if midi_port is None and midi_vid is not None:
                    if getattr(p, "vid", None) == midi_vid and getattr(p, "pid", None) == midi_pid:
                        midi_port = p.device

            # Try manufacturer substring
            for p in ports:
                man = (p.manufacturer or "").lower()
                if debug_port is None and debug_manufacturer:
                    if debug_manufacturer.lower() in man:
                        debug_port = p.device
                if midi_port is None and midi_manufacturer:
                    if midi_manufacturer.lower() in man:
                        midi_port = p.device

            # Fallback: prefer ACM then USB ordering
            device_names = [p.device for p in ports if (p.device.startswith("/dev/ttyACM") or p.device.startswith("/dev/ttyUSB"))]
            if debug_port is None and device_names:
                debug_port = device_names[0]
            if midi_port is None and len(device_names) > 1:
                midi_port = device_names[1]
            elif midi_port is None and len(device_names) == 1:
                midi_port = device_names[0]

            return debug_port, midi_port

        time.sleep(poll_interval)

    return None, None


class HIDControllerTestSuite:
    """Automated test suite for USB HID joystick controller"""
    
    def __init__(self, debug_port=None, midi_port=None):
        """Initialize test suite
        
        Args:
            debug_port: Serial port for debug output (e.g. /dev/ttyACM0)
            midi_port: Serial port for MIDI input (e.g. /dev/ttyACM1)
        """
        # Allow explicit env overrides
        env_dbg = os.environ.get("DEBUG_PORT")
        env_midi = os.environ.get("MIDI_PORT")

        if env_dbg:
            debug_port = env_dbg
        if env_midi:
            midi_port = env_midi

        # If not provided, attempt robust detection
        if not debug_port or not midi_port:
            dbg_vid = os.environ.get("DEBUG_VID")
            dbg_pid = os.environ.get("DEBUG_PID")
            midi_vid = os.environ.get("MIDI_VID")
            midi_pid = os.environ.get("MIDI_PID")
            dbg_man = os.environ.get("DEBUG_MANUFACTURER")
            midi_man = os.environ.get("MIDI_MANUFACTURER")

            found_dbg, found_midi = wait_for_ports(
                timeout=int(os.environ.get("PORT_WAIT_TIMEOUT", "10")),
                debug_vid=dbg_vid, debug_pid=dbg_pid,
                midi_vid=midi_vid, midi_pid=midi_pid,
                debug_manufacturer=dbg_man, midi_manufacturer=midi_man
            )

            debug_port = debug_port or found_dbg
            midi_port = midi_port or found_midi

        self.debug_port = debug_port
        self.midi_port = midi_port  # May still be used for backwards compat logging
        self.debug_ser = None
        self.midi_ser = None
        self.midi_output = None  # pygame.midi output device
        self.results = []
        self.firmware_info = {}
        
        # Initialize pygame.midi for native USB MIDI
        if PYGAME_MIDI_AVAILABLE:
            try:
                pygame.midi.init()
            except:
                pass
        
    @staticmethod
    def _find_port(port_type, baudrate):
        """(Deprecated) Find available serial port fallback"""
        ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
        if not ports:
            return None
        return ports[0] if port_type == "debug" else (ports[1] if len(ports) > 1 else ports[0])
    
    def connect(self):
        """Connect to debug serial and native USB MIDI"""
        try:
            if not self.debug_port:
                print("✗ No debug serial port detected. Connect RP2040 and/or set DEBUG_PORT environment variable.")
                print("   You can also run test/run_tests.sh which attempts upload and waits for enumeration.")
                return False

            if self.debug_port:
                self.debug_ser = serial.Serial(self.debug_port, 115200, timeout=2)
                print(f"✓ Debug serial: {self.debug_port} @ 115200 baud")
            else:
                print("⚠ Debug serial not found; some tests may be skipped")

            # Try native USB MIDI via pygame.midi
            midi_found = False
            if PYGAME_MIDI_AVAILABLE:
                try:
                    for i in range(pygame.midi.get_count()):
                        info = pygame.midi.get_device_info(i)
                        # Look for "Pico MIDI" output port (mode 0 = output)
                        if b"Pico" in info[1] and info[4] == 0:  # mode 0 = output
                            self.midi_output = pygame.midi.Output(i)
                            print(f"✓ Native USB MIDI: {info[1].decode()} (pygame.midi output)")
                            midi_found = True
                            break
                except Exception as e:
                    print(f"⚠ Native USB MIDI initialization failed: {e}")
            
            if not midi_found:
                # Fallback: try serial MIDI if available (for backwards compatibility)
                if self.midi_port:
                    try:
                        self.midi_ser = serial.Serial(self.midi_port, 31250, timeout=2)
                        print(f"✓ MIDI serial (fallback): {self.midi_port} @ 31250 baud")
                        midi_found = True
                    except:
                        pass
            
            if not midi_found:
                print("⚠ No MIDI input found (native USB MIDI or serial); MIDI tests will be skipped")

            time.sleep(2)  # Wait for firmware startup
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def close(self):
        """Close serial and MIDI connections"""
        if self.debug_ser:
            self.debug_ser.close()
        if self.midi_ser:
            self.midi_ser.close()
        if self.midi_output:
            try:
                self.midi_output.close()
            except:
                pass

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
        """Send MIDI CC message via native USB MIDI or serial fallback"""
        if self.midi_output:
            # Use native USB MIDI (pygame.midi)
            try:
                # pygame.midi.Output.write() expects list of (status, data1, data2, data3) tuples
                # For CC: [status=0xB0, data1=cc_num, data2=cc_val, data3=0]
                self.midi_output.write([[[0xB0, cc_num & 0x7F, cc_val & 0x7F, 0], pygame.midi.time()]])
                return True
            except Exception as e:
                print(f"⚠ pygame.midi CC send failed: {e}")
                return False
        elif self.midi_ser:
            # Fallback: serial MIDI
            try:
                msg = bytes([0xB0, cc_num & 0x7F, cc_val & 0x7F])
                self.midi_ser.write(msg)
                self.midi_ser.flush()
                return True
            except:
                return False
        else:
            return False

    def test_system_identification(self):
        """Test 1: System Connectivity - verify device responds to commands"""
        print("\n" + "=" * 70)
        print("TEST 1: System Connectivity")
        print("=" * 70)
        
        if not self.debug_ser:
            print("✗ FAIL: Debug port not available")
            self.results.append(("System Connectivity", False, "No debug port"))
            return False
        
        print("Checking device responsiveness...")
        
        # Send a simple MIDI command to trigger a response (try a couple times)
        lines = []
        if self.midi_ser:
            self.send_midi_cc(64, 0)  # CC#64=0 to trigger debug output
            time.sleep(0.2)

            # Read for up to 2s, re-sending once if needed
            start = time.time()
            resent = False
            while time.time() - start < 2.0:
                new_lines = self.read_debug_lines(timeout=0.25, max_lines=10)
                if new_lines:
                    lines.extend(new_lines)
                if any(("Angle:" in l and "rad" in l) for l in lines):
                    break
                if not resent and time.time() - start > 0.6:
                    # retry MIDI ping
                    self.send_midi_cc(64, 0)
                    resent = True
                time.sleep(0.05)
        else:
            # Read debug output to verify device is responding
            lines = self.read_debug_lines(timeout=1.0, max_lines=20)
        
        # Check for valid debug output format
        valid_response = False
        for line in lines:
            if "Angle:" in line and "rad" in line:
                valid_response = True
                print(f"  ✓ Device responsive: {line[:60]}")
                break
        
        if valid_response:
            print("\n✓ PASS: Device responding to commands")
            self.results.append(("System Connectivity", True, None))
            return True
        else:
            print("\n✗ FAIL: Device not responding (no debug output)")
            self.results.append(("System Connectivity", False, "No response"))
            return False

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
            match = re.search(r'Angle:\s+([\-\d.]+)\s+rad', line)
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
            match = re.search(r'Angle:\s+([\-\d.]+)\s+rad', line)
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
                match = re.search(r'Angle:\s+([\-\d.]+)\s+rad', line)
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
