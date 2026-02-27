# PID Tuning System

Documentation for motor PID calibration, including implementation details and user guides.

---

## Organization

- [implementation/](implementation/) - Technical implementation details
- [guides/](guides/) - User-facing how-to documentation

---

## Quick Start

**Need to tune a motor?**
→ Start with [guides/DUAL_LOOP_TUNING.md](guides/DUAL_LOOP_TUNING.md)

**Want real-time parameter adjustment?**
→ Use [guides/ONLINE_PARAMETER_TRANSFER.md](guides/ONLINE_PARAMETER_TRANSFER.md)

**Understanding the system?**
→ Read [implementation/DUAL_LOOP_IMPLEMENTATION.md](implementation/DUAL_LOOP_IMPLEMENTATION.md)

---

## Current System

**Architecture**: Dual-loop nested control
- Outer loop: P-only angle controller
- Inner loop: PID velocity controller

**Implementation Status**: ✅ Complete (Feb 22, 2026)

**Tools Available**:
- Automated calibration: `test/calibrate_pid.py`
- Online parameter transfer via serial commands
- Quality evaluation with 0-100 scoring

---

## Evolution

1. **Single-loop** (archived) - Initial P-only angle control
2. **Dual-loop** (current) - Nested P_angle + PID_velocity
3. **Planned enhancements** - See [implementation/CALIBRATION_PLAN.md](implementation/CALIBRATION_PLAN.md)
