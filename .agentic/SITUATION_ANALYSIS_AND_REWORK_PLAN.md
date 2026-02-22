# Situation Analysis & Rework Plan

**Date**: February 22, 2026  
**Status**: Session End - Action Items Identified

---

## Executive Summary

The project has achieved significant progress on **tuning evaluation** and **online parameter transfer** systems, but fundamental reliability issues with **motor control** and **host-device communication** are blocking productive development.

### Critical Issues Identified

1. **Motor Reliability**: Motor does not move reliably in response to MIDI commands
   - Step response tests show inconsistent movement (0.0° → -0.6°)
   - Even with 90° step commands, motor barely moves
   - Suggests MIDI input parsing or SimpleFOC controller integration issues

2. **Host-Device Communication**: Unreliable serial/USB communication between Python scripts and RP2040
   - Debug output sometimes missing initially (⚠ "Device not responding with debug output yet")
   - Timing-sensitive handshaking failures
   - Manual packet parsing is error-prone

3. **Code Maintainability**: Current code structure is difficult to debug and modify
   - C++ main.cpp mixes 6 concerns (FOC, MIDI, USB HID, serial commands, debugging)
   - Python scripts do manual serial parsing without error handling
   - No abstraction layers or clear module boundaries
   - Difficult to isolate issues

### Consequence

Cannot reliably:
- Test PID tuning (motor behavior is inconsistent)
- Iterate on parameters (unclear if changes have effect)
- Develop new features (communication failures cause random hangs)

---

## Current Architecture Analysis

### C++ Firmware (src/main.cpp)

**Monolithic Structure** (484 lines):
```
loop() {
  ├─ 1. FOC Control (~1 kHz)
  ├─ 2. MIDI Input (native USB MIDI, 3-byte parser)
  ├─ 2.5 Serial Command Input (PID parameter updates)
  ├─ 3. USB HID Output (~100 Hz)
  └─ 4. Debug Serial Output (~100 Hz)
}
```

**Problems**:
- MIDI parser is manual state machine (error-prone, no validation)
- SimpleFOC integration unclear (how gains are applied, feedback)
- Debug output competes with command input on same serial port
- No error handling or watchdog

### Python Tooling (test/calibrate_pid.py)

**Monolithic 1000+ lines**:
- Manual serial port detection
- Manual packet parsing (looking for "A=X.XX T=Y.YY")
- No retry/timeout handling
- Timing-dependent (sleep() everywhere)
- Monitor class hides communication details but doesn't validate

**Problems**:
- Fragile regex parsing (fails silently if format changes)
- No checksums or acknowledgments
- Assumes device always responds
- No way to detect communication hangs

---

## Root Cause Analysis

### Why Motor Doesn't Move Reliably

**Hypothesis 1: MIDI Input Not Working**
- Motor doesn't move in response to CC# commands
- SimpleFOC might not be receiving setpoint updates
- MIDI parser might be dropping messages
- No echo/acknowledgment of MIDI reception

**Hypothesis 2: SimpleFOC Controller Issue**
- Gains might not be applied correctly
- Motor might be in wrong control mode
- Encoder might not be initialized
- Velocity loop might not be connected to angle loop

**Hypothesis 3: Hardware Issue**
- Motor power insufficient
- Encoder I2C communication failing
- PWM driver not working
- Controller might be missing FOC initialization

**Cannot Debug Because**:
- No MIDI command acknowledgment
- No error messages when things fail
- No telemetry showing actual vs. expected
- Manual inspection required (can't script diagnostics)

### Why Communication is Unreliable

**Python Side**:
- Regex parsing: `r"A=([\d.-]+)\s+T=([\d.-]+)"` fails if:
  - Extra whitespace added
  - Numbers formatted differently
  - Line incomplete or duplicated
  - Port buffer overflows

**RP2040 Side**:
- Debug output doesn't wait for host to be ready
- Multiple serial routines competing (MIDI, commands, debug)
- No flow control
- USB CDC buffer might overflow

**Fundamental Issue**:
- Text-based protocol is fragile for real-time control
- No framing, checksum, or error detection
- No back-pressure mechanism

---

## Proposed Architecture Rework

### Phase 1: Communication Layer (Foundation)

#### C++ Side: Structured Serial Protocol

**Replace text-based format with binary protocol**:

```
Packet Structure:
  [SYNC:1] [LENGTH:1] [TYPE:1] [DATA:N] [CHECKSUM:1]
  
  SYNC = 0xAA (framing marker)
  TYPE:
    0x01 = MotorState (feedback)
    0x02 = MotorSetpoint (command)
    0x03 = PIDGains (command)
    0x04 = Acknowledge
    0x05 = Error
  
Example: Motor state at 1.5 rad, target 1.6 rad
  AA 08 01 3C 98 3C A0 85 D0   (8 bytes data, type=01)
```

**Benefits**:
- Self-synchronizing (can find SYNC even if data corrupted)
- Length prefix prevents overruns
- Checksum detects errors
- Type field enables extensibility
- Binary is compact and unambiguous

#### Python Side: Serial Communications Library

**Create `comms/motor_serial.py`**:

```python
class MotorSerial:
  def __init__(self, port, baudrate=115200):
    self.ser = serial.Serial(port, baudrate)
    self.lock = threading.Lock()  # Protect from concurrent access
  
  def send_command(self, cmd_type: int, data: bytes) -> bytes:
    """Send command, wait for ACK with timeout"""
    packet = self._build_packet(cmd_type, data)
    with self.lock:
      self.ser.write(packet)
      return self._read_response(timeout=1.0)  # Fail if no response
  
  def read_motor_state(self, timeout=0.1) -> MotorState:
    """Non-blocking read of latest motor state"""
    return self._parse_packet(timeout)
  
  def _build_packet(self, cmd_type, data):
    """Build binary packet with sync, length, checksum"""
    ...
  
  def _read_response(self, timeout):
    """Read with timeout, validate checksum, return parsed data"""
    ...
```

**Benefits**:
- Symmetric protocol (command/response)
- Built-in timeout handling
- Automatic validation
- Extensible for new message types
- Thread-safe for concurrent access

### Phase 2: Firmware Modularization

#### Separate Concerns

```
src/
├─ main.cpp                    # Entry point only
├─ control/
│  ├─ foc_controller.h .cpp   # SimpleFOC integration layer
│  └─ setpoint_tracker.h .cpp # Angle/velocity targets
├─ io/
│  ├─ midi_handler.h .cpp     # MIDI CC parsing (with validation)
│  ├─ serial_protocol.h .cpp   # Binary packet send/receive
│  └─ hid_joystick.h .cpp     # USB HID reports
├─ diagnostics/
│  ├─ telemetry.h .cpp        # Sampling, buffering, export
│  ├─ watchdog.h .cpp         # Deadlock detection
│  └─ error_log.h .cpp        # Persistent error tracking
└─ include/
   └─ types.h                 # Shared types, enums
```

#### Key Classes

```cpp
// control/foc_controller.h
class FOCController {
  void init(const PIDConfig& gains);
  void set_target_angle(float angle);
  void set_target_velocity(float vel);
  MOTORState loop_foc();   // Returns current state
  bool verify_initialized();
  const char* get_last_error();
};

// io/midi_handler.h
class MIDIHandler {
  bool on_byte(uint8_t byte, SetpointEvent& out);  // Returns true if complete message
  bool validate_message();
  void reset();  // For state machine recovery
};

// io/serial_protocol.h
class SerialProtocol {
  bool send_motor_state(const MotorState& state);
  bool read_command(CommandPacket& cmd, uint16_t timeout_ms);
  const char* get_last_error();
};

// diagnostics/telemetry.h
class Telemetry {
  void sample(const MotorState& state);
  void on_midi_command(uint8_t cc, uint8_t val);
  void on_foc_error(const char* error);
  const float* get_angle_buffer(uint16_t& count);  // For analysis
};
```

#### Benefits
- Clear module interfaces
- Can test each module in isolation
- Error handling at each boundary
- Diagnostics built-in, not afterthought
- Easy to add features without breaking existing code

### Phase 3: Python Testing Library

#### Create `motor_control/` package

```
test/
├─ motor_control/
│  ├─ __init__.py
│  ├─ comms.py               # Binary serial protocol
│  ├─ motor_client.py        # High-level motor API
│  ├─ calibration.py         # Tuning algorithms (refactored)
│  ├─ analysis.py            # Quality metrics
│  └─ diagnostics.py         # Fault detection
├─ test_motor_basic.py       # Connectivity, MIDI, response
├─ test_communication.py     # Packet loss, timing
├─ test_pid_tuning.py        # Calibration (refactored)
└─ calibrate_pid.py          # User-facing script (simplified)
```

#### Core API

```python
from motor_control import MotorClient, CalibrationConfig

class MotorClient:
  def __init__(self, port: str):
    self.comms = MotorSerial(port)
    self.state_buffer = []
  
  def connect(self) -> bool:
    """Verify device is responding"""
    return self.comms.ping(timeout=2.0) == ACK
  
  def set_pid_gain(self, motor: int, loop: str, param: str, value: float) -> bool:
    """Request gain change, wait for ACK"""
    return self.comms.send_command(...)
  
  def set_target(self, angle: float) -> bool:
    """Command motor to angle"""
    return self.comms.send_command(...)
  
  def read_state(self) -> MotorState:
    """Get latest state (non-blocking)"""
    return self.comms.read_motor_state()
  
  def record_session(self, duration: float) -> List[MotorState]:
    """Sample motor for duration, return all states"""
    states = []
    end_time = time.time() + duration
    while time.time() < end_time:
      state = self.read_state()
      if state:
        states.append(state)
      time.sleep(0.001)
    return states

class CalibrationTool:
  def __init__(self, client: MotorClient):
    self.client = client
  
  def step_response(self, step_size: float, baseline_cc: int) -> StepResult:
    """Refactored step response test"""
    # 1. Move to baseline
    self.client.set_target(baseline)
    states = self.client.record_session(2.0)  # Wait to settle
    
    # 2. Command step
    self.client.set_target(baseline + step_size)
    states.extend(self.client.record_session(3.0))  # Record response
    
    # 3. Analyze
    return StepAnalyzer(states).analyze()
```

---

## Implementation Roadmap

### Week 1: Communication Foundation
- [ ] Design binary protocol (document format)
- [ ] Implement C++ `SerialProtocol` class
- [ ] Implement Python `MotorSerial` class
- [ ] Test packet integrity (corruption, framing)
- [ ] Commit: "refactor: Binary protocol for reliable communication"

### Week 2: Firmware Modularization
- [ ] Extract `FOCController` from main.cpp
- [ ] Extract `MIDIHandler` with validation
- [ ] Extract `Telemetry` for diagnostics
- [ ] Add `Watchdog` for deadlock detection
- [ ] Refactor main.cpp to use modules
- [ ] Verify motor still works (regression test)
- [ ] Commit: "refactor: Modularize firmware into clear layers"

### Week 3: Python Library
- [ ] Create `motor_control/` package structure
- [ ] Implement `MotorClient` API
- [ ] Refactor `calibrate_pid.py` to use MotorClient
- [ ] Add basic unit tests
- [ ] Commit: "refactor: Extract motor control library"

### Week 4: Diagnostics & Testing
- [ ] Implement `Telemetry` telemetry capture
- [ ] Create `test_motor_basic.py` (connectivity, MIDI echo)
- [ ] Create `test_communication.py` (reliability)
- [ ] Add error recovery (automatic retry, reconnect)
- [ ] Implement `Watchdog` for stuck motor detection
- [ ] Commits: Multiple for each diagnostic tool

### Validation Checkpoints

**End of Week 1**: Binary protocol working reliably
- Test: Send 100 packets, 0 corruption
- Test: Detect single-bit error
- Test: Recover from framing loss

**End of Week 2**: Firmware modules functional
- Test: Motor still responds to MIDI
- Test: PID gains still update via serial
- Test: Telemetry captures data correctly
- Test: Watchdog detects hung FOC loop

**End of Week 3**: Python library API functional
- Test: `client.set_target(angle)` moves motor
- Test: `client.read_state()` consistent with device
- Test: Calibration uses MotorClient without regression

**End of Week 4**: Full diagnostics working
- Test: Can detect stuck motor automatically
- Test: Can script communication tests
- Test: Can recover from transient failures

---

## Benefits of This Rework

### For Development
- **Debuggability**: Each module can be tested independently
- **Maintainability**: Clear interfaces, no spaghetti code
- **Extensibility**: Easy to add new message types (e.g., temperature, current)
- **Reliability**: Error detection at every layer

### For Testing
- **Automation**: Python library enables scripted testing
- **Repeatability**: Binary protocol ensures consistent behavior
- **Coverage**: Can test edge cases (corruption, timeouts, lost packets)
- **Diagnostics**: Telemetry reveals what's happening

### For Tuning
- **Confidence**: Know communication is reliable before changing gains
- **Iteration Speed**: No more guess-and-check; can log effect of each change
- **Robustness**: Works reliably across temperature, voltage conditions

---

## Estimated Effort

- **Architecture Design**: 4 hours
- **C++ Implementation**: 8 hours
- **Python Implementation**: 6 hours
- **Testing & Validation**: 6 hours
- **Documentation**: 4 hours

**Total**: ~28 hours of focused development

---

## Risk Mitigation

### Risk: Breaking existing functionality
**Mitigation**: 
- Keep old code in parallel during transition
- Each module tested before integration
- Motor must still move at end of each week

### Risk: Scope creep
**Mitigation**:
- Freeze feature list during rework
- Weekly checkpoints to verify progress
- Stop and re-plan if blockers found

### Risk: New bugs in refactored code
**Mitigation**:
- Comprehensive automated tests
- Gradual migration (one module at a time)
- Regression testing at each checkpoint

---

## Success Criteria

After rework, the system should:

✅ **Reliable**: 99%+ packet success rate (1000 packets, 0-1 loss)  
✅ **Debuggable**: Can output diagnostic logs showing exactly what motor received  
✅ **Maintainable**: New developer can understand code structure in <1 hour  
✅ **Testable**: Can run automated test suite validating motor behavior  
✅ **Tunable**: Can rapidly iterate PID gains with high confidence  

### Validation Tests

```python
# test_motor_basic.py
def test_wifi_connectivity():
    """Motor responds to ping within 100ms"""
    
def test_midi_echo():
    """Send MIDI CC, verify motor acknowledges"""
    
def test_pid_response():
    """Step response is stable and reproducible"""
    
def test_packet_integrity():
    """100 packets sent/received with 0 corruption"""
    
def test_error_recovery():
    """Motor recovers from transient UART error"""
```

---

## Current Session Summary

**Accomplishments**:
- ✅ Tuning quality evaluation system (87.6/100 baseline)
- ✅ Online PID parameter transfer (10s iteration)
- ✅ Complete documentation
- ✅ Configurable step response tests

**Blockers Identified**:
- ❌ Motor doesn't move reliably
- ❌ Communication is flaky
- ❌ Can't debug due to code monolithicity

**Next Session**:
- Implement architecture rework
- Start with communication layer (binary protocol)
- Validate motor works reliably before continuing

---

## Conclusion

The project has **strong momentum** on tuning methodology but is **blocked by infrastructure issues**. A focused rework of the communication and firmware architecture will:

1. **Eliminate the blocker** (unreliable motor control)
2. **Enable automation** (scripted testing)
3. **Improve maintainability** (clear module structure)
4. **Build confidence** (validation at each step)

The rework is **justified** because:
- Current code is too fragile for productive iteration
- Issues are structural (architecture), not tactical (bugs)
- Benefits extend beyond this project (reusable library)

**Recommendation**: Schedule 4-week block for rework, then resume tuning work with infrastructure complete.
