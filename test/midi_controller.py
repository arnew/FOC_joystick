#!/usr/bin/env python3
"""
MIDI Controller Simulator
Sends MIDI CC messages to the RP2040 controller via serial port
"""

import serial
import time
import sys

class MIDIController:
    """Send MIDI CC messages to RP2040 via serial port (USB or UART)"""
    
    def __init__(self, port=None, baudrate=31250):
        """Initialize MIDI serial connection
        
        Args:
            port: Serial port path (e.g., /dev/ttyACM0). If None, auto-detect.
            baudrate: Baud rate (31250 for MIDI, 115200 for USB debug)
        """
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        
    def connect(self):
        """Open serial connection
        
        If port not specified, auto-detect available RP2040 ports.
        NOTE: RP2040 mini typically only has one USB serial port for both
              debug (115200) and MIDI (31250). Use UART module or USB-UART
              adapter for dedicated MIDI input.
        """
        if not self.port:
            # Auto-detect RP2040 ports
            import glob
            possible_ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
            
            if not possible_ports:
                print("❌ No serial ports found!")
                print("Troubleshooting:")
                print("  1. Check USB cable is connected to RP2040")
                print("  2. Verify RP2040 is in USB mode (not SWD debug)")
                print("  3. Run: lsusb | grep Raspberry")
                return False
            
            # Try each port
            for port in sorted(possible_ports):
                try:
                    ser = serial.Serial(port, self.baudrate, timeout=0.5)
                    self.port = port
                    self.serial = ser
                    print(f"✓ Connected to {port} at {self.baudrate} baud")
                    return True
                except (serial.SerialException, OSError):
                    continue
            
            print(f"❌ Could not connect to any port: {possible_ports}")
            print(f"   Tried baud rate: {self.baudrate}")
            return False
        else:
            # Explicit port specified
            try:
                self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
                time.sleep(0.5)  # Wait for serial setup
                print(f"✓ Connected to {self.port} at {self.baudrate} baud")
                return True
            except serial.SerialException as e:
                print(f"❌ Failed to connect to {self.port}: {e}")
                return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.serial:
            self.serial.close()
            print("Disconnected")
    
    def send_cc(self, cc_number, value, channel=0):
        """
        Send MIDI Control Change message
        
        Args:
            cc_number: CC number (0-127)
            value: CC value (0-127)
            channel: MIDI channel (0-15, default 0)
        """
        if not self.serial:
            print("Not connected!")
            return False
        
        # MIDI CC: 0xBn (where n = channel), CC#, value
        status_byte = 0xB0 | (channel & 0x0F)
        cc_byte = cc_number & 0x7F
        val_byte = value & 0x7F
        
        message = bytes([status_byte, cc_byte, val_byte])
        
        try:
            self.serial.write(message)
            print(f"Sent: CC#{cc_number:3d} = {value:3d}")
            return True
        except serial.SerialException as e:
            print(f"Failed to send: {e}")
            return False
    
    def sweep(self, cc_number, start=0, end=127, step=1, delay=0.1):
        """Sweep a CC from start to end value"""
        for value in range(start, end + 1, step):
            self.send_cc(cc_number, value)
            time.sleep(delay)
    
    def test_a320_endless_motor(self):
        """Test trim on endless motor (CC#64) with fine-grained steps"""
        print("\n=== Testing Endless Motor (Trim) ===")
        print("Sweeping CC#64 (Trim) 0→127→0 with fine resolution...")
        print("(128 steps = ~2.8° increments on endless motor)")
        self.sweep(64, 0, 127, step=1, delay=0.02)
        self.sweep(64, 127, 0, step=1, delay=0.02)
    
    def test_a320_limited_motor(self):
        """Test throttle on limited motor (CC#7) with fine-grained steps"""
        print("\n=== Testing Limited Motor (Throttle) ===")
        print("Sweeping CC#7 (Throttle) 0→127→0 with fine resolution...")
        print("(128 steps = ~1.4° increments on 180° motor)")
        self.sweep(7, 0, 127, step=1, delay=0.02)
        self.sweep(7, 127, 0, step=1, delay=0.02)


def interactive_menu(controller):
    """Interactive MIDI test menu"""
    print("\n=== MIDI Controller Test Menu ===")
    print("1. Test endless motor (CC#64 Trim)")
    print("2. Test limited motor (CC#7 Throttle)")
    print("3. Send custom CC")
    print("4. Quick sweep")
    print("5. Exit")
    
    while True:
        try:
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == "1":
                controller.test_a320_endless_motor()
            elif choice == "2":
                controller.test_a320_limited_motor()
            elif choice == "3":
                cc_num = int(input("CC number (0-127): "))
                value = int(input("CC value (0-127): "))
                controller.send_cc(cc_num, value)
            elif choice == "4":
                cc_num = int(input("CC number to sweep: "))
                controller.sweep(cc_num, delay=0.1)
            elif choice == "5":
                break
            else:
                print("Invalid choice")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except ValueError:
            print("Invalid input")


if __name__ == "__main__":
    import glob
    
    # Parse command-line arguments
    port = None
    baudrate = 31250  # MIDI standard
    
    if len(sys.argv) > 1:
        if sys.argv[1].startswith("/dev/"):
            port = sys.argv[1]
        else:
            try:
                baudrate = int(sys.argv[1])
            except ValueError:
                print(f"Usage: {sys.argv[0]} [port] [baudrate]")
                print(f"  port: e.g., /dev/ttyACM0 (auto-detect if omitted)")
                print(f"  baudrate: 31250 (MIDI) or 115200 (debug)")
                sys.exit(1)
    
    if len(sys.argv) > 2:
        try:
            baudrate = int(sys.argv[2])
        except ValueError:
            pass
    
    # Show available ports before connecting
    available = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
    print(f"Available serial ports: {available if available else '(none found)'}")
    print(f"Attempting connection at {baudrate} baud...")
    print()
    
    controller = MIDIController(port=port, baudrate=baudrate)
    
    if not controller.connect():
        print("\n⚠️  Failed to connect!")
        print("\nNote: RP2040 mini boards typically only have ONE USB serial port.")
        print("If your board has separate MIDI hardware via UART1, check:")
        print("  1. USB-UART adapter is plugged in")
        print("  2. UART1 TX/RX are wired to the adapter")
        print("  3. Baud rate matches Arduino Serial1.begin(31250)")
        print("\nAlternatively, use baudrate 115200 to send MIDI via the debug port:")
        print(f"  python3 {sys.argv[0]} 115200")
        sys.exit(1)
    
    try:
        interactive_menu(controller)
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        controller.disconnect()
