---
name: architect
description: "Use when planning where new code should live before implementation. Produces an Architecture Brief."
disable-model-invocation: true
argument-hint: "[feature or task description]"
---

# Architecture Planning

> **Purpose:** Design where new code should live before any implementation begins.

Read `.github/instructions/03-ARCHITECT.md` for the full architect workflow.
Read `.github/copilot-instructions.md` and `CLAUDE.md` for all standards.

## Workflow Summary

1. **Context Sufficiency Check** — inventory files, determine scope, identify missing context
2. **Map Existing Structure** — which engine modules, ruleset layers, fog-of-war boundaries are affected
3. **Architectural Gates** — Layer Alignment, Fog-of-War Safety, Version Lock, Action Whitelist, Ruleset Hierarchy
4. **Output Architecture Brief** — scope, files, gate results, dependencies, tests, doc updates
