# Tuning Guides

User-facing how-to documentation for motor calibration.

---

## Documents

- [DUAL_LOOP_TUNING.md](DUAL_LOOP_TUNING.md) - How to tune dual-loop PID system
- [ONLINE_PARAMETER_TRANSFER.md](ONLINE_PARAMETER_TRANSFER.md) - Real-time parameter adjustment guide

---

## Quick Start

**First time tuning?**
1. Read [DUAL_LOOP_TUNING.md](DUAL_LOOP_TUNING.md) for strategy
2. Run: `python3 test/calibrate_pid.py --motor 0`
3. If motor is noisy, see [../../quality/QUICK_FIX.md](../../quality/QUICK_FIX.md)

**Need faster iteration?**
1. Use [ONLINE_PARAMETER_TRANSFER.md](ONLINE_PARAMETER_TRANSFER.md)
2. Adjust gains via serial commands (no recompile)
3. Test immediately with `--step-only` mode

---

## Workflow

```
Automated Calibration (45s per test)
  ↓
If noisy → Apply quick fixes (Manual)
  ↓
Fine-tune with Online Parameters (10s per test)
  ↓
Validate with Quality Evaluation (87+/100 target)
```
