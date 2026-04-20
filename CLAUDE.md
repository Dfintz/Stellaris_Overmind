# CLAUDE.md — Stellaris Overmind

This file is the authority on all coding standards, architecture, and conventions for the
Stellaris 4.3.4 LLM-Driven AI Overhaul project.

Read `docs/PROJECT_OVERVIEW.md` for the full project specification.

---

## Project Identity

- **Name:** Stellaris Overmind
- **Purpose:** Non-cheating, expert-level Stellaris AI powered by a local LLM
- **Game Version Lock:** `4.3.4` — all rulesets, meta, and mechanics must match this version
- **Philosophy:** The LLM is a strategist, not a cheater

---

## Repository Structure

```
docs/           Project specs, ruleset spec, meta, personality system, exporter/executor specs
engine/         Python AI engine — 20+ modules (multi-agent, planner, providers, metrics, console)
mod/            Clausewitz mod files — events, effects, modifiers, AI personalities
examples/       Sample rulesets, events, and decisions (JSON)
training/       Model optimization — eval, curate, fine-tune, distill, quantize
scripts/        Utilities — teacher collection, Foundry upload, auto-execute
.claude/        Claude Code configuration and skills
.github/        Copilot instructions and skills
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| AI Engine | Python 3.11+, structured around pure functions and dataclasses |
| LLM Interface | Pluggable `LLMProvider` ABC — local (vLLM/Ollama), online (OpenAI-compat), hybrid |
| Game Integration | Clausewitz engine scripting + autosave parsing (no exporter mod needed) |
| Data Exchange | JSON directive files in `mod/ai_bridge/` for AI mode; `overmind_suggestion.txt` for player mode |
| Multi-Agent | Council orchestrator with domain sub-agents + government-weighted arbitration |
| Training | LoRA/QLoRA via HF/PEFT/TRL, GPTQ/AWQ quantization, wandb tracking |
| Console | Rich TUI dashboard (optional) |
| Testing | pytest (464+ tests) |
| Linting | ruff |
| Type Checking | mypy (strict mode) |

---

## Architecture Rules

### Fog-of-War Compliance (CRITICAL)
- **Never** expose hidden game data to the LLM
- The State Exporter must filter by intel level before emitting JSON
- The Validator must reject any directive referencing unseen information
- See `docs/EXPORTER_SPEC.md` for intel-level filtering rules

### Allowed Actions (Whitelist)
The LLM may only output one of these 11 actions:
```
EXPAND, BUILD_FLEET, IMPROVE_ECONOMY, FOCUS_TECH, DIPLOMACY, ESPIONAGE,
PREPARE_WAR, DEFEND, CONSOLIDATE, COLONIZE, BUILD_STARBASE
```
No free-form actions. The Validator rejects anything else.

### Dual Mode Architecture
- **Player mode** → displays strategic suggestions in the TUI + `overmind_suggestion.txt`;
  the human decides and acts.  No direct game execution.
- **AI mode** → steers Stellaris’ native AI via personality overrides + stat modifiers.
  The LLM decides macro strategy (what to prioritise); native AI handles micro
  (build queues, research picks, fleet composition, district placement).
  Does **not** bypass native AI build queues with direct console commands.

### Ruleset Hierarchy (highest → lowest priority)
1. **Origin Overrides** — hard rewrites (e.g., Void Dwellers: habitats only)
2. **Ethics Base** — strategic priorities (e.g., Militarist: high war frequency)
3. **Civic Modifiers** — strong biases (e.g., Technocracy: research priority)
4. **Trait Micro-Modifiers** — small nudges (e.g., Intelligent: +5% research)
5. **Patch Meta** — curated 4.3.4 strategies (never LLM-generated)

### Decision Format
Every LLM output must be:
```
ACTION: <one action>
TARGET: <target or NONE>
REASON: <must cite ruleset elements>
```

---

## Python Coding Standards

### Style
- Use `ruff` for formatting and linting
- Use `mypy --strict` for type checking
- Use `from __future__ import annotations` in every module
- Prefer dataclasses over raw dicts for structured data
- Prefer pure functions over classes where state is unnecessary

### Naming
- `snake_case` for functions, variables, modules
- `PascalCase` for classes and dataclasses
- `UPPER_SNAKE_CASE` for constants and action enums
- Module names must match their domain: `ruleset_generator.py`, `decision_engine.py`, etc.

### Type Annotations
- All public functions must have complete type annotations
- Use `dict`, `list`, `str | None` (not `Optional`, `Dict`, `List`)
- Dataclass fields must be typed

### Error Handling
- Raise `ValueError` for invalid LLM output or ruleset violations
- Never silently swallow errors — log or raise
- The Validator returns a `ValidationResult` dataclass with `valid: bool` and `errors: list[str]`

### Imports
- Standard library first, then third-party, then local — separated by blank lines
- No wildcard imports
- No circular imports between engine modules

---

## Clausewitz Mod Standards

### File Organization
- One file per feature (exporter, executor, events)
- Use Stellaris mod descriptor format
- Comments must explain the bridge mechanism (game ↔ Python)

### Fog-of-War Rules
- Exporter must check intel level before including any empire data
- Unknown systems, hidden fleets, and enemy economy (below High intel) must never appear
- Crisis spawn information is always hidden

---

## Game Mechanics Rules

### Version Lock
All code, rulesets, and meta must reference Stellaris `4.3.4` mechanics only.
If a mechanic does not exist in 4.3.4, it must not be referenced.

### Meta Contributions
- Must be tested in a real 4.3.4 game
- Must not be invented or hallucinated by the LLM
- Must be added to `docs/META_4.3.4.md`

### Personality System
- Each empire gets a unique personality from ethics + civics + traits + origin + government
- Leader shards (ruler, admiral, governor, scientist, general) contribute weighted opinions
- Government type determines shard weights (see `docs/PERSONALITY_SYSTEM.md`)

---

## Testing Standards

- All engine modules must have corresponding test files in `tests/`
- Test file naming: `test_<module_name>.py`
- Use pytest fixtures for common empire configurations
- Test fog-of-war filtering explicitly — ensure hidden data never leaks
- Test validator rejection of invalid actions, unseen targets, and civic/origin violations
- Test ruleset generation for all origin types

---

## Commit Standards

- Prefix commits with scope: `engine:`, `mod:`, `docs:`, `meta:`, `tests:`
- Keep commits atomic — one logical change per commit
- Never commit secrets, API keys, or `.env` files
