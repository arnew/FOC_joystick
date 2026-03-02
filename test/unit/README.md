# Unit Tests

Headless tests that run without hardware.

| File | Purpose |
|------|---------|
| `sim_device.py` | Headless device simulator (library) |
| `test_sim_device.py` | Pytest tests for the simulator |
| `test_config.cpp` | PlatformIO native unit test for config (TODO) |

Run: `python -m pytest test/unit/ -q`
