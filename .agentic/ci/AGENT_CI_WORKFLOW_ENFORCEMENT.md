# Agent CI Workflow Enforcement Plan

**Purpose**: Force all agent development to validate via CI/CD before considering work complete  
**Status**: Planning  
**Priority**: HIGH — Prevents broken code from accumulating  

---

## Problem Statement

**Current State**:
- Agents can push code without waiting for CI results
- No automated enforcement of AGENTS.md guidelines
- Manual verification required by humans
- Code quality issues discovered days later

**Desired State**:
- All agent changes validated by CI automatically
- Agents cannot proceed until CI passes
- AGENTS.md compliance enforced by machines, not documentation
- Humans only intervene for design decisions, not quality checks

---

## Core Principle (from AGENTS.md)

> "Test-driven. A test is only considered successful when run on the CI."  
> "CI is the authoritative test environment for this project"

**Agent Workflow**:
1. Make changes in feature/ or dev branch
2. Run **local pre-checks** (fast feedback)
3. Commit and push
4. **Wait for CI to complete** (authoritative validation)
5. Check CI status via `gh run list`
6. **Only proceed if all checks pass**
7. If CI fails, fix and repeat from step 2

---

## Implementation Strategy

### Phase 1: Local Pre-Checks (Immediate — 1 hour)

**Goal**: Fast feedback before push, reduce CI failures

**File**: `.github/scripts/pre-push-check.sh`

```bash
#!/bin/bash
set -e

echo "🔍 Running pre-push checks..."

# 1. Function size compliance
echo "  Checking function sizes (AGENTS.md)..."
python3 - <<'PY'
import pathlib, re, sys
max_lines = 43
func_start = re.compile(r'^\s*[\w:<>~*&\s]+\s+[\w:~]+\s*\([^;]*\)\s*\{\s*$')
control_start = re.compile(r'^\s*(if|for|while|switch|else|do|catch)\b')
failures = []
for path in sorted(pathlib.Path('src').glob('*.cpp')):
    lines = path.read_text(encoding='utf-8').splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if func_start.match(line) and not control_start.match(line):
            start = i
            sig = line.strip()
            depth = line.count('{') - line.count('}')
            i += 1
            while i < len(lines) and depth > 0:
                depth += lines[i].count('{') - lines[i].count('}')
                i += 1
            end = i - 1
            body_len = max(0, end - start - 1)
            if body_len > max_lines:
                failures.append(f"FAIL: {path}:{start + 1} - {sig} ({body_len} lines, max {max_lines})")
        else:
            i += 1
if failures:
    print('\n'.join(failures))
    sys.exit(1)
print('    ✅ All functions ≤43 lines')
PY

# 2. Build check
echo "  Building firmware..."
platformio run -e pico_1motor_endless -q
echo "    ✅ Build successful"

# 3. Headless tests
echo "  Running headless tests..."
python -m pytest test/ -q
echo "    ✅ Tests passed"

echo "✅ All pre-checks passed"
echo "📤 Proceeding with push - CI will run full validation"
```

**Installation** (for agents):
```bash
chmod +x .github/scripts/pre-push-check.sh
ln -sf ../../.github/scripts/pre-push-check.sh .git/hooks/pre-push
```

**Usage**:
- Runs automatically before `git push`
- Agent can override with `git push --no-verify` (but shouldn't)
- Exits with error if any check fails

---

### Phase 2: CI Status Verification (Immediate — 30 min)

**Goal**: Agent must check CI status after push

**File**: `.github/scripts/wait-for-ci.sh`

```bash
#!/bin/bash
set -e

BRANCH=$(git rev-parse --abbrev-ref HEAD)
COMMIT=$(git rev-parse HEAD | cut -c1-7)

echo "⏳ Waiting for CI to start for $BRANCH @ $COMMIT..."
sleep 10  # Give GitHub Actions time to trigger

# Find the latest run for this commit
RUN_ID=$(gh run list --branch "$BRANCH" --limit 5 --json databaseId,headSha \
  --jq ".[] | select(.headSha | startswith(\"$(git rev-parse HEAD)\")) | .databaseId" \
  | head -1)

if [ -z "$RUN_ID" ]; then
  echo "❌ No CI run found for this commit"
  echo "   Check manually: gh run list --branch $BRANCH"
  exit 1
fi

echo "✅ CI run started: $RUN_ID"
echo "📊 Watching CI progress..."

# Watch and wait for completion
gh run watch "$RUN_ID"

# Check final status
STATUS=$(gh run view "$RUN_ID" --json conclusion --jq '.conclusion')

if [ "$STATUS" = "success" ]; then
  echo "✅ CI PASSED - All checks successful"
  exit 0
elif [ "$STATUS" = "failure" ]; then
  echo "❌ CI FAILED - Checking logs..."
  gh run view "$RUN_ID" --log-failed
  exit 1
else
  echo "⚠️ CI status: $STATUS"
  exit 1
fi
```

**Usage** (by agents):
```bash
git push origin dev
.github/scripts/wait-for-ci.sh
```

**Integration with Agent Workflow**:
- Agent pushes changes
- Agent runs `wait-for-ci.sh`
- Script blocks until CI completes
- Script exits 0 (success) or 1 (failure)
- Agent checks exit code before proceeding

---

### Phase 3: Branch Protection Rules (Next Session — 15 min)

**Goal**: Prevent merging broken code

**GitHub Settings** → **Branches** → **Branch protection rule** for `dev`:

```yaml
Branch name pattern: dev

Require status checks to pass before merging:
  ✅ Require branches to be up to date before merging
  
  Required checks:
    - Build Firmware / build
    - Code Quality / function-size-check
    - Headless Test / pytest-headless
    # Hardware Test is optional (manual trigger)

Require linear history: ✅
Allow force pushes: ❌
Allow deletions: ❌
```

**For `main` branch**:
```yaml
Branch name pattern: main

# Same as dev, plus:
Require pull request reviews: ✅ (1 reviewer)
Dismiss stale reviews: ✅
Require review from Code Owners: ✅
```

**Effect**:
- Agents cannot push broken code to dev (CI must pass first)
- PRs to main require human review
- Force-push disabled (prevents history rewriting)

---

### Phase 4: Automated Test Expansion (Future — 4-6 hours)

**Goal**: Catch more issues automatically

**New Tests Needed**:

1. **MIDI Protocol Tests** (`test/test_midi_protocol.py`)
   ```python
   def test_all_a320_midi_ccs():
       """Test all 5 A320 MIDI CCs are recognized"""
       for cc in [7, 11, 64, 2, 32]:
           # Send CC, verify motor responds
   
   def test_cessna_midi_ccs():
       """Test all 4 Cessna MIDI CCs"""
   
   def test_glider_midi_ccs():
       """Test all 2 Glider MIDI CCs"""
   
   def test_invalid_cc_ignored():
       """Verify unknown CCs don't crash firmware"""
   ```

2. **Profile Switching Tests** (`test/test_profiles.py`)
   ```python
   @pytest.mark.parametrize("profile", ["A320", "CESSNA", "GLIDER"])
   def test_profile_builds(profile):
       """Verify each profile compiles"""
       # Temporarily edit config.h
       # Run platformio build
       # Verify success
   ```

3. **Memory Usage Tests** (`test/test_memory.py`)
   ```python
   def test_firmware_size_under_limit():
       """Verify firmware fits in 2MB flash"""
       elf_size = get_firmware_size()
       assert elf_size < 2_000_000, f"Firmware too large: {elf_size} bytes"
   ```

**CI Integration**:
- Add new test suite to `headless-test.yml`
- Run on every commit
- Block merge if any test fails

---

### Phase 5: Agent Instruction Update (Immediate — 30 min)

**Goal**: Make CI-first workflow explicit in agent docs

**File**: `.agentic/AGENT_GUIDELINES.md`

**Add Section**:

```markdown
## CI-First Development Workflow

### Every Change Must Pass CI

1. **Make changes** in feature/ or dev branch
2. **Run local pre-checks**:
   ```bash
   .github/scripts/pre-push-check.sh
   ```
3. **Commit and push**:
   ```bash
   git add .
   git commit -m "feat: description"
   git push origin dev
   ```
4. **Wait for CI** (required):
   ```bash
   .github/scripts/wait-for-ci.sh
   ```
5. **Check results**:
   - ✅ If CI passes → Document changes, proceed to next task
   - ❌ If CI fails → Fix immediately, repeat from step 2

### Do NOT Proceed If CI Fails

- ❌ Do not commit more changes on top of failing CI
- ❌ Do not ask human to "check CI later"
- ❌ Do not skip CI verification
- ✅ Fix the failure first, then continue

### CI Check Status

```bash
# Quick status
gh run list --branch dev --limit 5

# View specific run
gh run view <run-id>

# View failure logs
gh run view <run-id> --log-failed
```

### Local Tests Are Pre-Checks Only

Per AGENTS.md:
> "If local tests are run by an agent, treat them as pre-checks only;  
> final validation is CI"

- Local tests → Fast feedback, prevent obvious failures
- CI tests → Authoritative, determines success/failure
- Do not ask user to run tests
```

---

## Enforcement Checklist

### Immediate Actions (This Session):

- [x] Create `CI_TEST_RESULTS_2026-02-28.md` with findings
- [x] Create `AGENT_CI_WORKFLOW_ENFORCEMENT.md` (this file)
- [ ] Create `.github/scripts/pre-push-check.sh`
- [ ] Create `.github/scripts/wait-for-ci.sh`
- [ ] Update `.agentic/AGENT_GUIDELINES.md` with CI-first workflow
- [ ] Commit and push all documentation

### Next Session Actions:

- [ ] Enable branch protection on `dev` (requires repo admin)
- [ ] Add pre-push hook to repository
- [ ] Test agent workflow with deliberate failure
- [ ] Verify CI catches and blocks failure

### Future Actions:

- [ ] Expand test suite (MIDI, profiles, memory)
- [ ] Add automated hardware test trigger (if possible)
- [ ] Create CI dashboard/badge for README
- [ ] Document exceptions (when human can override)

---

## Success Criteria

**CI Workflow is Enforced When**:

1. ✅ Agents run local pre-checks before every push
2. ✅ Agents wait for CI completion after push
3. ✅ Agents fix failures immediately (within same session)
4. ✅ Broken code cannot reach dev branch (branch protection)
5. ✅ Function size violations caught automatically
6. ✅ Build failures caught before merge
7. ✅ Test failures block further development

**Measurement**:
- Track CI failure rate on dev (target: <10%)
- Track time-to-fix for CI failures (target: <30 minutes)
- Track commits with passing CI (target: >90%)

---

## Exceptions & Edge Cases

### When Human Can Override:

1. **Emergency Hotfix**
   - Critical production issue
   - Human can force-push to hotfix/ branch
   - Must document reason in commit message

2. **CI Infrastructure Failure**
   - GitHub Actions down
   - Runner offline
   - Human verifies locally, documents in commit

3. **Known False Positive**
   - Test is flaky (e.g., timing-sensitive)
   - Issue documented in test file
   - Human approves merge with comment

### When Agent Should Stop:

1. **CI Fails 3+ Times**
   - Stop iterating
   - Document findings in `.agentic/sessions/`
   - Ask human for guidance

2. **Unclear Failure**
   - Error message ambiguous
   - Cannot reproduce locally
   - Capture logs, ask human

3. **Resource Constraints**
   - CI queue too long (>10 minutes)
   - Hardware test requires manual intervention
   - Document state, wait for human

---

## Integration with Existing Processes

### Git Flow Compatibility:

```bash
# Feature development
git flow feature start add-new-profile
# ... make changes ...
.github/scripts/pre-push-check.sh  # Local check
git flow feature publish            # Push to remote
.github/scripts/wait-for-ci.sh     # Wait for CI
# If CI passes:
git flow feature finish             # Merge to dev (human only)
```

### Agent Commits:

- Agent uses its own author name/email
- Commit messages follow conventional commits format
- Each commit includes CI reference in body (optional):
  ```
  feat: add glider profile support
  
  - Add GLIDER_CONFIG array
  - Update ACTIVE_CONFIG switching
  
  CI-Run: https://github.com/user/repo/actions/runs/12345
  ```

---

## Tools & Scripts Summary

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `pre-push-check.sh` | Fast local validation | Before every push |
| `wait-for-ci.sh` | Block until CI completes | After every push |
| `gh run list` | Check CI status | Monitor progress |
| `gh run view --log-failed` | Debug failures | When CI fails |

**Installation**:
```bash
# Make scripts executable
chmod +x .github/scripts/*.sh

# Set up pre-push hook (optional)
ln -sf ../../.github/scripts/pre-push-check.sh .git/hooks/pre-push
```

---

## Knowledge Base Integration

**New Files**:
- `.agentic/ci/CI_TEST_RESULTS_2026-02-28.md` — Latest test results
- `.agentic/ci/AGENT_CI_WORKFLOW_ENFORCEMENT.md` — This plan
- `.github/scripts/pre-push-check.sh` — Local validation
- `.github/scripts/wait-for-ci.sh` — CI waiting script

**Updated Files**:
- `.agentic/AGENT_GUIDELINES.md` — Add CI-first workflow section
- `.agentic/ci/README.md` — Link to new enforcement docs

**README.md Links**:
- Add CI badge: `![CI](https://github.com/user/repo/actions/workflows/build.yml/badge.svg?branch=dev)`
- Link to CI docs: `See [CI Workflow](.agentic/ci/AGENT_CI_WORKFLOW_ENFORCEMENT.md)`

