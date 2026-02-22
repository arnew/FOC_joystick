#!/usr/bin/env python3
"""
USB HID Joystick Monitor
Reads and displays joystick axis values from the USB HID device
Uses pygame which provides cross-platform joystick support
"""

import sys
import time

def monitor_joystick():
    """Monitor joystick axis values using pygame"""
    try:
        import pygame
    except ImportError:
        print("pygame not installed. Install with: pip3 install pygame")
        return False
    
    pygame.init()
    pygame.joystick.init()
    
    # Look for joystick
    joystick_count = pygame.joystick.get_count()
    if joystick_count == 0:
        print("No joystick found!")
        print("Make sure the USB HID joystick is connected and enumerated.")
        return False
    
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    print(f"Found joystick: {joystick.get_name()}")
    print(f"Axes: {joystick.get_numaxes()}")
    print(f"Buttons: {joystick.get_numbuttons()}")
    print(f"Hats: {joystick.get_numhats()}")
    print("\nMonitoring axes (Ctrl+C to exit)...")
    print("=" * 60)
    
    clock = pygame.time.Clock()
    
    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.JOYAXISMOTION:
                    # Convert -1.0..1.0 to 0..1023
                    value = int((event.value + 1.0) / 2.0 * 1023)
                    print(f"Axis {event.axis}: {event.value:7.4f} ({value:4d}/1023)")
                elif event.type == pygame.JOYBUTTONDOWN:
                    print(f"Button {event.button} pressed")
                elif event.type == pygame.JOYHATMOTION:
                    print(f"Hat {event.hat}: {event.value}")
            
            clock.tick(10)  # 10 Hz update
    except KeyboardInterrupt:
        print("\nExit")
        return True
    finally:
        pygame.quit()


def monitor_serial_debug():
    """Monitor serial debug output from RP2040"""
    import serial
    
    port = "/dev/ttyACM0"  # RP2040 debug serial
    
    print(f"Connecting to {port} at 115200 baud...")
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        time.sleep(1)
        print("Connected. Press Ctrl+C to exit.\n")
        print("=" * 60)
        
        while True:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(line)
    except serial.SerialException as e:
        print(f"Failed to connect: {e}")
        return False
    except KeyboardInterrupt:
        print("\nExit")
        return True
    finally:
        ser.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serial":
        monitor_serial_debug()
    else:
        monitor_joystick()
