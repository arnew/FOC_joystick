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
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from serial.tools import list_ports

# Import high-speed monitor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    
    def __init__(self, debug_port=None, midi_port=None, enable_monitor=False):
        """Initialize test suite
        
        Args:
            debug_port: Serial port for debug output (e.g. /dev/ttyACM0)
            midi_port: Serial port for MIDI input (e.g. /dev/ttyACM1)
            enable_monitor: Enable optional high-speed monitor test (TEST 5B)
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
        self.enable_monitor = enable_monitor  # Enable optional high-speed monitor test
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
                    print(f"  Scanning for USB MIDI devices ({pygame.midi.get_count()} total):")
                    for i in range(pygame.midi.get_count()):
                        info = pygame.midi.get_device_info(i)
                        # info = (interf, name, input, output, opened)
                        # name = device name bytes, output (info[3]) = 1 if device can receive
                        device_name = info[1].decode('utf-8', errors='ignore')
                        is_output = info[3] == 1
                        print(f"    [{i}] {device_name} {'(OUT)' if is_output else '(IN)'}")
                        
                        # Look for RP2040 MIDI output port (to send to device)
                        # Check for common RP2040/Pico MIDI names
                        # Exclude ALSA virtual ports ("Midi Through")
                        device_lower = device_name.lower()
                        if is_output and 'through' not in device_lower:
                            # Prefer specific keywords first, fallback to generic 'usb'
                            if any(keyword in device_lower for keyword in ['pico', 'rp2040', 'tinyusb']):
                                self.midi_output = pygame.midi.Output(i)
                                print(f"✓ Native USB MIDI: {device_name} (pygame.midi)")
                                midi_found = True
                                break
                            elif 'usb' in device_lower and 'midi' in device_lower:
                                # Accept generic "USB MIDI" but not "Midi Through"
                                self.midi_output = pygame.midi.Output(i)
                                print(f"✓ Native USB MIDI: {device_name} (pygame.midi)")
                                midi_found = True
                                break
                except Exception as e:
                    print(f"⚠ Native USB MIDI scan failed: {e}")
            
            if not midi_found:
                # Fallback: try serial MIDI if available (for backwards compatibility)
                if self.midi_port:
                    try:
                        self.midi_ser = serial.Serial(self.midi_port, 31250, timeout=2)
                        print(f"⚠ MIDI serial (fallback): {self.midi_port} @ 31250 baud")
                        print(f"  WARNING: Firmware may not handle serial MIDI - USB MIDI preferred!")
                    except Exception as e:
                        print(f"✗ MIDI serial fallback failed: {e}")
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

    @staticmethod
    def _extract_last_angle(lines):
        """Extract last angle from debug lines (old or compact format)."""
        angle = None
        for line in lines:
            match = re.search(r'Angle:\s+([\-\d.]+)\s+rad', line)
            if not match:
                match = re.search(r'A=([\-\d.]+)', line)
            if match:
                angle = float(match.group(1))
        return angle

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
        
        # Send a MIDI command to trigger motor response and debug output
        lines = []
        midi_sent = False
        if self.midi_output:
            # Use native USB MIDI to trigger motor response
            try:
                self.send_midi_cc(64, 0)  # CC#64=0 to trigger debug output
                midi_sent = True
            except:
                pass
        
        if midi_sent or self.midi_ser:
            # With MIDI, we can trigger response
            # Wait for next debug output (1 Hz = 1 second interval)
            time.sleep(1.2)
            # Read for up to 3s, re-sending once if needed
            start = time.time()
            resent = False
            while time.time() - start < 3.0:
                new_lines = self.read_debug_lines(timeout=1.5, max_lines=10)
                if new_lines:
                    lines.extend(new_lines)
                if any(("Angle:" in l and "rad" in l) for l in lines):
                    break
                if not resent and time.time() - start > 0.6:
                    # retry MIDI ping
                    if self.midi_output:
                        try:
                            self.send_midi_cc(64, 0)
                        except:
                            pass
                    resent = True
                time.sleep(0.1)
        else:
            # No MIDI, wait for natural 1Hz debug output
            time.sleep(1.2)  # Wait for next message after connection
            lines = self.read_debug_lines(timeout=2.5, max_lines=20)
        
        # Check for valid debug output format
        valid_response = False
        for line in lines:
            # Support both old format ("Angle: X rad") and new format ("A=X.XX T=Y.YY")
            if ("Angle:" in line and "rad" in line) or re.search(r'A=[\-\d.]+', line):
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
            # Support both old format ("Angle: X rad") and new format ("A=X.XX")
            match = re.search(r'Angle:\s+([\-\d.]+)\s+rad', line)
            if not match:
                match = re.search(r'A=([\-\d.]+)', line)  # New compact format
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
        
        if not self.midi_output and not self.midi_ser:
            print("✗ SKIP: MIDI port not available")
            self.results.append(("Motor Response to MIDI", None, "MIDI port unavailable"))
            return None
        
        # Capture baseline angle first (wait for debug output at 1 Hz)
        baseline_lines = self.read_debug_lines(timeout=1.5, max_lines=20)
        baseline_angle = self._extract_last_angle(baseline_lines)

        # Send MIDI CC (use a non-center value to force noticeable motion)
        print("Sending MIDI CC#64 value 127...")
        self.send_midi_cc(64, 127)
        # Wait for next debug output cycle (1 Hz = 1 second + margin)
        time.sleep(1.5)
        
        # Read response
        lines = self.read_debug_lines(timeout=2.0)
        
        print("Response:")
        for line in lines[-5:]:  # Last 5 lines
            print(f"  {line}")
        
        # Check if motor responded via log line and/or measured angle delta
        motor_moved = False
        final_angle = self._extract_last_angle(lines)
        
        for line in lines:
            if "MIDI:" in line and "CC#64" in line:
                motor_moved = True
        if baseline_angle is not None and final_angle is not None:
            delta = abs(final_angle - baseline_angle)
            if delta >= 0.02:
                motor_moved = True
        
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
        """Test 5: Send MIDI sweep, verify meaningful motion across command range"""
        print("\n" + "=" * 70)
        print("TEST 5: Motor Sweep & Joystick Output")
        print("=" * 70)
        
        if not self.midi_output and not self.midi_ser:
            print("✗ SKIP: MIDI port not available")
            self.results.append(("Motor Sweep", None, "MIDI port unavailable"))
            return None
        
        print("Sending MIDI CC#64 sweep in limited range (test compatibility)…")
        
        positions = []
        # Test limited range (0-64) to avoid wrapping issues with endless motors
        # This maps to 0-180° range, testable for both motor types
        test_values = [0, 16, 32, 48, 64]
        
        for cc_val in test_values:
            self.send_midi_cc(64, cc_val)
            # Wait for debug output (1 Hz rate) plus motor settle time
            time.sleep(1.5)
            
            # Read the angle (support both old and new format)
            lines = self.read_debug_lines(timeout=2.0)
            angle_found = False
            for line in lines:
                match = re.search(r'Angle:\s+([\-\d.]+)\s+rad', line)
                if not match:
                    match = re.search(r'A=([\-\d.]+)', line)  # New compact format
                if match:
                    angle = float(match.group(1))
                    positions.append((cc_val, angle))
                    angle_deg = angle * 180 / 3.14159
                    print(f"  CC#64={cc_val:3d} → Angle={angle:7.4f} rad ({angle_deg:6.1f}°)")
                    angle_found = True
                    break
            
            if not angle_found:
                print(f"  CC#64={cc_val:3d} → No angle reading")
                # Try to read MIDI debug to see if command was received
                for line in lines:
                    if 'MIDI' in line:
                        print(f"    Debug: {line.strip()}")
        
        if len(positions) < 3:
            print("✗ FAIL: Could not read sufficient angles during sweep")
            self.results.append(("Motor Sweep", False, "Angles not readable"))
            return False
        
        # Validate that motor tracks different MIDI commands to distinct positions
        angles = [p[1] for p in positions]
        excursion = max(angles) - min(angles)
        
        # Check 1: Minimum excursion (motor must actually move)
        if excursion < 0.06:
            print("✗ FAIL: Sweep response too weak")
            print(f"  Excursion: {excursion:.4f} rad (need >= 0.06)")
            self.results.append(("Motor Sweep", False, "Insufficient excursion"))
            return False
        
        # Check 2: Verify position changes between commands (not stuck at one point)
        unique_positions = len(set(round(a, 3) for a in angles))  # 1mm resolution
        if unique_positions < 3:
            print("✗ FAIL: Motor not responding to different MIDI values")
            print(f"  Only {unique_positions} distinct positions detected")
            print(f"  Angles: {angles}")
            self.results.append(("Motor Sweep", False, "Motor not tracking commands"))
            return False
        
        # Check 3: Verify positions correlate with MIDI values (monotonic trend)
        # Sort by MIDI value and check angle progression
        sorted_pos = sorted(positions, key=lambda x: x[0])
        sorted_angles = [p[1] for p in sorted_pos]
        
        # Count direction changes (should be mostly monotonic)
        direction_changes = 0
        for i in range(len(sorted_angles) - 1):
            if i > 0:
                prev_dir = sorted_angles[i] - sorted_angles[i-1]
                curr_dir = sorted_angles[i+1] - sorted_angles[i]
                if abs(prev_dir) > 0.01 and abs(curr_dir) > 0.01:  # Ignore noise
                    if (prev_dir > 0) != (curr_dir > 0):
                        direction_changes += 1
        
        # Allow at most 1 direction change (for backlash/noise at endpoints)
        if direction_changes > 1:
            print("✗ FAIL: Motor positions not monotonic with MIDI values")
            print(f"  Direction changes: {direction_changes} (expected <= 1)")
            print(f"  Sorted positions: {sorted_pos}")
            self.results.append(("Motor Sweep", False, "Non-monotonic response"))
            return False
        
        print(f"✓ PASS: Motor tracks sweep range")
        print(f"  Excursion: {excursion:.4f} rad, {unique_positions} distinct positions")
        self.results.append(("Motor Sweep", True, None))
        return True

    def test_motor_dynamics_highspeed(self):
        """Test 5b (Removed): High-speed motor dynamics capture

        REMOVED: High-speed monitoring tool removed (motor_monitor.py).
        Reason: Requires 10-100 Hz sampling incompatible with 1 Hz USB debug rate.
        See .agentic/FAILED_EXPERIMENTS.md for details.
        """
        if not self.debug_ser:
            print("⊘ SKIP: Debug serial not available for high-speed monitoring")
            return None
        
        print("\n" + "=" * 70)
        print("TEST 5B: High-Speed Motor Dynamics (REMOVED)")
        print("=" * 70)
        print("⊘ SKIP: High-speed monitoring removed (incompatible with USB stability)")
        print("        See .agentic/FAILED_EXPERIMENTS.md")
        return None

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

    def write_results_json(self, json_out, success):
        """Write structured test results for CI artifacts"""
        if not json_out:
            return

        status_map = {True: "pass", False: "fail", None: "skip"}
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "debug_port": self.debug_port,
            "midi_port": self.midi_port,
            "enable_monitor": self.enable_monitor,
            "success": bool(success),
            "summary": {
                "passed": sum(1 for _, s, _ in self.results if s is True),
                "failed": sum(1 for _, s, _ in self.results if s is False),
                "skipped": sum(1 for _, s, _ in self.results if s is None),
                "total": len(self.results),
            },
            "results": [
                {"test": name, "status": status_map[state], "note": note}
                for name, state, note in self.results
            ],
            "firmware_info": self.firmware_info,
        }

        output_path = Path(json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote JSON results: {output_path}")

    def run_all(self, json_out=None, selected_tests=None):
        """Run all tests or selected subset
        
        Args:
            json_out: Path to write JSON results
            selected_tests: List of test names to run (e.g., ['connectivity', 'midi'])
                           If None, runs all tests
        """
        print("\n" + "=" * 70)
        print("USB HID JOYSTICK CONTROLLER - AUTOMATED TEST SUITE")
        print("=" * 70)
        
        if not self.connect():
            print("Failed to connect to device")
            self.write_results_json(json_out, False)
            return False
        
        # Map of test names to methods
        test_map = {
            'connectivity': self.test_system_identification,
            'position': self.test_motor_initial_position,
            'midi': self.test_motor_response_to_midi,
            'scaling': self.test_joystick_scaling,
            'sweep': self.test_motor_sweep,
            'dynamics': self.test_motor_dynamics_highspeed,
        }
        
        # Determine which tests to run
        if selected_tests:
            # Validate test names
            invalid = [t for t in selected_tests if t not in test_map]
            if invalid:
                print(f"ERROR: Unknown test(s): {', '.join(invalid)}")
                print(f"Available tests: {', '.join(test_map.keys())}")
                self.close()
                return False
            tests_to_run = [(name, test_map[name]) for name in selected_tests]
            print(f"Running selected tests: {', '.join(selected_tests)}")
        else:
            # Run all tests
            tests_to_run = [
                ('connectivity', self.test_system_identification),
                ('position', self.test_motor_initial_position),
                ('midi', self.test_motor_response_to_midi),
                ('scaling', self.test_joystick_scaling),
                ('sweep', self.test_motor_sweep),
            ]
            # Add dynamics only if monitor enabled
            if self.enable_monitor:
                tests_to_run.append(('dynamics', self.test_motor_dynamics_highspeed))
        
        try:
            # Run tests in sequence
            for test_name, test_method in tests_to_run:
                test_method()
            
            # Print summary
            all_pass = self.print_results()
            self.write_results_json(json_out, all_pass)
            return all_pass
        finally:
            self.close()


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(
        description="Automated test suite for USB HID joystick controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python3 test_suite_automated.py                    # Run all standard tests
  python3 test_suite_automated.py --enable-monitor   # Include high-speed dynamics test
  python3 test_suite_automated.py --tests midi sweep # Run only MIDI and sweep tests
  
Available tests:
  connectivity - System identification (firmware, config)
  position     - Motor initial position check
  midi         - Motor response to MIDI commands
  scaling      - Joystick output scaling
  sweep        - Motor sweep range and tracking
  dynamics     - High-speed dynamics (requires --enable-monitor)
        """
    )
    parser.add_argument(
        "--enable-monitor",
        action="store_true",
        help="Enable optional high-speed motor dynamics monitoring (TEST 5B)"
    )
    parser.add_argument("--debug-port", help="Serial port for debug output")
    parser.add_argument("--midi-port", help="Serial port for MIDI input")
    parser.add_argument("--json-out", help="Write structured JSON test report to this path")
    parser.add_argument(
        "--tests",
        nargs='+',
        metavar='TEST',
        help="Run only specified tests (e.g., --tests midi sweep)"
    )
    
    args = parser.parse_args()
    
    suite = HIDControllerTestSuite(
        debug_port=args.debug_port,
        midi_port=args.midi_port,
        enable_monitor=args.enable_monitor
    )
    success = suite.run_all(json_out=args.json_out, selected_tests=args.tests)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
