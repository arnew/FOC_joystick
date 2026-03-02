# GitHub Integration & Agent Workflow

## Authentication & Capability Inventory

```bash
gh auth status
# Output (verified Feb 27, 2026):
# Logged in to github.com as arnew (keyring)
# Git operations protocol: ssh
# Token scopes: admin:public_key, gist, read:org, repo
```

All commands below are verified working on Windows PowerShell.

### Available Commands

| Command | Purpose | Status | Notes |
|---------|---------|--------|-------|
| `gh run list` | See recent CI runs | ✓ | Replaces web scraping |
| `gh run view ID` | Get run details | ✓ | Can show jobs and steps |
| `gh run view ID --log-failed` | Read failure logs | ✓ | Instant diagnosis |
| `gh run rerun ID --failed` | Retry failed jobs only | ✓ | No re-push needed |
| `gh run watch ID` | Block until completion | ✓ | Windows: alternate buffer quirk |
| `gh api repos/arnew/FOC_joystick/...` | Raw REST API | ✓ | For complex queries |
| `gh issue create` | Track bugs/features | ✓ | Enabled on repo |
| `gh pr create` | Open pull requests | ✓ | For code review before merge |
| `gh workflow run` | Trigger on demand | ✓ | All 3 workflows support `workflow_dispatch` |

---

## Develop → Validate Cycle

**For every feature/bugfix:**

### 1. Develop on feature branch
```bash
git flow feature start my-feature
# ... code/commit/test locally
```

### 2. Push & auto-trigger CI
```bash
git add -A
git commit -m "feat: description"
git push origin feature/my-feature
# → All 3 CI workflows trigger automatically
```

### 3. Monitor workflow status
```bash
# Get list of recent runs
gh run list --repo arnew/FOC_joystick --limit 10

# Find your run (look for matching commit message or branch)
# ID will be shown in first column (databaseId), e.g. 22477466804
```

### 4. Watch until completion
**Option A (blocking):**
```bash
gh run watch 22477466804 --repo arnew/FOC_joystick --exit-status
# Waits for completion, exits with 0 (pass) or 1 (fail)
```

**Option B (polling):**
```bash
gh api repos/arnew/FOC_joystick/actions/runs/22477466804 | \
  python -c "import sys,json; d=json.load(sys.stdin); print(d['status'], d.get('conclusion','pending'))"
# Output: "completed success" or "in_progress None"
```

### 5. Diagnose failures
```bash
# View failed steps and logs
gh run view 22477466804 --repo arnew/FOC_joystick --log-failed | tail -50

# Or get full JSON for step-by-step inspection
gh api repos/arnew/FOC_joystick/actions/runs/22477466804/jobs | \
  python -c "import sys,json; d=json.load(sys.stdin); [print(j['name'], j['status'], j.get('conclusion','pending')) for j in d['jobs']]"
```

### 6. Fix issues
```bash
# If CI failed: identify root cause from logs
# Fix code locally and push again
git add -A
git commit -m "fix: address CI failure"
git push
# → CI re-triggers automatically
```

### 7. Verify all green
```bash
# Run list should show ✓ for Code Quality, Headless Test, Hardware Test
# (Hardware Test requires physical device on runner — may show other errors)
gh run list --repo arnew/FOC_joystick --limit 3
```

### 8. Complete feature
```bash
# Only when CI is green (or fails only due to hardware setup)
git flow feature finish my-feature
# → Human merges to dev
```

---

## On-Demand Testing

**Trigger a specific workflow without pushing:**

```bash
# Rerun only failed jobs from a previous run
gh run rerun 22477466804 --repo arnew/FOC_joystick --failed

# Trigger workflow manually (workflow_dispatch)
gh workflow run "Code Quality" --repo arnew/FOC_joystick -r feature/my-feature
gh workflow run "Headless Test" --repo arnew/FOC_joystick -r feature/my-feature
gh workflow run "Hardware Test" --repo arnew/FOC_joystick -r feature/my-feature
```

---

## Issue Tracking

**Create an issue for a known problem or feature:**

```bash
# Simple issue
gh issue create --repo arnew/FOC_joystick \
  --title "Motor noise on axis Y" \
  --body "Observed high-frequency jitter. See .agentic/FAILED_EXPERIMENTS.md"

# Reference in commits
git commit -m "fix(motor_control): reduce PWM frequency

Fixes #42 (motor noise)"
```

**List open issues:**
```bash
gh issue list --repo arnew/FOC_joystick
```

---

## CI Workflows Explained

### Code Quality (ubuntu-latest, ~2m)
1. **Check function sizes** — awk scan of `src/*.cpp`, fail if any >43 lines (AGENTS.md compliance)
2. **Build firmware** — `platformio run -e pico_1motor_endless` (verify compilation)

**Failure → Fix → Push → Re-trigger automatically**

### Headless Test (ubuntu-latest, ~15s)
1. **Set up Python 3.11** — via `actions/setup-python`
2. **Install pytest, pyserial** — via pip
3. **Run pytest** — `pytest -q` (all test_*.py files)
   - Simulator tests (3): `test_sim_device.py` tests axis profiles
   - Hardware test gated by `RUN_HARDWARE_TESTS=1` env var (skipped in headless)
   - Result: typically 3 passed, 1 skipped

**Failure → Diagnose from pytest output → Fix → Push**

### Hardware Test ([self-hosted, hardware], ~25s + device wait)
1. **Setup Python venv** — creates `$HOME/ci-venv` (works around PEP 668 on Debian)
2. **Install platformio, pyserial** — into venv
3. **Build firmware** — `platformio run -e pico_1motor_endless`
4. **Upload to device** — `platformio run --target upload` (requires RP2040 in BOOTSEL mode)
   - **Current blocker**: No device in BOOTSEL on runner. Picotool times out.
5. **Run hardware tests** — `./test/run_ci_tests.sh` (serial port, MIDI, joystick over USB HID)
6. **Upload artifacts** — logs and JSON results to GitHub

**Status (Feb 27, 2026)**: Upload step fails (no device); test steps skipped.

---

## Troubleshooting

| Issue | Check |
|-------|-------|
| `gh: command not found` | Add to PATH: `$env:PATH += ";C:\Program Files\GitHub CLI"` |
| `gh auth status` shows no account | Run `gh auth login` (Windows will open browser) |
| `ERROR: HTTP 404` on `gh run view ID` | ID wrong format; use databaseId from `gh run list --json databaseId` |
| Workflow doesn't exist | Verify YAML in `.github/workflows/` and commit is pushed |
| `workflow_dispatch` not available | Add `workflow_dispatch:` to triggers in workflow YAML (fixed on all 3 in Feb 27 push) |
| Hardware test times out forever | Device not in BOOTSEL; physically press RP2040 BOOTSEL button before trigger |

---

## Summary for Agents

**Every push → CI auto-runs → Monitor with `gh run list` → Check logs with `gh run view --log-failed` → Fix → Push → Repeat**

Quick aliases for shell:
```bash
# Add to shell profile to speed up workflow
alias gh-status='gh run list --repo arnew/FOC_joystick --limit 5'
alias gh-watch='gh run watch $(gh run list --repo arnew/FOC_joystick --limit 1 --json databaseId | jq -r ".[0].databaseId") --exit-status'
```
