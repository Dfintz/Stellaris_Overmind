---
name: engine-module
description: "Use when creating or modifying Python modules in engine/ — ruleset generator, decision engine, personality shards, or validator."
---

# Engine Module Development

> **Use when:** Creating or modifying Python modules in the `engine/` directory — ruleset
> generator, decision engine, personality shards, or validator.

Your full coding standards are in `.github/copilot-instructions.md` and `CLAUDE.md`.

---

## Quick Start Checklist

Before writing any engine code:

- [ ] Read the relevant spec doc (`RULESET_SPEC.md`, `PERSONALITY_SYSTEM.md`, `EXPORTER_SPEC.md`, `EXECUTOR_SPEC.md`)
- [ ] Check existing code in `engine/` for patterns and constants
- [ ] Verify the mechanic exists in Stellaris 4.3.4
- [ ] Identify fog-of-war implications

---

## Module Responsibilities

| Module | Owns | Does NOT Own |
|--------|------|-------------|
| `ruleset_generator.py` | Ethics/civic/trait/origin constants, `generate_ruleset()` | LLM prompting, validation |
| `decision_engine.py` | Prompt construction, LLM response parsing, `decide()` | Ruleset data, personality profiles |
| `personality_shards.py` | Government weights, personality profile generation | Decision making, validation |
| `validator.py` | Directive validation, fog-of-war checks, constraint enforcement | Ruleset generation, LLM interaction |

---

## File Creation Order

1. **Constants/Data** — add to appropriate dict in `ruleset_generator.py`
2. **Personality** — add nudge in `personality_shards.py` if ethic/civic/trait affects personality
3. **Validation** — add constraint in `validator.py` if origin/civic creates a hard rule
4. **Tests** — add test cases in `tests/test_<module>.py`

---

## Rules

- Every module starts with `from __future__ import annotations`
- All public functions have complete type annotations
- Constants use `UPPER_SNAKE_CASE` and are `dict[str, dict]`
- Use `dataclass` for structured returns (never raw tuples)
- Raise `ValueError` for invalid input, not `Exception`
- No imports between `ruleset_generator` ↔ `decision_engine` ↔ `personality_shards`
- `GAME_VERSION = "4.3.4"` must appear in both `ruleset_generator.py` and `validator.py`
