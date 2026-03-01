#!/usr/bin/env python3
"""
Endstop observation tool — structured test session.

Connects to the device, streams telemetry, and periodically queries
haptic state. The human moves the motor; this script logs everything.

Usage: python3 test/tools/endstop_observer.py
"""

import serial
import time
import sys
import threading

PORT = '/dev/ttyACM0'
BAUD = 115200

def parse_telemetry(line):
    """Parse @T ms,target,actual,error,variance,settled"""
    parts = line.split(',')
    if len(parts) != 6:
        return None
    try:
        return {
            'ms': int(parts[0]),
            'target': float(parts[1]),
            'actual': float(parts[2]),
            'error': float(parts[3]),
            'variance': float(parts[4]),
            'settled': int(parts[5]),
        }
    except ValueError:
        return None

def rad2deg(r):
    return r * 180.0 / 3.14159265

def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.1)
    time.sleep(2)
    ser.reset_input_buffer()

    print("=" * 70)
    print("ENDSTOP OBSERVATION SESSION")
    print("=" * 70)
    print("Streaming telemetry. Haptic state queried every 2s.")
    print("Press Ctrl+C to stop.\n")

    last_haptic_query = 0
    haptic_state = {}
    
    # Send initial config query
    ser.write(b'W\n')
    
    try:
        while True:
            now = time.time()
            
            # Read all available data
            while ser.in_waiting:
                try:
                    line = ser.readline().decode('utf-8', errors='replace').strip()
                except:
                    continue
                    
                if not line:
                    continue
                
                # Parse telemetry
                if line.startswith('@T '):
                    t = parse_telemetry(line[3:])
                    if t:
                        target_deg = rad2deg(t['target'])
                        actual_deg = rad2deg(t['actual'])
                        error_deg = rad2deg(t['error'])
                        settled = "SETTLED" if t['settled'] else "MOVING"
                        
                        # Compact one-line display
                        haptic_info = ""
                        if haptic_state:
                            haptic_info = f"  | detent={haptic_state.get('detent','?')} snap={haptic_state.get('snap','?')}° raw={haptic_state.get('raw','?')}°"
                        
                        print(f"  T={target_deg:7.1f}°  A={actual_deg:7.1f}°  "
                              f"err={error_deg:+6.1f}°  var={t['variance']:.4f}  "
                              f"{settled}{haptic_info}")
                
                # Parse haptic state from W query response
                elif 'current:' in line and 'detent=' in line:
                    # Parse: "  current:    detent=0  target=0.00°  raw=1.36°"
                    try:
                        parts = line.split()
                        for p in parts:
                            if p.startswith('detent='):
                                haptic_state['detent'] = p.split('=')[1]
                            elif p.startswith('target='):
                                haptic_state['snap'] = p.split('=')[1].rstrip('°')
                            elif p.startswith('raw='):
                                haptic_state['raw'] = p.split('=')[1].rstrip('°')
                    except:
                        pass
                
                elif 'range:' in line and '..' in line:
                    # "  range:      0.00° .. 180.00°"
                    print(f"  >> {line.strip()}")
                
                elif '[HAPTIC]' in line:
                    print(f"  >> {line.strip()}")
                
                elif '[CMD]' in line:
                    print(f"  >> {line.strip()}")
            
            # Query haptic state every 2 seconds
            if now - last_haptic_query > 2.0:
                ser.write(b'W\n')
                last_haptic_query = now
            
            time.sleep(0.05)  # 20 Hz poll
    
    except KeyboardInterrupt:
        print("\n\nSession ended.")
    finally:
        ser.close()

if __name__ == '__main__':
    main()
