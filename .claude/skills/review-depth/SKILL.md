---
name: review-depth
description: "Use for architectural depth review — module boundaries, fog-of-war architecture, bridge design."
disable-model-invocation: true
---

# Code Review — Architectural Depth Pass

> **Purpose:** Deep reasoning about module ownership, fog-of-war boundaries, and bridge integrity.

Read `.github/instructions/06-REVIEW-DEPTH.md` for the full review workflow.

## Architectural Gates

1. **Module Alignment** — is the function in the right module?
2. **Fog-of-War Architecture** — is the boundary in the right place?
3. **Ruleset Data Ownership** — who owns the data? Constants vs external files?
4. **Bridge Boundary Audit** — JSON schema enforced on both sides?
5. **Extensibility** — can new ethics/civics/origins/actions be added safely?
