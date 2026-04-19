# Testing

> **Use when:** Writing or modifying tests for the Stellaris Overmind engine.
> All tests use pytest and live in the `tests/` directory.

Your full coding standards are in `.github/copilot-instructions.md` and `CLAUDE.md`.

---

## Quick Start Checklist

- [ ] Test file name: `tests/test_<module_name>.py`
- [ ] Use pytest fixtures for common empire configurations
- [ ] Cover fog-of-war filtering explicitly
- [ ] Cover validator rejection paths
- [ ] Cover all origin types in ruleset generation

---

## Test Structure

```
tests/
    test_ruleset_generator.py
    test_decision_engine.py
    test_personality_shards.py
    test_validator.py
    conftest.py              ← shared fixtures
```

---

## Fixture Patterns

### conftest.py — Shared Empire Fixtures

```python
import pytest

@pytest.fixture
def une_empire() -> dict:
    """United Nations of Earth — standard democratic empire."""
    return {
        "ethics": ["Egalitarian", "Xenophile", "Militarist"],
        "civics": ["Beacon of Liberty", "Meritocracy"],
        "traits": ["Intelligent", "Thrifty"],
        "origin": "Prosperous Unification",
        "government": "Democracy",
    }

@pytest.fixture
def void_dwellers_empire() -> dict:
    """Void Dwellers — habitat-only colonization."""
    return {
        "ethics": ["Materialist", "Xenophobe"],
        "civics": ["Technocracy", "Citizen Service"],
        "traits": ["Intelligent", "Natural Engineers"],
        "origin": "Void Dwellers",
        "government": "Oligarchy",
    }

@pytest.fixture
def sample_state() -> dict:
    """Minimal valid game state snapshot."""
    return {
        "version": "4.3.4",
        "year": 2230,
        "month": 6,
        "colonies": ["Earth", "Mars"],
        "known_empires": [
            {"name": "Tzynn Empire", "attitude": "Hostile", "intel_level": "Low"}
        ],
        "economy": {"energy": 100, "minerals": 200, "alloys": 50},
        "fleets": [],
    }
```

---

## Test Categories

### 1. Ruleset Generation Tests
- Verify each ethic produces correct base priorities
- Verify civic modifiers apply correctly
- Verify trait micro-modifiers apply correctly
- Verify origin overrides replace lower-layer values
- Verify the hierarchy: origin override wins over ethic base

### 2. Decision Engine Tests
- Verify prompt construction includes ruleset + state + event
- Verify LLM response parsing extracts ACTION/TARGET/REASON
- Verify invalid actions raise `ValueError`
- Verify stub response when no LLM connected

### 3. Personality Tests
- Verify government weighting (Imperial=80% ruler, Democracy=20% ruler, etc.)
- Verify ethic influence on personality dimensions
- Verify values are clamped to [0.0, 1.0]
- Verify all government types have valid weights

### 4. Validator Tests (CRITICAL)
- **Fog-of-war:** reject directive targeting unknown system
- **Action whitelist:** reject invalid action names
- **Version lock:** reject mismatched ruleset version
- **Origin constraints:** Void Dwellers can't colonize non-habitats
- **Civic constraints:** Inward Perfection blocks diplomacy
- **Civic constraints:** Barbaric Despoilers only raiding wars
- **Reason required:** reject empty reason field

### 5. Integration Tests
- Full pipeline: generate ruleset → build personality → decide → validate
- Verify end-to-end fog-of-war compliance

---

## Rules

- Use `from __future__ import annotations` in test files
- Test names: `test_<what>_<condition>_<expected>` pattern
- One assert per test where practical
- Use parametrize for testing multiple ethics/civics/origins
- Never mock the validator — always test real validation
- Fog-of-war tests are mandatory for any state-handling code
