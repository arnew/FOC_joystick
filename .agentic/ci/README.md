# CI/CD & GitHub Integration

Tools and workflows for automated testing, cloud validation, and agentic GitHub operations.

## Quick Navigation

- [GitHub Integration & Development Workflow](GITHUB_INTEGRATION.md) — How agents use `gh` CLI for develop/push/validate cycle, CI monitoring, and issue tracking
- [Agent CI Workflow Enforcement](AGENT_CI_WORKFLOW_ENFORCEMENT.md) — Comprehensive plan for forcing agents to validate all changes via CI/CD (5-phase implementation with automation scripts)
- [CI Test Results 2026-02-28](CI_TEST_RESULTS_2026-02-28.md) — Complete CI validation results from aircraft profiles implementation

## Current Infrastructure

**Validation policy**:
- CI is the source of truth for test pass/fail.
- The human user cannot run tests for agent tasks; agents must rely on CI results.
- Local runs by agents are optional pre-checks, not acceptance criteria.

**Workflows** (3 tiers + 1 manual):
- **Code Quality** (`ubuntu-latest`): function size check + PIO build
- **Headless Test** (`ubuntu-latest`): pytest unit tests, simulator, no hardware  
- **Hardware Test** (`[self-hosted, hardware]`): build → upload → HIL tests (physical device required) — runs all tests on push/PR
- **Manual Hardware Test** (`[self-hosted, hardware]`): selective test execution for rapid debugging

**Tools**:
- `gh` CLI — all GitHub operations (auth as `arnew` with `repo` scope)
- `workflow_dispatch` — on-demand CI triggers (all workflows support this)
- `git-flow` — branch management (feature/*, dev, main, release/*)

## Rapid Iteration with Manual Tests

For debugging failed tests without running the full suite:

**Trigger manual test run** (GitHub web UI):
1. Go to Actions → Manual Hardware Test
2. Click "Run workflow"
3. Select tests to run: `connectivity position midi scaling sweep dynamics`
4. Optionally skip build/upload if firmware is already deployed

**Trigger via CLI**:
```bash
# Run only MIDI and sweep tests
gh workflow run manual-hardware-test.yml \
  --ref dev \
  -f tests="midi sweep"

# Skip build (use existing firmware)
gh workflow run manual-hardware-test.yml \
  --ref dev \
  -f tests="connectivity midi" \
  -f skip_build=true
```

**Available tests**:
- `connectivity` — System identification (firmware, config)
- `position` — Motor initial position check
- `midi` — Motor response to MIDI commands
- `scaling` — Joystick output scaling
- `sweep` — Motor sweep range and tracking
- `dynamics` — High-speed dynamics (requires --enable-monitor)

**Local testing (agent pre-check only)**:
```bash
python3 test/quality_goals_test_suite.py             # Run all tests
python3 test/quality_goals_test_suite.py --tests A B # Run specific tests
```

Do not require or request local test execution from the human user. Use CI/manual CI workflows for verification.

## Self-Hosted Runner Requirements

The hardware test runner requires specific system permissions for device access:

**User Group Memberships** (for runner user, e.g., `ghr`):
```bash
sudo usermod -aG dialout ghr    # Serial port access (/dev/ttyACM*)
sudo usermod -aG audio ghr      # ALSA MIDI sequencer (/dev/snd/seq) - REQUIRED for pygame.midi
sudo usermod -aG plugdev ghr    # USB device access
```

**After group changes**, restart the runner service:
```bash
sudo systemctl restart actions.runner.*.service
```

**Verify access**:
```bash
id ghr  # Should show: dialout, audio, plugdev in groups
sudo -u ghr ls -l /dev/ttyACM* /dev/snd/seq  # Should succeed
```

**Why audio group?** The hardware tests use `pygame.midi` for native USB MIDI communication with the RP2040. Without `audio` group membership, pygame finds 0 MIDI devices and motor sweep tests fail.

**Common Issues**:
- **ALSA errors** (`Unknown SEQ default`): Install `alsa-utils` and restart ALSA: `sudo apt install alsa-utils && sudo systemctl restart alsa-restore`
- **Runner not seeing new groups**: Must restart runner service after usermod: `sudo systemctl restart actions.runner.*.service`
- **Verify runner groups at runtime**: `ps aux | grep Runner.Listener` then `cat /proc/<PID>/status | grep Groups`

## Status (Feb 27, 2026)

✅ Code Quality: passing  
✅ Headless Test: passing (pytest 3 passed, 1 skipped)  
⚠️ Hardware Test: blocked on device setup (no RP2040 in BOOTSEL mode on runner)

## See Also

- [architecture/](../architecture/) — overall project structure
- [testing/](../testing/) — test results, test findings, headless testing guide
