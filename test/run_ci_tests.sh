#!/bin/bash
# CI/CD Hardware Test Runner
# Runs automated test suite on self-hosted runner with attached hardware
#
# Usage:
#   ./run_ci_tests.sh                    # Run all tests
#   ./run_ci_tests.sh midi sweep         # Run only specified tests

set -eo pipefail

SERIAL_PORT=${SERIAL_PORT:-/dev/ttyACM0}
MIDI_PORT=${MIDI_PORT:-}
TEST_DIR=$(dirname "$0")
LOG_FILE=${LOG_FILE:-ci_hardware_test.log}
JSON_FILE=${JSON_FILE:-ci_hardware_test.json}

echo "=== Hardware Test Suite ==="
echo "Serial port: $SERIAL_PORT"
echo "Test directory: $TEST_DIR"
if [ "$#" -gt 0 ]; then
    echo "Selected tests: $*"
fi

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

# Run automated test suite and always emit artifacts
cd "$TEST_DIR"
args=(test_suite_automated.py --debug-port "$SERIAL_PORT" --json-out "$JSON_FILE")
if [ -n "$MIDI_PORT" ]; then
    args+=(--midi-port "$MIDI_PORT")
fi
# Pass through test selection if specified
if [ "$#" -gt 0 ]; then
    args+=(--tests "$@")
fi

set +e
python3 "${args[@]}" 2>&1 | tee "$LOG_FILE"
test_exit=${PIPESTATUS[0]}
set -e

echo ""
echo "Artifacts written: $TEST_DIR/$LOG_FILE, $TEST_DIR/$JSON_FILE"

if [ "$test_exit" -eq 0 ]; then
    echo "=== All tests passed ==="
else
    echo "=== Tests failed with exit code $test_exit ==="
fi

exit "$test_exit"
