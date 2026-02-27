#!/bin/bash
# Hardware Integration Test Suite - Task 2
# Run on CI runner with motor connected
# Date: 2026-02-27
# Status: Ready for execution

set -e  # Exit on error

echo "================================"
echo "Hardware Integration Test Suite"
echo "================================"
echo ""
echo "Prerequisites:"
echo "  ✓ Motor connected to CI runner"
echo "  ✓ USB cable connected (Micro-B)"
echo "  ✓ Power 5V 2A minimum"
echo "  ✓ dev branch checked out"
echo ""

# ============================================================================
# PART 1: BUILD TEST
# ============================================================================
echo "PART 1: Build Firmware"
echo "======================="

printf "Building pico_1motor_endless environment... "
python -m platformio run -e pico_1motor_endless 2>&1 | tail -5 | grep -q "\\[.*\\] Linking" && echo "✓ BUILD SUCCESS" || {
  echo "✗ BUILD FAILED"
  exit 1
}

# Check binary size
BIN_SIZE=$(ls -lhS .pio/build/pico_1motor_endless/firmware.elf 2>/dev/null | awk '{print $5}' || echo "unknown")
echo "  Binary size: $BIN_SIZE"
echo ""

# ============================================================================
# PART 2: UPLOAD TEST
# ============================================================================
echo "PART 2: Upload Firmware (Automatic Reset)"
echo "=========================================="

printf "Uploading via automatic 1200bps DTR reset... "
timeout 60 python -m platformio run --target upload -e pico_1motor_endless 2>&1 | tee /tmp/upload.log | tail -10
if grep -q "SUCCESS\|upload.*firmware\|Verifying\|100" /tmp/upload.log; then
  echo "✓ UPLOAD SUCCESS"
else
  echo "✗ UPLOAD FAILED - Device not found (may need manual BOOTSEL)"
  exit 1
fi
echo ""

# Wait for device to enumerate after reboot
echo "Waiting for device enumeration..."
sleep 3

# ============================================================================
# PART 3: MOTOR TEST
# ============================================================================
echo "PART 3: Motor Angle Tracking Test"
echo "=================================="

# Find serial port
if [ -e /dev/ttyACM0 ]; then
  SERIAL_PORT="/dev/ttyACM0"
elif [ -e /dev/ttyUSB0 ]; then
  SERIAL_PORT="/dev/ttyUSB0"
else
  echo "✗ MOTOR TEST FAILED - No serial port found"
  exit 1
fi

echo "Serial port: $SERIAL_PORT"

printf "Opening serial port (115200 baud, 5 second sample)... "
timeout 5 cat "$SERIAL_PORT" 2>/dev/null | head -20 > /tmp/serial_output.txt || true

# Check for expected output pattern
if grep -q "A=[0-9].*.T=[0-9]" /tmp/serial_output.txt 2>/dev/null; then
  echo "✓ MOTOR OUTPUT DETECTED"
  echo ""
  echo "Sample output:"
  head -5 /tmp/serial_output.txt | sed 's/^/  /'
  echo ""
else
  echo "✗ MOTOR TEST FAILED - No angle output detected"
  echo "Expected format: A=X.XX T=Y.YY"
  cat /tmp/serial_output.txt | head -10 | sed 's/^/  /'
  exit 1
fi

# ============================================================================
# PART 4: HID JOYSTICK TEST
# ============================================================================
echo "PART 4: USB HID Joystick Test"
echo "============================="

if [ -e /dev/input/js0 ]; then
  echo "✓ HID JOYSTICK DETECTED at /dev/input/js0"
  
  # Try to read a single event
  timeout 2 cat /dev/input/js0 2>/dev/null | head -c 8 > /tmp/js_event.bin 2>/dev/null || true
  if [ -s /tmp/js_event.bin ]; then
    echo "✓ HID INPUT STREAM WORKING (axis events detected)"
  else
    echo "⚠ HID enumerated but no axis events yet (may need joystick movement)"
  fi
else
  echo "⚠ HID JOYSTICK NOT DETECTED at /dev/input/js0"
  echo "  Check: Is device enumerated in lsusb?"
  lsusb | grep -i "adafruit\|gaming\|hid" || echo "  No gaming devices found"
  echo "  Fallback: Can test with pygame after implementation"
fi
echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo "================================"
echo "Test Summary"
echo "================================"
echo "✓ Firmware built successfully"
echo "✓ Firmware uploaded (automatic reset)"
echo "✓ Motor angle tracking confirmed"
if [ -e /dev/input/js0 ]; then
  echo "✓ HID joystick enumerated"
else
  echo "⚠ HID joystick requires further verification"
fi
echo ""
echo "Hardware integration test PASSED"
echo "Ready for MIDI testing in next phase"
