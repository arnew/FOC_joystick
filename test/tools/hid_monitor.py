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
                    # Convert -1.0..1.0 to 0..65535
                    value = int((event.value + 1.0) / 2.0 * 65535)
                    print(f"Axis {event.axis}: {event.value:7.4f} ({value:5d}/65535)")
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


if __name__ == "__main__":
    monitor_joystick()
