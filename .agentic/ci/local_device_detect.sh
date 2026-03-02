#!/bin/bash
# local_device_detect.sh - Detect RP2040 device and testing capabilities
# Usage: source local_device_detect.sh [--save]
# 
# Sets environment variables:
#   DEVICE_PORT - Serial port path (e.g., /dev/ttyACM0)
#   DEVICE_AVAILABLE - true/false
#   DEVICE_BOOTSEL - true if device appears in bootloader
#   CAN_TEST_LOCAL - true if device ready for testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[DEVICE DETECTION] Scanning for RP2040 devices...${NC}"

# Initialize variables
DEVICE_PORT=""
DEVICE_AVAILABLE=false
DEVICE_BOOTSEL=false
CAN_TEST_LOCAL=false

# 1. Check for serial ports
echo "[CHECK 1] Serial ports..."
SERIAL_PORTS=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true)

if [ -z "$SERIAL_PORTS" ]; then
    echo -e "${RED}✗ No serial ports found${NC}"
else
    echo -e "${GREEN}✓ Found serial ports:${NC}"
    for port in $SERIAL_PORTS; do
        echo "  - $port"
        # Prefer ttyACM0 if it exists
        if [ "$port" = "/dev/ttyACM0" ]; then
            DEVICE_PORT="$port"
        fi
    done
    
    # If no preferred port found, use first one
    if [ -z "$DEVICE_PORT" ]; then
        DEVICE_PORT=$(echo "$SERIAL_PORTS" | head -1)
    fi
    
    DEVICE_AVAILABLE=true
fi

# 2. Check for USB vendor ID (RP2040 = 2e8a)
echo "[CHECK 2] RP2040 USB identification..."
if lsusb 2>/dev/null | grep -q "2e8a"; then
    echo -e "${GREEN}✓ Found RP2040 (vendor 2e8a)${NC}"
    
    # Check if in bootloader mode
    if lsusb | grep -q "2e8a:0003"; then
        echo -e "${YELLOW}⚠ Device in BOOTSEL mode (firmware upload pending)${NC}"
        DEVICE_BOOTSEL=true
    elif lsusb | grep -q "2e8a:0005"; then
        echo -e "${GREEN}✓ Device in normal operation mode${NC}"
        CAN_TEST_LOCAL=true
    fi
else
    if [ "$DEVICE_AVAILABLE" = true ]; then
        echo -e "${YELLOW}⚠ Serial port found but RP2040 not detected via lsusb${NC}"
        echo "  (May be filtered by permissions or running in VM)"
    else
        echo -e "${RED}✗ No RP2040 detected${NC}"
    fi
fi

# 3. Check serial port permissions
if [ -n "$DEVICE_PORT" ]; then
    echo "[CHECK 3] Serial port permissions..."
    if [ -r "$DEVICE_PORT" ] && [ -w "$DEVICE_PORT" ]; then
        echo -e "${GREEN}✓ Can read/write $DEVICE_PORT${NC}"
        CAN_TEST_LOCAL=true
    else
        echo -e "${RED}✗ No read/write permission on $DEVICE_PORT${NC}"
        echo "  Fix with: sudo usermod -a -G dialout \$USER"
        CAN_TEST_LOCAL=false
    fi
fi

# 4. Test connectivity
if [ "$CAN_TEST_LOCAL" = true ]; then
    echo "[CHECK 4] Testing serial connectivity..."
    # Try to get a telemetry line with 2 second timeout
    if timeout 2 cat "$DEVICE_PORT" 2>/dev/null | head -1 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Device responding on $DEVICE_PORT${NC}"
    else
        echo -e "${YELLOW}⚠ Device not responding (may need firmware upload)${NC}"
        CAN_TEST_LOCAL=false
    fi
fi

# Summary
echo ""
echo "=========================================="
echo "DEVICE STATUS SUMMARY"
echo "=========================================="
echo "Device Port:       $DEVICE_PORT"
echo "Available:         $DEVICE_AVAILABLE"
echo "In BOOTSEL:        $DEVICE_BOOTSEL"
echo "Ready to Test:     $CAN_TEST_LOCAL"
echo "=========================================="
echo ""

# Export variables for use in scripts
export DEVICE_PORT
export DEVICE_AVAILABLE
export DEVICE_BOOTSEL
export CAN_TEST_LOCAL

# Save to config file if requested
if [ "${1:-}" = "--save" ]; then
    CONFIG_FILE=".agentic/local_device.conf"
    echo "[SAVE] Writing config to $CONFIG_FILE"
    cat > "$CONFIG_FILE" << EOF
# Local device configuration (auto-detected)
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

DEVICE_PORT=$DEVICE_PORT
DEVICE_AVAILABLE=$DEVICE_AVAILABLE
DEVICE_BOOTSEL=$DEVICE_BOOTSEL
CAN_TEST_LOCAL=$CAN_TEST_LOCAL

# Test commands:
# - Local test:  cd test && python3 test_motor_movement.py
# - CI test:     gh workflow run hardware-test.yml --ref dev
EOF
    echo -e "${GREEN}✓ Config saved${NC}"
fi

# Exit with success only if device is ready
if [ "$CAN_TEST_LOCAL" = true ]; then
    exit 0
else
    exit 1
fi
