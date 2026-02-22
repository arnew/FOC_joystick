# Instructions to AI Agents

**Purpose**: USB HID joystick controller for Flight Simulator with dual motorized axes and MIDI input.

**Development Model**: 
Git-flow. All changes must be developed in feature/hotfix branches, development is maintained in dev, releases are kept in main, releases are prepared in git flow.
Test-driven. All changes must pass automated tests before continuation. Testing is wanted during development, before merging a branch or creating a release tests must be successful.
Agent-positive. The agent creates commits and merges code using its own name in git itself.

## Repository Structure

```
.agentic/              # Knowledge base for agents
  ├─ PLANNING.md      # 6-phase implementation architecture
  ├─ QUICKSTART.md    # Build, upload, test instructions
  ├─ TEST_RESULTS.md  # Latest test status & metrics
  └─ TESTING_FINDINGS.md  # Hardware issues & fixes

.github/copilot-instructions.md  # Coding & style guidelines

src/
  ├─ main.cpp         # Motor control, MIDI handler, USB HID
  ├─ config.h         # Axis profiles, motor configurations

test/
  ├─ test_suite_automated.py  # 5 automated tests (system ID, motor response, etc.)
  ├─ debug_joystick.py        # Real-time monitor
  ├─ debug_midi.py            # Interactive MIDI sender
  └─ README.md                # Test documentation

platformio.ini         # Build for pico_1motor_endless, pico_1motor_limited, pico_2motor_limited
```

## Quick Workflow

1. **Build**: `platformio run -e pico_1motor_endless`
2. **Upload**: `platformio run -e pico_1motor_endless --target upload`
3. **Test**: `python3 test/test_suite_automated.py`
4. **Debug**: `python3 test/debug_joystick.py` (monitor) + `python3 test/debug_midi.py` (control)

## Key Facts

- **Hardware**: RP2040 + SimpleFOC + AS5600 encoder
- **Protocol**: MIDI CC @ 31250 baud (USB dual CDC)
- **Architecture**: 6 phases (config → motors → MIDI → scaling → USB → integration)
- **Testing**: Automated suite verifies system ID, motor response, joystick output

See [.agentic/PLANNING.md](./.agentic/PLANNING.md) for full specifications.