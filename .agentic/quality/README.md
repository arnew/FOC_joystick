# Quality Evaluation

Motor performance evaluation, diagnostics, and fixes.

---

## Documents

- [QUALITY_EVALUATION.md](QUALITY_EVALUATION.md) - Quality scoring system (implementation & analysis)
- [QUICK_FIX.md](QUICK_FIX.md) - Step-by-step fix guide for noisy motor
- [FIX_RESULTS.md](FIX_RESULTS.md) - Results after applying fixes (28.4 → 72.9/100)

---

## Quality Score

**0-100 Scale** combining 5 metrics:
1. Overshoot (peak deviation from target)
2. Settling time (time to reach steady-state)
3. Position noise (standard deviation)
4. Drift (mean error from target)
5. Stability (% time within tolerance)

**Rating Buckets**:
- 90-100: EXCELLENT
- 70-89: GOOD
- 50-69: FAIR
- 0-49: POOR

---

## Current Status

**Latest Result**: 72.9/100 GOOD (Feb 22, 2026)

**Evolution**:
- Initial: 28.4/100 POOR (noisy, unstable)
- After fixes: 72.9/100 GOOD (stable positioning)

See [FIX_RESULTS.md](FIX_RESULTS.md) for details.

---

## Quick Fix Workflow

Motor noisy or unstable?
1. Read [QUICK_FIX.md](QUICK_FIX.md)
2. Apply manual fixes (reduce gains, adjust ramp)
3. Verify with quality evaluation
4. Target 70+/100 for stable operation
