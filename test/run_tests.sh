#!/usr/bin/env bash
set -euo pipefail

# Usage: ./test/run_tests.sh [env]
# Example: ./test/run_tests.sh pico_1motor_endless

ENV=${1:-${ENV:-pico_1motor_endless}}
UPLOAD_RETRIES=1
WAIT_SECONDS=${WAIT_SECONDS:-20}

echo "Build environment: ${ENV}"
platformio run -e "${ENV}"

echo "Attempting upload (env: ${ENV})..."
if ! platformio run -e "${ENV}" --target upload; then
  echo "Initial upload failed."
  for i in $(seq 1 ${UPLOAD_RETRIES}); do
    echo ""
    echo "Please put the board into BOOTSEL (mass storage) mode now, then press Enter to retry upload or Ctrl-C to cancel."
    read -r
    if platformio run -e "${ENV}" --target upload; then
      echo "Upload succeeded on retry."
      break
    else
      echo "Upload still failed."
    fi
  done
fi

# Wait for serial device to enumerate
echo "Waiting up to ${WAIT_SECONDS}s for serial port (/dev/ttyACM* or /dev/ttyUSB*)..."
shopt -s nullglob || true
found=0
for i in $(seq 1 "${WAIT_SECONDS}"); do
  files=(/dev/ttyACM* /dev/ttyUSB*)
  if [ "${#files[@]}" -gt 0 ]; then
    echo "Found serial device(s): ${files[*]}"
    found=1
    break
  fi
  sleep 1
done

if [ "${found}" -ne 1 ]; then
  echo "Warning: No serial device appeared after ${WAIT_SECONDS}s. You may need to replug the board or run the test script manually."
fi

echo "Running automated tests..."
# After CDC MIDI removal, only 1 ACM device (debug serial) should enumerate
# MIDI input is now native USB MIDI, not a serial port
if [ -z "${DEBUG_PORT:-}" ]; then
  acm=(/dev/ttyACM*)
  usb=(/dev/ttyUSB*)
  # combine preferred ordering
  devs=()
  for d in "${acm[@]}"; do
    if [ -e "$d" ]; then devs+=("$d"); fi
  done
  for d in "${usb[@]}"; do
    if [ -e "$d" ]; then devs+=("$d"); fi
  done

  if [ ${#devs[@]} -ge 1 ]; then
    export DEBUG_PORT=${devs[0]}
    echo "Auto-set DEBUG_PORT=${DEBUG_PORT}"
  fi
fi

set +e
python3 test/test_suite_automated.py
rc_serial=$?
set -e

# Run HID/joystick presence test (non-root friendly)
echo "Running HID/joystick presence test..."
set +e
python3 test/test_hid_report.py
rc_hid=$?
set -e

echo "Serial tests exit code: ${rc_serial}, HID presence test exit code: ${rc_hid}"

# Run HID exercise test (sends MIDI -> verifies axis changes) if pygame + MIDI available
echo "Running HID exercise test (pygame + MIDI)..."
set +e
python3 test/test_hid_exercise.py
rc_hid_exercise=$?
set -e

echo "HID exercise test exit code: ${rc_hid_exercise}"

# Exit non-zero if either test failed
if [ ${rc_serial} -ne 0 ] || [ ${rc_hid} -ne 0 ] || [ ${rc_hid_exercise} -ne 0 ]; then
  echo "One or more tests failed"
  exit 1
fi
