# Instructions to AI Agents

**Purpose**: USB HID joystick controller for Flight Simulator with dual motorized axes and MIDI input.

**Philisophy**:
UNIX - KISS
Only mandatory inventions. When stuff is already available, use the lib, tool, whatever.

**Development Model**: 
Git-flow. All changes must be developed in feature/hotfix branches, development is maintained in dev, releases are kept in main, releases are prepared in git flow.
Test-driven. All changes must pass automated tests before continuation. Testing is wanted during development, before merging a branch or creating a release tests must be successful.
Agent-positive. The agent creates commits and merges code using its own name in git itself.

**Agentic Knowledge**:
Knowledge goes as graph database into .agentic/. Every folder in there gets a README.md index, linking to subfolders.
Code style guidelines are in .agentic/architecture/README.md.

