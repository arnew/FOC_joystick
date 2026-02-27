#!/bin/bash
# CI/CD Hardware Test Runner
# Runs automated test suite on self-hosted runner with attached hardware

set -e

SERIAL_PORT=${SERIAL_PORT:-/dev/ttyACM0}
TEST_DIR=$(dirname "$0")

echo "=== Hardware Test Suite ==="
echo "Serial port: $SERIAL_PORT"
echo "Test directory: $TEST_DIR"

# Activate venv if it exists (CI environment)
if [ -f "$HOME/ci-venv/bin/activate" ]; then
    echo "Activating CI venv..."
    source "$HOME/ci-venv/bin/activate"
    python3 --version
fi

echo ""

# Check device is connected
if [ ! -e "$SERIAL_PORT" ]; then
    echo "ERROR: Device not found at $SERIAL_PORT"
    exit 1
fi

# Run automated test suite
cd "$TEST_DIR"
python3 test_suite_automated.py --port "$SERIAL_PORT" --timeout 60

echo ""
echo "=== All tests passed ==="
