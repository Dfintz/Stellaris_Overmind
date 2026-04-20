# Copilot Instructions — Stellaris Overmind

This file is the authority on all coding standards, architecture, and conventions for the
Stellaris 4.3.4 LLM-Driven AI Overhaul project.

Read `docs/PROJECT_OVERVIEW.md` for the full project specification.
Read `CLAUDE.md` for the complete standards reference (shared with Claude Code).

---

## Project Summary

**Stellaris Overmind** is a non-cheating, expert-level Stellaris AI powered by a local LLM.
The AI plays within Stellaris 4.3.4 rules, respects fog-of-war, adapts to ethics/civics/traits/origins,
and makes macro-strategic decisions like a strong human player — live, without pausing the game.

---

## Critical Constraints

1. **Fog-of-War Compliance** — Never expose hidden game data to the LLM. The State Exporter
   filters by intel level. The Validator rejects any directive referencing unseen information.

2. **Action Whitelist** — The LLM may only choose from 11 allowed actions:
   `EXPAND`, `BUILD_FLEET`, `IMPROVE_ECONOMY`, `FOCUS_TECH`, `DIPLOMACY`, `ESPIONAGE`,
   `PREPARE_WAR`, `DEFEND`, `CONSOLIDATE`, `COLONIZE`, `BUILD_STARBASE`.

3. **Version Lock** — All mechanics, rulesets, and meta must match Stellaris `4.3.4`.
   Do not reference mechanics from other versions.

4. **No God Mode** — The LLM receives only known fleets, known borders, known diplomacy,
   known planets, known economy, and intel-level-appropriate enemy info.

5. **Meta is Curated** — The LLM applies meta; it does not invent meta.
   All meta entries in `docs/META_4.3.4.md` are tested in real 4.3.4 gameplay.

6. **Dual Mode** — Player mode shows suggestions only (no direct execution).
   AI mode steers native AI via personality overrides + stat modifiers
   (no build queue bypass).

---

## Repository Layout

| Directory | Purpose |
|-----------|---------|
| `docs/` | Project specs, ruleset spec, meta, personality system, exporter/executor specs |
| `engine/` | Python AI engine: 20+ modules (multi-agent, planner, providers, metrics, console) |
| `mod/` | Clausewitz mod files: state exporter, action executor, event hooks |
| `examples/` | Sample rulesets, events, and decisions (JSON) |

---

## Python Standards

- Python 3.11+, `from __future__ import annotations` in every module
- `ruff` for linting/formatting, `mypy --strict` for type checking, `pytest` for tests
- Prefer dataclasses over raw dicts, pure functions over stateful classes
- All public functions fully type-annotated
- `ValueError` for invalid LLM output or ruleset violations
- `ValidationResult(valid: bool, errors: list[str])` pattern for validation

---

## Key Architecture References

| Document | Purpose |
|----------|---------|
| `docs/PROJECT_OVERVIEW.md` | Full project specification |
| `docs/RULESET_SPEC.md` | Ruleset schema, hierarchy, validation rules |
| `docs/META_4.3.4.md` | Curated patch meta (early/mid/late game, origin-specific, forbidden) |
| `docs/PERSONALITY_SYSTEM.md` | Leader shards, government weighting, decision synthesis |
| `docs/EXPORTER_SPEC.md` | State snapshot format, intel filtering, export triggers |
| `docs/EXECUTOR_SPEC.md` | Action mapping, validation layer, execution timing |
