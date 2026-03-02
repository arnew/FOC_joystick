# Agent Guidelines

## Philosophy

**UNIX - KISS**
- Only mandatory inventions
- Use existing libraries/tools when available
- Functions stay small (≤43 lines per AGENTS.md)
- Keep it simple, working > perfect

## Observability: Show Your Work

**When testing or diagnosing, always show all raw observations first, then derive conclusions.**

Every test report must contain:
1. **Target** — what was commanded (angle, position, value)
2. **Actual** — what was measured (sensor reading, device output)
3. **Variance** — spread/noise of measurements (stddev, min/max)
4. **Internal vs external** — device-reported vs host-measured values
5. **Acceptance criteria** — the threshold being tested against
6. **Conclusion** — PASS/FAIL derived from the above

Never report just "FAIL" or "8% pass rate" without the underlying numbers.

## Housekeeping

**The repo must stay clean at all times. Cleanup is not optional post-work.**

### Files
- `git status` must be clean before and after each work session
- Test artifacts (.json, .log) must never be committed — they belong in .gitignore
- No orphan files in the workspace root

### test/ directory structure
- **One active test suite** at the top level (currently `quality_goals_test_suite.py`)
- `test/tools/` — interactive debug/monitoring scripts (debug_joystick, hid_monitor, etc.)
- `test/unit/` — pytest-compatible unit tests and their helpers
- `test/archive/` — superseded tests kept for reference, not run
- Each subdirectory gets a README.md

### .agentic/ directory structure
- **≤7 files at root** (Miller's number). Currently: README, PURPOSE, AGENT_GUIDELINES, KNOWLEDGE_BASE, FAILED_EXPERIMENTS, FEATURE_ROADMAP, USB_STABILITY_ISSUE
- **No session logs at root** — they go in `sessions/`
- **No scripts at root** — they go in a subdirectory
- **No date-stamped files at root** — a date stamp means it's a session log
- **Knowledge articles are conclusive** — they describe what IS, not what happened
- Session logs capture findings → findings get consolidated into knowledge articles → session logs get moved to `sessions/`

## Development Model

### Git Flow
- **Branches**: `feature/*`, `hotfix/*`, `dev`, `main`, `release/*`
- **Agent commits**: Agents create commits with their own name
- **Agent pushes**: Agents push/pull directly via GitHub integration
- **Human merges**: Only humans run `git flow finish`

### Test-Driven
- All changes must pass automated tests
- Testing during development is encouraged
- Tests must pass before merging
- Use pytest with hardware markers
- CI is the authoritative test environment for this project
- Do not ask the human user to run tests for agent verification
- If local tests are run by an agent, treat them as pre-checks only; final validation is CI

### CI-First Workflow
**Agents must validate all changes via CI before considering work complete**

**Pre-Push Validation** (Use `.github/scripts/pre-push-check.sh`):
```bash
.github/scripts/pre-push-check.sh
```
This checks:
- Function size compliance (≤43 lines per AGENTS.md)
- Build success (platformio run)
- Headless tests pass (pytest)

**Post-Push CI Verification** (Use `.github/scripts/wait-for-ci.sh`):
```bash
# Push changes
git push origin <branch>

# Wait for CI and verify all workflows pass
.github/scripts/wait-for-ci.sh <commit-sha>
```
This waits for all 4 CI workflows (Build, Code Quality, Headless Test, Hardware Test) to complete and reports status.

**Mandatory CI Checks**:
- ✅ Build Firmware: Compiles successfully for all environments
- ✅ Code Quality: Function size limits enforced, no lint errors
- ✅ Headless Test: pytest suite passes (unit tests, simulators)
- ⏳ Hardware Test: Full HIL validation (may take 5-10 min, requires physical device)

**Workflow**:
1. Make changes
2. Run pre-push checks locally (optional but recommended)
3. Commit and push to dev branch
4. Use wait-for-ci.sh or gh CLI to monitor CI status
5. If CI fails, investigate logs and fix
6. Only consider task complete when all CI checks pass

**CI Failure Handling**:
- Check GitHub Actions logs: `gh run view <run-id> --log-failed`
- Fix issues locally
- Re-run pre-push checks
- Push fixes and verify CI again
- **Do not proceed** to next task until CI is green

**References**:
- Full enforcement plan: [.agentic/ci/AGENT_CI_WORKFLOW_ENFORCEMENT.md](.agentic/ci/AGENT_CI_WORKFLOW_ENFORCEMENT.md)
- Recent CI results: [.agentic/ci/CI_TEST_RESULTS_2026-02-28.md](.agentic/ci/CI_TEST_RESULTS_2026-02-28.md)

### Agent-Positive
- ✅ Agents plan and execute without asking (unless design decision)
- ✅ Agents create commits and merge code
- ✅ Agents push/pull and use GitHub integration
- ❌ Agents don't burn resources on non-critical features
- ❌ Agents stop when stuck and document state

### Human-Decides
- Only human merges branches (`git flow finish`)
- Human makes philosophy and design decisions
- Human controls hardware constraints (e.g., BOOTSEL press budget)

## Core Principles

### 1. Document Working Solutions FIRST
- **Before iterating**: Document what works
- **Before fixing**: Capture baseline behavior
- **Before refactoring**: Test and record current state
- **Example**: Manual BOOTSEL works → document, then try automation

### 2. Respect Constraints
- **Hardware limits**: Don't waste test resources
- **Time limits**: Simple working > complex perfect
- **User patience**: If trying 3x without progress, STOP and ask
- **Example**: 10 BOOTSEL presses budget → stop at 7, document findings

### 3. Manual Workarounds Are Acceptable
- **CI/CD**: Manual BOOTSEL trigger on runner is fine
- **Development**: Command-line workflows are acceptable
- **Testing**: Hardware tests can require intervention
- **Automation is nice-to-have**, not required

### 4. Incremental Testing
- **One change at a time** when hardware is involved
- **Validate before proceeding** to next iteration
- **Rollback if stuck** after 2-3 failed attempts
- **Example**: Test callback → fail → try polling → fail → STOP and document

### 5. Knowledge Base Before Iteration
- **Capture findings** in `.agentic/` hierarchy
- **Update docs** after each successful change
- **Link related docs** for navigation
- **Example**: Bootloader issue → create TINYUSB_BOOTLOADER_ISSUE.md

## Decision Framework

### When to Proceed Autonomously
- ✅ Implementation matches clear specification
- ✅ Change is low-risk (code formatting, docs, tests)
- ✅ Rollback path is trivial
- ✅ No hardware constraints involved

### When to Ask User
- ❓ Design decision required (architecture, approach)
- ❓ Multiple valid approaches exist
- ❓ User constraint unclear (BOOTSEL budget, timeline)
- ❓ Stuck after 2-3 attempts without progress

### When to STOP
- 🛑 Burning hardware test resources without validation
- 🛑 Same approach failing 3+ times
- 🛑 User constraint nearly exhausted (e.g., 8/10 BOOTSEL presses used)
- 🛑 Dependency chain too deep (yak shaving)

## Anti-Patterns to Avoid

### ❌ Chasing Perfect Automation
**Bad**: Try 5 different bootloader approaches, waste all BOOTSEL presses
**Good**: Manual BOOTSEL works → document → move to features

### ❌ Testing Without Hardware
**Bad**: Iterate DTR callbacks without device to test
**Good**: Stop at callback implementation, document for later hardware test

### ❌ Iterating Without Validation
**Bad**: Try approach A, B, C, D without testing each
**Good**: Try A → test → document → try B → test → document

### ❌ Infrastructure Over Features
**Bad**: Spend 4 hours on automated uploads
**Good**: Use manual BOOTSEL, spend 4 hours on MIDI input (actual feature)

### ❌ Ignoring Working Baseline
**Bad**: Refactor working code without tests
**Good**: Capture working baseline, test, then refactor

## Communication Style

### Progress Updates
- Be concise and factual
- Report what works, what doesn't, what's next
- Use checkboxes for status (✅ ❌ ⏳ ❓)
- Link to docs for details

### Asking for Input
- State the problem clearly
- Provide 2-3 options with tradeoffs
- Recommend an approach (or recommend STOP)
- Respect user's decision

### Documenting Failures
- Capture what was tried
- Explain why it failed
- Document workaround/solution
- Mark as LOW/HIGH priority for future work

## Example: Good Agent Behavior

**Scenario**: Bootloader reentry not working after 3 attempts

**Bad Response**:
> Let me try approach #4 with polling in setup()...

**Good Response**:
> ❌ Automated bootloader reentry failed after 3 attempts (callback, USB-first, polling).
> ✅ Manual BOOTSEL uploads work 100% reliably.
> 
> **Status**: 7/10 BOOTSEL presses used
> **Options**:
> 1. Accept manual BOOTSEL for now, document workaround → LOW priority fix later
> 2. Continue trying (risk: use remaining presses without guarantee)
> 3. Research earlephilhower bootloader docs → may find solution
> 
> **Recommendation**: Option 1 - document and move to feature development.
> 
> Your call?

## Knowledge Base Structure

```
.agentic/
├── PURPOSE.md                    (this project's goals)
├── AGENT_GUIDELINES.md          (this file)
├── KNOWLEDGE_BASE.md            (technical findings)
├── README.md                    (index/navigation)
├── ci/
│   ├── README.md                (CI status and workflows)
│   ├── GITHUB_INTEGRATION.md    (gh CLI usage)
│   └── TINYUSB_BOOTLOADER_ISSUE.md
├── testing/
│   ├── README.md
│   ├── HEADLESS_TESTING.md
│   └── TEST_RESULTS.md
└── sessions/
    ├── README.md
    └── YYYY-MM-DD_session_summary.md
```

Every folder gets a README.md index with links to related docs.
