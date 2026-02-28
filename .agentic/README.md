# Agent Knowledge Base

**Purpose**: Reference knowledge for USB HID joystick controller with SimpleFOC motor and MIDI input.

---

## START HERE (Required Reading)

1. **[PURPOSE.md](PURPOSE.md)** — Project goals, hardware, success criteria
2. **[AGENT_GUIDELINES.md](AGENT_GUIDELINES.md)** — Rules, housekeeping, observability
3. **[KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md)** — Working baseline, known issues

---

## Directory Structure

```
.agentic/
├─ PURPOSE.md                  What this project is
├─ AGENT_GUIDELINES.md         How agents work (rules, testing, cleanup)
├─ KNOWLEDGE_BASE.md           Technical baseline & working state
├─ FAILED_EXPERIMENTS.md       Dead ends (PID auto-tuning, RB command, dual-motor)
├─ USB_STABILITY_ISSUE.md      USB bandwidth/CDC congestion fix
├─ FEATURE_ROADMAP.md          Planned work (phases 1-4)
├─ architecture/               System design, build procedures, hardware setup
├─ ci/                         CI workflows, scripts, device detection
├─ testing/                    Test plans, results, device testing guide
├─ tuning/                     SimpleFOC PID tuning guides
└─ sessions/                   Session logs, historical records
```

---

## Quick Paths

- **Build firmware** → [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md#working-baseline)
- **Run tests** → [testing/DEVICE_TESTING.md](testing/DEVICE_TESTING.md)
- **What failed before** → [FAILED_EXPERIMENTS.md](FAILED_EXPERIMENTS.md)
- **CI/CD** → [ci/README.md](ci/README.md)
- **Tuning motors** → [tuning/README.md](tuning/README.md)
- **Hardware specs** → [architecture/HARDWARE_SETUP.md](architecture/HARDWARE_SETUP.md)
