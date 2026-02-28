#!/usr/bin/env python3
"""
Multi-method firmware upload for RP2040 Pico.
Tries multiple upload strategies in sequence:
1. RB command (reboot to bootloader)
2. Manual BOOTSEL detection
3. PlatformIO built-in upload
"""

import serial
import time
import subprocess
import sys
from pathlib import Path
import shutil

class MultiUploader:
    def __init__(self, device="/dev/ttyACM0", verbose=True):
        self.device = device
        self.verbose = verbose
        self.firmware_path = Path(__file__).parent.parent / ".pio/build/pico_1motor_endless/firmware.uf2"
        
    def log(self, msg: str, level="INFO"):
        if self.verbose:
            if level == "ERR":
                print(f"[{level}] {msg}")
            elif level == "OK":
                print(f"[{level}] ✓ {msg}")
            else:
                print(f"[{level}] {msg}")
    
    def device_online(self) -> bool:
        return Path(self.device).exists()
    
    def wait_for_bootsel(self, timeout_sec=20) -> bool:
        """Wait for RPI-RP2 mount to appear"""
        self.log(f"Waiting for BOOTSEL mount ({timeout_sec}s timeout)...")
        
        for i in range(timeout_sec):
            # Check common mount points
            for mount in ["/media/arnew/RPI-RP2", "/media/*/RPI-RP2", "/run/media/*/RPI-RP2"]:
                if "*" in mount:
                    # Glob pattern
                    parts = mount.split("*/")
                    base = Path(parts[0])
                    if base.exists():
                        for item in base.iterdir():
                            check_path = item / "RPI-RP2"
                            if check_path.exists():
                                self.log(f"Found BOOTSEL at {check_path}", "OK")
                                return True
                else:
                    if Path(mount).exists():
                        self.log(f"Found BOOTSEL at {mount}", "OK")
                        return True
            
            time.sleep(1)
            if (i + 1) % 5 == 0:
                print(".", end="", flush=True)
        
        print()
        return False
    
    def get_bootsel_mount(self) -> Path:
        """Get the BOOTSEL mount path"""
        for mount in ["/media/arnew/RPI-RP2", "/run/media/arnew/RPI-RP2"]:
            if Path(mount).exists():
                return Path(mount)
        
        # Try glob
        base = Path("/media")
        if base.exists():
            for user_dir in base.iterdir():
                rpi_path = user_dir / "RPI-RP2"
                if rpi_path.exists():
                    return rpi_path
        
        return None
    
    def method_1_rb_command(self) -> bool:
        """Method 1: Send RB command to trigger bootloader"""
        self.log("METHOD 1: RB Command (reboot to bootloader)")
        
        if not self.device_online():
            self.log("Device not online", "ERR")
            return False
        
        try:
            self.log("Connecting to device...")
            ser = serial.Serial(self.device, 115200, timeout=1)
            time.sleep(0.5)
            ser.read_all()
            
            self.log("Sending RB command...")
            ser.write(b'RB\n')
            time.sleep(0.5)
            response = ser.read_all().decode('utf-8', errors='ignore')
            
            if 'BOOTLOADER' in response or 'BOOTSEL' in response:
                self.log("RB command acknowledged", "OK")
            else:
                self.log(f"Response: {response[:100]}", "")
            
            ser.close()
            
            # Wait for BOOTSEL mount
            if self.wait_for_bootsel(timeout_sec=15):
                self.log("Method 1 SUCCESS", "OK")
                return True
            else:
                self.log("Method 1 FAILED - BOOTSEL not mounted", "ERR")
                return False
                
        except Exception as e:
            self.log(f"Method 1 exception: {e}", "ERR")
            return False
    
    def method_2_manual_bootsel(self) -> bool:
        """Method 2: Wait for manual BOOTSEL button press"""
        self.log("\nMETHOD 2: Manual BOOTSEL (human action required)")
        self.log("Press and hold BOOTSEL button, press RESET, release both")
        
        if self.wait_for_bootsel(timeout_sec=30):
            self.log("Method 2 SUCCESS - BOOTSEL detected", "OK")
            return True
        else:
            self.log("Method 2 FAILED - timeout waiting for BOOTSEL", "ERR")
            return False
    
    def method_2_only(self) -> bool:
        """Alias for manual BOOTSEL"""
        return self.method_2_manual_bootsel()
    
    def copy_firmware_to_bootsel(self) -> bool:
        """Copy firmware.uf2 to BOOTSEL mount"""
        mount = self.get_bootsel_mount()
        if not mount:
            self.log("BOOTSEL mount not found", "ERR")
            return False
        
        if not self.firmware_path.exists():
            self.log(f"Firmware not found: {self.firmware_path}", "ERR")
            return False
        
        try:
            self.log(f"Copying firmware to {mount}...")
            dest = mount / "firmware.uf2"
            shutil.copy2(self.firmware_path, dest)
            self.log(f"Firmware copied: {dest}", "OK")
            return True
        except Exception as e:
            self.log(f"Copy failed: {e}", "ERR")
            return False
    
    def wait_for_device_reboot(self, timeout_sec=10) -> bool:
        """Wait for device to reboot after firmware upload"""
        self.log(f"Waiting for device reboot ({timeout_sec}s)...")
        
        for i in range(timeout_sec):
            if self.device_online():
                self.log("Device online!", "OK")
                return True
            time.sleep(1)
        
        self.log("Device reboot timeout", "ERR")
        return False
    
    def upload(self) -> bool:
        """Try upload methods in sequence"""
        self.log("=== Multi-Method Firmware Upload ===\n")
        
        # Try RB command first
        if self.method_1_rb_command():
            if self.copy_firmware_to_bootsel():
                time.sleep(3)
                if self.wait_for_device_reboot():
                    return True
        
        # Fall back to manual BOOTSEL
        self.log("\nFalling back to Method 2...")
        if self.method_2_manual_bootsel():
            if self.copy_firmware_to_bootsel():
                time.sleep(3)
                if self.wait_for_device_reboot():
                    return True
        
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Multi-method RP2040 firmware upload')
    parser.add_argument('--device', default='/dev/ttyACM0', help='Serial device')
    parser.add_argument('--method', choices=['1', '2', 'all'], default='all', help='Upload method')
    parser.add_argument('--quiet', action='store_true', help='Suppress output')
    args = parser.parse_args()
    
    uploader = MultiUploader(device=args.device, verbose=not args.quiet)
    
    if args.method == '1':
        success = uploader.method_1_rb_command()
        if success:
            uploader.copy_firmware_to_bootsel()
            uploader.wait_for_device_reboot()
    elif args.method == '2':
        success = uploader.method_2_only()
        if success:
            uploader.copy_firmware_to_bootsel()
            uploader.wait_for_device_reboot()
    else:  # all
        success = uploader.upload()
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
