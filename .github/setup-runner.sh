#!/bin/bash
# Setup script for self-hosted GitHub Actions runner
# Run this on the runner machine to install all dependencies

set -e

echo "=== GitHub Actions Runner Setup ==="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "ERROR: Don't run this script as root (it will use sudo when needed)"
   exit 1
fi

# Install system packages
echo "Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3-serial python3-pygame pipx

# Install PlatformIO via pipx
echo ""
echo "Installing PlatformIO via pipx..."
pipx install platformio
pipx ensurepath

# Add user to dialout group
echo ""
echo "Adding user to dialout group..."
sudo usermod -a -G dialout $USER

# Verify installation
echo ""
echo "=== Verification ==="
echo "Python version: $(python3 --version)"
echo "pipx version: $(pipx --version)"
echo "PlatformIO version: $($HOME/.local/bin/platformio --version 2>/dev/null || echo 'NOT FOUND - logout/login required')"

# Check device
echo ""
if [ -e /dev/ttyACM0 ]; then
    echo "✓ Device found at /dev/ttyACM0"
    ls -l /dev/ttyACM0
else
    echo "⚠ Device NOT found at /dev/ttyACM0 (connect hardware)"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "IMPORTANT: Log out and back in for group changes to take effect!"
echo "Then verify platformio is in PATH:"
echo "  platformio --version"
echo ""
echo "To start the runner:"
echo "  cd ~/actions-runner"
echo "  ./run.sh"
