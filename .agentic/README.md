# Agent Knowledge Base

**Purpose**: Reference knowledge for USB HID joystick controller with SimpleFOC motor and MIDI input.

---

## START HERE (Required Reading)

1. **[PURPOSE.md](PURPOSE.md)** — Project goals, hardware, success criteria
2. **[AGENT_GUIDELINES.md](AGENT_GUIDELINES.md)** — Rules, housekeeping, observability
3. **[KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md)** — Working baseline, known issues

**Root-level documents** (referenced by [AGENTS.md](../AGENTS.md)):
- **[REQUIREMENTS.md](../REQUIREMENTS.md)** — SOPHIST-style requirements, traceability
- **[ROADMAP.md](../ROADMAP.md)** — Version increments, backlog
- **[MILESTONES.md](MILESTONES.md)** — Detailed exit criteria, hardware plans

---

## Directory Structure

```
.agentic/
├─ PURPOSE.md                        What this project is
├─ AGENT_GUIDELINES.md               How agents work (rules, testing, cleanup)
├─ KNOWLEDGE_BASE.md                 Technical baseline & working state
├─ MILESTONES.md                     Version plan, exit criteria, hardware roadmap
├─ AIRCRAFT_CONTROLS_RESEARCH.md     Real aircraft control feel research
├─ FAILED_EXPERIMENTS.md             Dead ends (PID auto-tuning, RB command, …)
├─ USB_STABILITY_ISSUE.md            USB bandwidth/CDC congestion fix
├─ architecture/                     System design, build procedures, hardware
├─ ci/                               CI workflows, scripts, device detection
├─ testing/                          Test plans, results, device testing guide
├─ tuning/                           SimpleFOC PID tuning guides
└─ sessions/                         Session logs (pre-v0.1-rc, historical)
```

---

## Quick Paths

- **Build firmware** → [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md#working-baseline)
- **Run tests** → [testing/DEVICE_TESTING.md](testing/DEVICE_TESTING.md)
- **Milestones & roadmap** → [MILESTONES.md](MILESTONES.md)
- **What failed before** → [FAILED_EXPERIMENTS.md](FAILED_EXPERIMENTS.md)
- **CI/CD** → [ci/README.md](ci/README.md)
- **Tuning motors** → [tuning/README.md](tuning/README.md)
- **Hardware specs** → [architecture/HARDWARE_SETUP.md](architecture/HARDWARE_SETUP.md)
