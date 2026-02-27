# Headless Testing (No Hardware)

Purpose: run Python tests on machines without attached devices.

## Scope

- Unit-style checks only
- Hardware-dependent tests are skipped by default
- Use this for CI runners without USB devices

## How To Run

```bash
# Headless default
python -m pytest -q

# Hardware tests (only on a machine with devices)
RUN_HARDWARE_TESTS=1 python -m pytest -q
```

## Notes

- Hardware gating uses `RUN_HARDWARE_TESTS=1`.
- `pygame` is optional in headless mode.
- Use a labeled runner for hardware tests to avoid false failures.
