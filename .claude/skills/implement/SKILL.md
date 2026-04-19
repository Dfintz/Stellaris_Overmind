---
name: implement
description: "Use when implementing a feature. Follows Architecture Brief if one exists."
disable-model-invocation: true
argument-hint: "[feature or task description]"
---

# Implementation

> **Purpose:** Implement the feature following the Architecture Brief and coding standards.

Read `.github/instructions/04-IMPLEMENT.md` for the full implementation workflow.
Read `.github/copilot-instructions.md` and `CLAUDE.md` for all standards.

## Workflow Summary

1. **Context Sufficiency Check** — inventory, scope, missing files, confirm brief
2. **Pre-Implementation Discovery** — ruleset consistency, fog-of-war verification, action compliance, type consistency
3. **Implementation Order** — types/dataclasses → core logic → validation → tests → docs → examples
4. **Post-Implementation Checklist** — annotations, future imports, fog-of-war, validator, tests, docs
