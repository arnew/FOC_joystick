# Agent Knowledge Base

**Purpose**: Agent-accessible documentation for autonomous development

---

## ⚠️ START HERE (Required Reading)

**Before starting any work, read these in order:**

1. **[PURPOSE.md](PURPOSE.md)** - Project goals, hardware, success criteria
2. **[AGENT_GUIDELINES.md](AGENT_GUIDELINES.md)** - How agents should behave, decision framework, anti-patterns
3. **[KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md)** - Working baseline, known issues, technical details

---

## Directory Structure

```
.agentic/
├── PURPOSE.md              ⭐ What this project is
├── AGENT_GUIDELINES.md     ⭐ How agents work
├── KNOWLEDGE_BASE.md       ⭐ Technical baseline
├── README.md               (this file)
├── ci/                     GitHub workflows, automation
├── testing/                Test infrastructure and results
└── sessions/               Development session notes
```

---

## Quick Links

### Essential Reading
1. [Project Purpose](PURPOSE.md) - Goals and success criteria
2. [Agent Guidelines](AGENT_GUIDELINES.md) - Decision framework and anti-patterns
3. [Technical Knowledge](KNOWLEDGE_BASE.md) - Working baseline and known issues

### Development
- [Working Baseline](KNOWLEDGE_BASE.md#working-baseline) - Current feature/modularize-main state
- [Known Issues](KNOWLEDGE_BASE.md#known-issues) - TinyUSB bootloader, etc.
- [Build Commands](KNOWLEDGE_BASE.md#working-baseline) - How to compile and upload

### Testing
- [Test Strategy](KNOWLEDGE_BASE.md#testing-strategy) - Headless vs hardware tests
- [CI/CD Pipeline](KNOWLEDGE_BASE.md#cicd-pipeline) - GitHub Actions workflows

---

## Navigation

Each subdirectory contains its own README.md with links to related documentation:

- `ci/README.md` - CI/CD workflows and GitHub integration
- `testing/README.md` - Test infrastructure and findings
- `sessions/README.md` - Session summaries and progress tracking
