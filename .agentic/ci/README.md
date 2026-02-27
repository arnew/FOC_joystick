# CI/CD & GitHub Integration

Tools and workflows for automated testing, cloud validation, and agentic GitHub operations.

## Quick Navigation

- [GitHub Integration & Development Workflow](GITHUB_INTEGRATION.md) — How agents use `gh` CLI for develop/push/validate cycle, CI monitoring, and issue tracking

## Current Infrastructure

**Workflows** (3 tiers):
- **Code Quality** (`ubuntu-latest`): function size check + PIO build
- **Headless Test** (`ubuntu-latest`): pytest unit tests, simulator, no hardware  
- **Hardware Test** (`[self-hosted, hardware]`): build → upload → HIL tests (physical device required)

**Tools**:
- `gh` CLI — all GitHub operations (auth as `arnew` with `repo` scope)
- `workflow_dispatch` — on-demand CI triggers (all workflows support this)
- `git-flow` — branch management (feature/*, dev, main, release/*)

## Status (Feb 27, 2026)

✅ Code Quality: passing  
✅ Headless Test: passing (pytest 3 passed, 1 skipped)  
⚠️ Hardware Test: blocked on device setup (no RP2040 in BOOTSEL mode on runner)

## See Also

- [architecture/](../architecture/) — overall project structure
- [testing/](../testing/) — test results, test findings, headless testing guide
