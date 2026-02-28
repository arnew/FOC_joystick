#!/bin/bash
# ci_device_detect.sh - Detect device on CI hardware runner
# Usage: bash ci_device_detect.sh
#
# Checks:
# - Is this a self-hosted runner?
# - Is the RP2040 device available?
# - Can we deploy firmware?
# - Can we run tests?

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo "CI DEVICE DETECTION"
echo "==========================================${NC}"
echo ""

# Check if we're in a CI environment
if [ -z "$GITHUB_ACTIONS" ]; then
    echo -e "${YELLOW}⚠ Not running under GitHub Actions${NC}"
    echo "  (This script is meant for CI workflows)"
fi

if [ -n "$GITHUB_RUNNER_NAME" ]; then
    echo "Runner: $GITHUB_RUNNER_NAME"
fi

echo ""
echo "Checking hardware availability..."
echo ""

# 1. Check for RP2040 devices
echo "[CHECK 1] Serial ports..."
DEVICE_COUNT=$(ls /dev/ttyACM* 2>/dev/null | wc -l)
if [ "$DEVICE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $DEVICE_COUNT serial device(s)${NC}"
    ls -la /dev/ttyACM* 2>/dev/null || true
    DEVICE_PORT="/dev/ttyACM0"
else
    echo -e "${RED}✗ No serial devices found${NC}"
    echo "  Check: ls /dev/ttyACM*"
    DEVICE_PORT=""
fi

echo ""

# 2. Check USB enumeration
echo "[CHECK 2] USB enumeration..."
if command -v lsusb &> /dev/null; then
    if lsusb | grep -q "2e8a"; then
        echo -e "${GREEN}✓ RP2040 found on USB${NC}"
        lsusb | grep 2e8a
    else
        echo -e "${RED}✗ No RP2040 on USB${NC}"
    fi
else
    echo -e "${YELLOW}⚠ lsusb not available${NC}"
fi

echo ""

# 3. Check udev permissions (typical CI issue)
echo "[CHECK 3] Device access..."
if [ -n "$DEVICE_PORT" ] && [ -e "$DEVICE_PORT" ]; then
    if [ -r "$DEVICE_PORT" ] && [ -w "$DEVICE_PORT" ]; then
        echo -e "${GREEN}✓ Can read/write $DEVICE_PORT${NC}"
    else
        echo -e "${RED}✗ No read/write permission on $DEVICE_PORT${NC}"
        echo "  Run: sudo usermod -a -G dialout github"
        ls -la "$DEVICE_PORT"
    fi
fi

echo ""

# 4. Check for platformio
echo "[CHECK 4] Firmware upload tools..."
if command -v platformio &> /dev/null; then
    echo -e "${GREEN}✓ PlatformIO available${NC}"
    UPLOAD_CAPABLE=true
else
    echo -e "${YELLOW}⚠ PlatformIO not found${NC}"
    echo "  Install with: pip install platformio"
    UPLOAD_CAPABLE=false
fi

echo ""

# 5. Check for python test runner
echo "[CHECK 5] Test tools..."
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓ Python available${NC}"
    python3 --version
    TEST_CAPABLE=true
else
    echo -e "${RED}✗ Python not found${NC}"
    TEST_CAPABLE=false
fi

echo ""

# 6. Test device responsiveness
if [ -n "$DEVICE_PORT" ] && [ -r "$DEVICE_PORT" ]; then
    echo "[CHECK 6] Device responsiveness..."
    # Try to read telemetry with timeout
    if timeout 2 bash -c "head -1 < $DEVICE_PORT > /dev/null 2>&1"; then
        echo -e "${GREEN}✓ Device responding${NC}"
        DEVICE_READY=true
    else
        echo -e "${YELLOW}⚠ No response from device (may need boot)${NC}"
        DEVICE_READY=false
    fi
else
    echo -e "${RED}✗ Cannot test device (no port)${NC}"
    DEVICE_READY=false
fi

echo ""
echo -e "${BLUE}=========================================="
echo "SUMMARY"
echo "==========================================${NC}"
echo "Device Port:        ${DEVICE_PORT:-none}"
echo "USB Detected:       $(lsusb 2>/dev/null | grep -q 2e8a && echo 'yes' || echo 'no')"
echo "Device Responsive:  $([ "$DEVICE_READY" = true ] && echo 'yes' || echo 'no')"
echo "Can Upload:         $([ "$UPLOAD_CAPABLE" = true ] && echo 'yes' || echo 'no')"
echo "Can Test:           $([ "$TEST_CAPABLE" = true ] && echo 'yes' || echo 'no')"
echo -e "==========================================${NC}"
echo ""

# Set exit code based on critical checks
if [ -n "$DEVICE_PORT" ] && [ "$DEVICE_READY" = true ] && [ "$UPLOAD_CAPABLE" = true ]; then
    echo -e "${GREEN}✓ CI environment ready for testing${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠ Some checks failed - review above${NC}"
    exit 1
fi
