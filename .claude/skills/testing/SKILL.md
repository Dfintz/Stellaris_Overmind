---
name: testing
description: "Use when writing or modifying pytest tests for the Stellaris Overmind engine modules."
---

# Testing

> **Use when:** Writing or modifying tests in `tests/`. Uses pytest.

---

## Structure

```
tests/
    conftest.py                   ← shared fixtures
    test_ruleset_generator.py
    test_decision_engine.py
    test_personality_shards.py
    test_validator.py
```

## Critical Test Categories

1. **Fog-of-war** — reject directives targeting unknown systems/empires
2. **Action whitelist** — reject invalid action names
3. **Version lock** — reject mismatched ruleset versions
4. **Origin constraints** — Void Dwellers habitats only, etc.
5. **Civic constraints** — Inward Perfection blocks diplomacy, etc.
6. **Ruleset hierarchy** — origin overrides win over ethics base

## Rules

- Test names: `test_<what>_<condition>_<expected>`
- Use parametrize for multiple ethics/civics/origins
- Never mock the validator
- Fog-of-war tests are mandatory for state-handling code
