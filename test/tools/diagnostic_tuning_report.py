#!/usr/bin/env python3
"""
Diagnostic Tuning Report - Comprehensive Motor Performance Analysis

Captures:
- Actual position traces showing settling behavior
- PID configuration from device
- Limit checking (voltage, current, angle)
- Tolerance measurements
- Tuning recommendations based on observed behavior
"""

import serial
import time
import math
import json
import sys
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class PositionTrace:
    """Position sample with metadata"""
    time_ms: float
    angle_deg: float
    target_deg: float
    error_deg: float
    velocity_dps: Optional[float] = None


@dataclass
class SettlingAnalysis:
    """Analysis of settling behavior"""
    target_deg: float
    final_error_deg: float
    settled: bool
    settle_time_ms: Optional[float]
    overshoot_deg: float
    undershoot_deg: float
    oscillation_detected: bool
    rms_error: float
    trace: List[PositionTrace]


class DiagnosticTuningReport:
    """Generate comprehensive tuning diagnostic report"""
    
    def __init__(self, port: str = '/dev/ttyACM0'):
        self.port = port
        self.ser = None
        self.pid_config = {}
        self.limits = {}
        self.statistics = {}
        
    def connect(self) -> bool:
        """Connect to device"""
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=2.0)
            time.sleep(0.5)
            print(f"✓ Connected to {self.port}")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def query_pid_config(self) -> Dict:
        """Query current PID configuration via SimpleFOC Commander"""
        print("\n=== Querying PID Configuration ===")
        config = {}
        
        # Query angle PID (P, I, D)
        for cmd, name in [('AP', 'angle_P'), ('AI', 'angle_I'), ('AD', 'angle_D')]:
            self.ser.reset_input_buffer()
            self.ser.write(f'M0.{cmd}?\n'.encode())
            time.sleep(0.2)
            response = self.ser.read_all().decode('utf-8', errors='ignore')
            match = re.search(r'([\d.]+)', response)
            if match:
                config[name] = float(match.group(1))
                print(f"  {name}: {config[name]}")
        
        # Query velocity PID (VP, VI, VD)
        for cmd, name in [('VP', 'velocity_P'), ('VI', 'velocity_I'), ('VD', 'velocity_D')]:
            self.ser.reset_input_buffer()
            self.ser.write(f'M0.{cmd}?\n'.encode())
            time.sleep(0.2)
            response = self.ser.read_all().decode('utf-8', errors='ignore')
            match = re.search(r'([\d.]+)', response)
            if match:
                config[name] = float(match.group(1))
                print(f"  {name}: {config[name]}")
        
        # Query limits
        for cmd, name in [('L', 'voltage_limit'), ('C', 'current_limit')]:
            self.ser.reset_input_buffer()
            self.ser.write(f'M0.{cmd}?\n'.encode())
            time.sleep(0.2)
            response = self.ser.read_all().decode('utf-8', errors='ignore')
            match = re.search(r'([\d.]+)', response)
            if match:
                config[name] = float(match.group(1))
                print(f"  {name}: {config[name]}")
        
        self.pid_config = config
        return config
    
    def query_limits(self) -> Dict:
        """Query angle limits and mode"""
        print("\n=== Querying Angle Limits ===")
        limits = {}
        
        # Query angle limit mode
        self.ser.reset_input_buffer()
        self.ser.write(b'LM?\n')
        time.sleep(0.2)
        response = self.ser.read_all().decode('utf-8', errors='ignore')
        if 'Limit mode' in response:
            if 'wrap' in response.lower():
                limits['mode'] = 'wrap'
            elif 'clamp' in response.lower():
                limits['mode'] = 'clamp'
            else:
                limits['mode'] = 'unlimited'
            print(f"  Mode: {limits['mode']}")
        
        # Query angle limits (if applicable)
        for cmd, name in [('LN', 'min_angle_deg'), ('LX', 'max_angle_deg')]:
            self.ser.reset_input_buffer()
            self.ser.write(f'{cmd}?\n'.encode())
            time.sleep(0.2)
            response = self.ser.read_all().decode('utf-8', errors='ignore')
            match = re.search(r'([\d.]+)', response)
            if match:
                angle_rad = float(match.group(1))
                limits[name] = math.degrees(angle_rad)
                print(f"  {name}: {limits[name]:.1f}°")
        
        self.limits = limits
        return limits
    
    def capture_settling_trace(self, target_deg: float, duration_sec: float = 5.0) -> SettlingAnalysis:
        """Capture detailed position trace during settling"""
        print(f"\n  Target: {target_deg}° ... ", end="", flush=True)
        
        # Set target
        target_rad = math.radians(target_deg)
        self.ser.write(f'T{target_rad:.4f}\n'.encode())
        
        # Capture trace
        trace = []
        start_time = time.time()
        last_angle = None
        
        while time.time() - start_time < duration_sec:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                match = re.search(r'A=([\-\d.]+)\s+T=([\-\d.]+)', line)
                if match:
                    actual_rad = float(match.group(1))
                    target_rad_echo = float(match.group(2))
                    
                    actual_deg = math.degrees(actual_rad)
                    error_deg = abs(actual_deg - target_deg)
                    
                    # Calculate velocity if we have previous sample
                    velocity_dps = None
                    if last_angle is not None and trace:
                        dt = (time.time() - start_time) * 1000 - trace[-1].time_ms
                        if dt > 0:
                            velocity_dps = (actual_deg - last_angle) / (dt / 1000.0)
                    
                    trace.append(PositionTrace(
                        time_ms=(time.time() - start_time) * 1000,
                        angle_deg=actual_deg,
                        target_deg=target_deg,
                        error_deg=error_deg,
                        velocity_dps=velocity_dps
                    ))
                    
                    last_angle = actual_deg
            
            time.sleep(0.01)
        
        # Analyze settling behavior
        if not trace:
            print("✗ No data")
            return None
        
        angles = [t.angle_deg for t in trace]
        errors = [t.error_deg for t in trace]
        
        # Final error (last 10 samples average)
        final_samples = min(10, len(errors))
        final_error = sum(errors[-final_samples:]) / final_samples
        
        # Overshoot/undershoot
        max_angle = max(angles)
        min_angle = min(angles)
        overshoot = max(0, max_angle - target_deg)
        undershoot = max(0, target_deg - min_angle)
        
        # Settling time (first time error drops below 1° and stays there)
        settle_time = None
        settled = False
        for i in range(len(errors) - 5):
            if all(e < 1.0 for e in errors[i:i+5]):
                settle_time = trace[i].time_ms
                settled = True
                break
        
        # Oscillation detection (count zero crossings of error around target)
        oscillations = 0
        for i in range(1, len(trace)):
            if (trace[i-1].angle_deg - target_deg) * (trace[i].angle_deg - target_deg) < 0:
                oscillations += 1
        oscillation_detected = oscillations > 3
        
        # RMS error
        rms_error = math.sqrt(sum(e**2 for e in errors) / len(errors))
        
        analysis = SettlingAnalysis(
            target_deg=target_deg,
            final_error_deg=final_error,
            settled=settled,
            settle_time_ms=settle_time,
            overshoot_deg=overshoot,
            undershoot_deg=undershoot,
            oscillation_detected=oscillation_detected,
            rms_error=rms_error,
            trace=trace
        )
        
        # Print summary
        status = "✓" if settled else "✗"
        settle_str = f"{settle_time:.0f}ms" if settle_time else "N/A"
        print(f"{status} Error: {final_error:.2f}° | Settle: {settle_str} | Overshoot: {overshoot:.2f}° | RMS: {rms_error:.2f}°")
        
        return analysis
    
    def test_multiple_positions(self) -> List[SettlingAnalysis]:
        """Test settling at multiple representative positions"""
        print("\n=== Position Settling Tests ===")
        
        test_positions = [0, 45, 90, 135, 180, 225, 270, 315]
        results = []
        
        for pos in test_positions:
            analysis = self.capture_settling_trace(pos, duration_sec=3.0)
            if analysis:
                results.append(analysis)
            time.sleep(0.5)  # Brief pause between tests
        
        return results
    
    def query_statistics(self) -> Dict:
        """Query device statistics"""
        print("\n=== Device Statistics ===")
        
        self.ser.reset_input_buffer()
        time.sleep(0.1)
        self.ser.write(b'S\n')
        time.sleep(0.5)
        
        # Collect response
        response_lines = []
        timeout = time.time() + 1.0
        while time.time() < timeout:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    response_lines.append(line)
                    print(f"  {line}")
            time.sleep(0.05)
        
        response = '\n'.join(response_lines)
        
        # Parse key statistics
        stats = {}
        match = re.search(r'Max error:\s+([\d.]+)\s+rad', response)
        if match:
            stats['max_error_deg'] = math.degrees(float(match.group(1)))
        
        match = re.search(r'Movements:\s+(\d+)', response)
        if match:
            stats['movements'] = int(match.group(1))
        
        self.statistics = stats
        return stats
    
    def generate_tuning_recommendations(self, analyses: List[SettlingAnalysis]) -> List[str]:
        """Generate tuning recommendations based on observed behavior"""
        recommendations = []
        
        # Analyze common patterns
        avg_final_error = sum(a.final_error_deg for a in analyses) / len(analyses)
        avg_overshoot = sum(a.overshoot_deg for a in analyses) / len(analyses)
        avg_settle_time = sum(a.settle_time_ms for a in analyses if a.settle_time_ms) / max(1, sum(1 for a in analyses if a.settle_time_ms))
        settled_count = sum(1 for a in analyses if a.settled)
        oscillating_count = sum(1 for a in analyses if a.oscillation_detected)
        
        print("\n=== Performance Summary ===")
        print(f"  Positions tested: {len(analyses)}")
        print(f"  Settled within 1°: {settled_count}/{len(analyses)} ({settled_count/len(analyses)*100:.0f}%)")
        print(f"  Average final error: {avg_final_error:.2f}°")
        print(f"  Average overshoot: {avg_overshoot:.2f}°")
        print(f"  Average settle time: {avg_settle_time:.0f}ms")
        print(f"  Oscillating: {oscillating_count}/{len(analyses)}")
        
        print("\n=== Tuning Recommendations ===")
        
        # High final error → increase P or check mechanical
        if avg_final_error > 2.0:
            recommendations.append("❗ HIGH STEADY-STATE ERROR (avg {:.2f}°)".format(avg_final_error))
            recommendations.append("   → Increase angle_P (currently {:.1f}, try {:.1f})".format(
                self.pid_config.get('angle_P', 10.0),
                self.pid_config.get('angle_P', 10.0) * 1.5
            ))
            recommendations.append("   → OR increase angle_I (currently {:.1f}, try 0.1-0.5)".format(
                self.pid_config.get('angle_I', 0.0)
            ))
            recommendations.append("   → Check sensor alignment and mechanical friction")
        
        # High overshoot → reduce P, increase D
        if avg_overshoot > 5.0:
            recommendations.append("❗ HIGH OVERSHOOT (avg {:.2f}°)".format(avg_overshoot))
            recommendations.append("   → Reduce angle_P (currently {:.1f}, try {:.1f})".format(
                self.pid_config.get('angle_P', 10.0),
                self.pid_config.get('angle_P', 10.0) * 0.7
            ))
            recommendations.append("   → Increase angle_D (currently {:.1f}, try {:.1f})".format(
                self.pid_config.get('angle_D', 0.5),
                self.pid_config.get('angle_D', 0.5) * 2.0
            ))
        
        # Oscillation → reduce P, increase D
        if oscillating_count > len(analyses) / 2:
            recommendations.append("❗ OSCILLATION DETECTED")
            recommendations.append("   → Reduce angle_P (currently {:.1f}, try {:.1f})".format(
                self.pid_config.get('angle_P', 10.0),
                self.pid_config.get('angle_P', 10.0) * 0.8
            ))
            recommendations.append("   → Increase angle_D (currently {:.1f}, try {:.1f})".format(
                self.pid_config.get('angle_D', 0.5),
                self.pid_config.get('angle_D', 0.5) * 1.5
            ))
            recommendations.append("   → Check low-pass filter (currently {:.3f}s, try 0.010s for more damping)".format(0.005))
        
        # Slow settling → increase P or velocity limits
        if avg_settle_time > 2000:
            recommendations.append("❗ SLOW SETTLING (avg {:.0f}ms)".format(avg_settle_time))
            recommendations.append("   → Increase angle_P (currently {:.1f}, try {:.1f})".format(
                self.pid_config.get('angle_P', 10.0),
                self.pid_config.get('angle_P', 10.0) * 1.3
            ))
            recommendations.append("   → Check velocity_limit (increase if capped)")
            recommendations.append("   → Check voltage_limit (currently {:.1f}V, try {:.1f}V if motor can handle)".format(
                self.pid_config.get('voltage_limit', 2.0),
                min(12.0, self.pid_config.get('voltage_limit', 2.0) * 1.5)
            ))
        
        # Good performance
        if avg_final_error < 1.0 and avg_overshoot < 3.0 and settled_count == len(analyses):
            recommendations.append("✅ GOOD PERFORMANCE - PID well tuned!")
            recommendations.append("   Current settings are working well")
            recommendations.append("   Fine-tune if needed for specific applications")
        
        # Voltage/current limits check
        if self.pid_config.get('voltage_limit', 2.0) < 3.0:
            recommendations.append("⚠️  LOW VOLTAGE LIMIT ({:.1f}V)".format(self.pid_config.get('voltage_limit', 2.0)))
            recommendations.append("   → Consider increasing if motor performance is sluggish")
            recommendations.append("   → Check motor specs for safe operating voltage")
        
        for rec in recommendations:
            print(rec)
        
        return recommendations
    
    def export_report(self, analyses: List[SettlingAnalysis], recommendations: List[str], filepath: str):
        """Export comprehensive diagnostic report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'device': self.port,
            'pid_config': self.pid_config,
            'limits': self.limits,
            'statistics': self.statistics,
            'settling_analyses': [
                {
                    'target_deg': a.target_deg,
                    'final_error_deg': a.final_error_deg,
                    'settled': a.settled,
                    'settle_time_ms': a.settle_time_ms,
                    'overshoot_deg': a.overshoot_deg,
                    'undershoot_deg': a.undershoot_deg,
                    'oscillation_detected': a.oscillation_detected,
                    'rms_error': a.rms_error,
                    'trace_length': len(a.trace)
                }
                for a in analyses
            ],
            'recommendations': recommendations,
            'summary': {
                'avg_final_error_deg': sum(a.final_error_deg for a in analyses) / len(analyses),
                'avg_overshoot_deg': sum(a.overshoot_deg for a in analyses) / len(analyses),
                'settled_count': sum(1 for a in analyses if a.settled),
                'total_tests': len(analyses)
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✓ Report exported to {filepath}")
    
    def run_full_diagnostic(self, export_path: str = 'diagnostic_tuning_report.json'):
        """Run complete diagnostic and generate report"""
        if not self.connect():
            return False
        
        try:
            # Query configuration
            self.query_pid_config()
            self.query_limits()
            
            # Run settling tests
            analyses = self.test_multiple_positions()
            
            # Query final statistics
            self.query_statistics()
            
            # Generate recommendations
            recommendations = self.generate_tuning_recommendations(analyses)
            
            # Export report
            self.export_report(analyses, recommendations, export_path)
            
            return True
        finally:
            if self.ser:
                self.ser.close()
                print("\n✓ Connection closed")


def main():
    """Run diagnostic report"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Diagnostic Tuning Report for Motor Control")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port")
    parser.add_argument("--output", default="diagnostic_tuning_report.json", help="Output JSON file")
    
    args = parser.parse_args()
    
    diagnostic = DiagnosticTuningReport(port=args.port)
    success = diagnostic.run_full_diagnostic(export_path=args.output)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
