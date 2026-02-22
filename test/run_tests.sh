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
python3 test/test_suite_automated.py
