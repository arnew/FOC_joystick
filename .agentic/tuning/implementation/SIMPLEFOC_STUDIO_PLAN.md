# SimpleFOC Studio Integration Plan

**Status**: Planned  
**Date**: February 23, 2026  
**Estimated Effort**: 8-12 hours  

---

## Overview

Replace custom serial command protocol with SimpleFOC's built-in Commander class to enable official SimpleFOC Studio GUI integration for interactive motor tuning.

### Goals

- ✅ GUI-based motor tuning with real-time visualization
- ✅ Remove 243 lines of custom command parsing code
- ✅ Standard SimpleFOC ecosystem compatibility
- ✅ Preserve quality evaluation system for validation

### Non-Goals

- ❌ Binary protocol rework (deferred - SimpleFOC Studio sufficient)
- ❌ Custom GUI development (using official tool)
- ❌ Automated tuning algorithms (manual tuning focus)

---

## Current State Analysis

### Existing Custom Protocol

**Location**: `src/main.cpp` lines 86-703

**Components**:
- Manual string parsing with `sscanf()`
- Custom command format: `PID 0 P 8.257`, `VEL 0 I 10.0`, `SHOW`
- Custom monitoring: `A=X.XX T=Y.YY` @ 100Hz
- 243 lines of command handling code

**Issues**:
- Competes with debug output on same serial port
- No error handling or validation
- SimpleFOC Studio incompatible
- Maintenance burden

### SimpleFOC Commander

**Built-in SimpleFOC library feature** (v2.4.0+):
- Text-based command protocol
- Automatic parsing via `command.run()`
- Motor callbacks: `command.motor(&motor0, cmd)`
- Monitoring: `motor.useMonitoring(Serial)`
- SimpleFOC Studio compatible

**Reference**: https://docs.simplefoc.com/commander_interface

---

## Architecture

### Firmware (Zero Custom Parsing)

```cpp
#include <communication/Commander.h>

Commander command = Commander(Serial);

void onMotor0(char* cmd) { 
  command.motor(&motor0, cmd);  // SimpleFOC handles parsing
}

void setup() {
  // Motor initialization...
  
  // Commander setup
  motor0.useMonitoring(Serial);
  motor0.monitor_variables = _MON_TARGET | _MON_ANGLE | _MON_VEL;
  motor0.monitor_downsample = 100;  // ~1 Hz
  command.add('M', onMotor0, "motor0");
  command.verbose = VerboseMode::machine_readable;
}

void loop() {
  motor0.loopFOC();
  motor0.move();
  command.run();        // SimpleFOC processes all commands
  motor0.monitor();     // SimpleFOC outputs monitoring data
  
  // Existing: MIDI, USB HID...
}
```

**Total changes**: ~20 lines added, 243 lines removed

### Python Tools

**Send Commander-format commands**:
```python
# Angle gain: MAP20.0
cmd = f"{motor}A{param}{value}\n"

# Velocity gain: MVI10.0  
cmd = f"{motor}V{param}{value}\n"

# Target: M1.57
cmd = f"{motor}{angle}\n"
```

**Parse Commander monitoring**:
```python
# Tab-separated: "target\tangle\tvelocity\n"
parts = line.split('\t')
target, angle, velocity = float(parts[0]), float(parts[1]), float(parts[2])
```

### SimpleFOC Studio

**GUI Workflow**:
1. Open https://studio.simplefoc.com
2. Connect to serial port (115200 baud)
3. Motor appears in device tree
4. Adjust PID sliders → Commander applies gains
5. Real-time plots show motor response

**Commander handles all interaction** - zero custom protocol needed.

---

## Implementation Steps

### Step 1: Remove Custom Protocol (2 hours)

**File**: `src/main.cpp`

**Delete**:
- Lines 86-140: `PIDGains` structs
- Lines 143-150: `serial_cmd_buffer` globals
- Lines 152-320: `handle_serial_command()` function
- Lines 321-355: `apply_pid_gains()` function
- Lines 357-380: `print_current_gains()` function
- Lines 683-703: Serial input processing loop

**Total**: 243 lines removed

### Step 2: Add SimpleFOC Commander (1 hour)

**File**: `src/main.cpp`

**Add to globals**:
```cpp
#include <communication/Commander.h>
Commander command = Commander(Serial);
void onMotor0(char* cmd) { command.motor(&motor0, cmd); }
// void onMotor1(char* cmd) { command.motor(&motor1, cmd); }  // Future
```

**Add to setup()**:
```cpp
motor0.useMonitoring(Serial);
motor0.monitor_variables = _MON_TARGET | _MON_ANGLE | _MON_VEL;
motor0.monitor_downsample = 100;
command.add('M', onMotor0, "motor0");
command.verbose = VerboseMode::machine_readable;
```

**Add to loop()**:
```cpp
command.run();      // Process serial commands
motor0.monitor();   // Output monitoring data
```

**Total**: ~20 lines added

### Step 3: Update Python Tools (3-4 hours)

**File**: `test/calibrate_pid.py`

**Update command methods**:
```python
def send_angle_gain(self, motor_id, param, value):
    motor = 'M' if motor_id == 0 else 'N'
    param = {'P': 'P', 'I': 'I', 'D': 'D'}[param]
    self.serial.write(f"{motor}A{param}{value}\n".encode())
    time.sleep(0.05)

def send_velocity_gain(self, motor_id, param, value):
    motor = 'M' if motor_id == 0 else 'N'
    param = {'P': 'P', 'I': 'I', 'D': 'D'}[param]
    self.serial.write(f"{motor}V{param}{value}\n".encode())
    time.sleep(0.05)

def set_target_angle(self, motor_id, angle_rad):
    motor = 'M' if motor_id == 0 else 'N'
    self.serial.write(f"{motor}{angle_rad}\n".encode())
```

**Update monitoring parser**:
```python
def _parse_monitor_line(self, line):
    """Parse SimpleFOC tab-separated monitoring"""
    try:
        parts = line.strip().split('\t')
        if len(parts) >= 2:
            return {
                'target': float(parts[0]),
                'angle': float(parts[1]),
                'velocity': float(parts[2]) if len(parts) > 2 else 0.0
            }
    except (ValueError, IndexError):
        return None
```

**Files to update**:
- `test/calibrate_pid.py` - Command format and parsing
- `test/debug_joystick.py` - Monitoring format
- Any other tools using serial communication

### Step 4: Test SimpleFOC Studio (2-3 hours)

**Download**:
- Web: https://studio.simplefoc.com (recommended)
- Desktop: https://github.com/JorgeMaker/SimpleFOCStudio/releases

**Test checklist**:
- [ ] Studio connects to serial port
- [ ] Motor appears in device tree
- [ ] PID sliders adjust gains successfully
- [ ] Real-time plots show angle/velocity
- [ ] Target commanding works
- [ ] Monitoring output continuous

**Test dual motor** (when motor1 configured):
- [ ] Motor 0 (command 'M') works
- [ ] Motor 1 (command 'N') works
- [ ] Both appear as separate devices in Studio

### Step 5: Validate Python Tools (1 hour)

**Run existing tests with Commander protocol**:
```bash
# Step response test with quality evaluation
python3 test/calibrate_pid.py --motor 0 --step-only
# Should output: Quality Score: XX/100

# Automated test suite
python3 test/test_suite_automated.py
# All tests should pass with new protocol
```

**Verify**:
- [ ] Commands sent in Commander format
- [ ] Monitoring parsed correctly
- [ ] Quality evaluation still works
- [ ] Step response testing functional

### Step 6: Update Documentation (2 hours)

**Files to update**:

1. `tuning/guides/ONLINE_PARAMETER_TRANSFER.md`
   - Replace custom protocol with Commander format
   - Add SimpleFOC Studio section
   - Update command reference

2. `architecture/README.md`
   - Update quick workflow to include Studio
   - Remove custom protocol references

3. `sessions/SESSION_SUMMARY.md`
   - Mark custom protocol as experimental/deprecated
   - Document transition to Commander

4. This file (`SIMPLEFOC_STUDIO_PLAN.md`)
   - Update status from "Planned" to "Completed"
   - Add results section

---

## Command Reference

### SimpleFOC Commander Format

**Motor Commands** (motor ID = 'M' for motor0, 'N' for motor1):

| Command | Description | Example |
|---------|-------------|---------|
| `M<value>` | Set target angle (rad) | `M1.57` → 90° |
| `MAP<value>` | Set angle P gain | `MAP20.0` |
| `MAI<value>` | Set angle I gain | `MAI0.0` |
| `MAD<value>` | Set angle D gain | `MAD0.5` |
| `MVP<value>` | Set velocity P gain | `MVP0.125` |
| `MVI<value>` | Set velocity I gain | `MVI10.0` |
| `MVD<value>` | Set velocity D gain | `MVD0.0` |
| `MLU<value>` | Set voltage limit | `MLU12.0` |
| `MLV<value>` | Set velocity limit | `MLV10.0` |
| `M` | Query current state | `M` → monitoring data |

**Monitoring Output** (configured via `motor.monitor_variables`):
```
target\tangle\tvelocity\n
1.57\t1.56\t0.01\n
```

### Example Session

```bash
# Connect to serial
screen /dev/ttyACM0 115200

# Configure angle controller
MAP20.0
MAI0.0
MAD0.5

# Configure velocity controller  
MVP0.125
MVI10.0
MVD0.0

# Set target
M1.57

# Query state
M
# Response: 1.57\t1.56\t0.01
```

---

## Integration with Existing Systems

### Quality Evaluation System

**Preserved for automated validation**:
- Step response testing: `calibrate_pid.py --step-only`
- Quality scoring: 0-100 scale (overshoot, settling, noise, drift, stability)
- Automated regression testing

**New workflow**:
1. **Manual tuning** with SimpleFOC Studio (interactive GUI)
2. **Validation** with quality metrics (automated scoring)
3. **Refinement** in Studio if score <70/100
4. **Persistence** to `include/pid_config.h`

### MIDI Input

**No conflicts** - MIDI and Commander use different serial streams:
- MIDI: USB MIDI interface (TinyUSB)
- Commander: Serial/CDC (text commands)

Both continue working in parallel.

### USB HID Joystick

**No conflicts** - HID output independent of serial commands.

---

## Testing Strategy

### Unit Tests

**Firmware**:
- [ ] Commander receives commands correctly
- [ ] Motor callbacks execute
- [ ] Monitoring output format valid

**Python**:
- [ ] Command formatting correct (Commander syntax)
- [ ] Monitoring parsing handles tab-separated values
- [ ] Quality metrics unchanged

### Integration Tests

**SimpleFOC Studio**:
- [ ] Connection established
- [ ] Motor control functional
- [ ] Real-time monitoring works
- [ ] Gain adjustment effective

**Python Tools**:
- [ ] `calibrate_pid.py` works with Commander
- [ ] `debug_joystick.py` parses monitoring
- [ ] Quality evaluation produces scores

**Combined**:
- [ ] Studio and Python tools interoperable
- [ ] No protocol conflicts
- [ ] Both can adjust gains without interference

---

## Risks & Mitigation

### Risk 1: Dual Motor Support

**Issue**: Commander uses separate command characters ('M', 'N') not motor ID parameter

**Mitigation**:
- Register separate callbacks for each motor
- `command.add('M', onMotor0, "motor0")`
- `command.add('N', onMotor1, "motor1")`
- Document command prefix per motor

### Risk 2: Monitoring Format Incompatibility

**Issue**: Tab-separated format differs from current `A=X.XX T=Y.YY`

**Mitigation**:
- Update Python parsers before firmware deployment
- Test parsing with mock data
- Validate all tools parse correctly before deployment

### Risk 3: SimpleFOC Studio Connection Issues

**Issue**: Serial port conflicts or Studio not detecting motor

**Mitigation**:
- Verify baud rate matches (115200)
- Check `command.verbose` mode (machine_readable for Studio)
- Test with SimpleFOC example sketches first
- Fallback: Manual serial terminal if Studio fails

### Risk 4: Loss of Custom Protocol Features

**Issue**: Custom protocol had specific features now gone

**Assessment**:
- Custom gains application: ✅ Commander has `motor.PID_velocity.P = value`
- Multi-motor support: ✅ Commander uses separate command chars
- Debug output: ✅ Commander has `motor.monitor()`
- Quality metrics: ✅ Preserved in Python tools

**Verdict**: No critical features lost

---

## Success Criteria

**Functional**:
- ✅ SimpleFOC Studio connects and controls motor
- ✅ Python tools send Commander commands successfully
- ✅ Quality evaluation system produces scores
- ✅ Real-time monitoring displays in Studio

**Code Quality**:
- ✅ 243 lines of custom code removed
- ✅ Zero custom parsing (SimpleFOC handles all)
- ✅ Standard SimpleFOC ecosystem compatibility

**Documentation**:
- ✅ Commander protocol documented
- ✅ SimpleFOC Studio workflow explained
- ✅ Updated all references to custom protocol

**Performance**:
- ✅ No degradation in FOC loop performance
- ✅ Monitoring output at expected rate
- ✅ Command latency acceptable (<100ms)

---

## Future Enhancements

**After Initial Integration**:

1. **Automated Pre-Tuning** (optional)
   - Run Ziegler-Nichols via Python
   - Apply gains via Commander
   - Validate with quality metrics
   - Refine manually in Studio

2. **Motor 1 Configuration** (when hardware ready)
   - Add `onMotor1()` callback
   - Register command 'N'
   - Test dual motor Studio support

3. **Advanced Monitoring** (if needed)
   - Add current monitoring (`_MON_CURR_Q`, `_MON_CURR_D`)
   - Add voltage monitoring (`_MON_VOLT_Q`, `_MON_VOLT_D`)
   - Custom monitoring variables

4. **Parameter Persistence** (quality of life)
   - Save tuned gains to EEPROM
   - Load on startup
   - Studio command to persist

---

## References

- **SimpleFOC Commander**: https://docs.simplefoc.com/commander_interface
- **SimpleFOC Studio**: https://docs.simplefoc.com/studio
- **SimpleFOC Motor Commands**: https://docs.simplefoc.com/motor_commands_source
- **Example Implementation**: `.pio/libdeps/.../Simple FOC/examples/motor_commands_serial_examples/`

---

## Implementation Checklist

### Preparation
- [ ] Read SimpleFOC Commander documentation
- [ ] Review example sketches
- [ ] Backup current firmware (commit to git)

### Firmware Changes
- [ ] Remove custom protocol code (243 lines)
- [ ] Add Commander include and global
- [ ] Add motor callback(s)
- [ ] Configure monitoring
- [ ] Add `command.run()` to loop
- [ ] Build and test compilation

### Python Updates
- [ ] Update command format (all tools)
- [ ] Update monitoring parser
- [ ] Test with mock serial data
- [ ] Validate quality metrics unchanged

### Testing
- [ ] SimpleFOC Studio connection
- [ ] Motor control via Studio
- [ ] Python tools with Commander
- [ ] Quality evaluation end-to-end
- [ ] Automated test suite

### Documentation
- [ ] Update ONLINE_PARAMETER_TRANSFER.md
- [ ] Update architecture README
- [ ] Update session summary
- [ ] Mark custom protocol as deprecated

### Deployment
- [ ] Git commit with clear message
- [ ] Tag release (if appropriate)
- [ ] Update project README

---

## Decision Log

**Feb 23, 2026**: Chose SimpleFOC Commander over binary protocol rework
- **Rationale**: Lower effort (8-12 hrs vs 28 hrs), official tool support, community ecosystem
- **Trade-off**: Deferred binary protocol reliability features
- **Outcome**: Will evaluate Studio extensively; may revisit binary protocol if needed

**Feb 23, 2026**: Preserve quality evaluation system
- **Rationale**: Custom protocol experiment produced valuable validation tools
- **Usage**: Automated quality gates after manual GUI tuning
- **Integration**: Python tools send Commander format, quality metrics unchanged
