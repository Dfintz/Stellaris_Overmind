---
name: review-breadth
description: "Use for breadth-first code review — systematic compliance checking, fog-of-war verification, and ruleset consistency."
disable-model-invocation: true
---

# Code Review — Breadth Pass

> **Purpose:** Find as many concrete issues as possible through systematic review.

Read `.github/instructions/05-REVIEW-BREADTH.md` for the full review workflow.

## Review Passes

1. **Fog-of-War Compliance** (CRITICAL) — hidden data never reaches LLM
2. **Action Whitelist** — only 10 allowed actions
3. **Ruleset Hierarchy** — origin > ethics > civics > traits > meta
4. **Version Lock** — all mechanics match 4.3.4
5. **Python Quality** — types, imports, error handling
6. **Test Coverage** — fog-of-war edge cases, validator rejections, all origins
