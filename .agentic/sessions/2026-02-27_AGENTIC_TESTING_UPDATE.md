# Session: 2026-02-27 - Headless Test Enablement

## Context

- Runner has no hardware attached.
- Goal: keep CI green without disabling hardware tests permanently.

## Changes

- Added `RUN_HARDWARE_TESTS=1` gate for hardware-only pytest checks.
- Documented headless pytest usage for CI and local runs.

## Outcome

- `pytest -q` passes in headless mode (hardware tests skipped).

## Follow-ups

- Add a dedicated hardware runner label for gated jobs.
- Add CI job split: headless vs hardware.
