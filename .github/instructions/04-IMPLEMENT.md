---
applyTo: '**'
---

# Implementation

> **Model:** Opus 4.6
> **Purpose:** Implement the feature described in the task, following the Architecture Brief
> produced by 03-ARCHITECT if one exists.

Your full coding standards are in `.github/copilot-instructions.md` and `CLAUDE.md` — those
documents are the authority on all style, naming, architecture, and pattern decisions.

If an Architecture Brief from 03-ARCHITECT is present, follow it. Any decision it marks as
`[UNVERIFIED]` must be flagged to the user before implementing.

---

## MANDATORY FIRST STEP: Context Sufficiency Check

### Step 1 — Inventory what you have

List every file provided, one per line:

- File path
- What it contains (one sentence)
- Its layer (`engine/ruleset`, `engine/decision`, `engine/personality`, `engine/validator`,
  `mod/exporter`, `mod/executor`, `mod/events`, `docs`, `examples`, `tests`)

### Step 2 — Determine scope

> **Scope: 🧠 Engine** / **🎮 Mod** / **📋 Ruleset** / **🔗 Bridge**

### Step 3 — Identify missing files

| Missing file | Needed to implement |
|---|---|
| `path/to/file` | e.g. "Need validator interface to add new constraint" |

### Step 4 — Proceed or request

If critical files are missing, stop and list them.

### Step 5 — Confirm Architecture Brief

If a Brief exists:
- Confirm you will follow it
- List any `[UNVERIFIED]` assumptions that affect implementation
- If contradicted by actual code, STOP and flag before writing

---

## MANDATORY SECOND STEP: Pre-Implementation Discovery

### 1. Ruleset Consistency
- [ ] If adding a new ethic/civic/trait/origin: verify it exists in Stellaris 4.3.4
- [ ] If modifying ruleset hierarchy: confirm override order is preserved
- [ ] Check `engine/ruleset_generator.py` for existing entries before adding duplicates

### 2. Fog-of-War Verification
- [ ] If touching state export: verify intel-level filtering is applied
- [ ] If adding new state fields: classify each as always-visible, intel-gated, or never-visible
- [ ] Validator must reject any new field that could leak hidden info

### 3. Action Compliance
- [ ] If adding a new action: it must be added to `ALLOWED_ACTIONS` in both `decision_engine.py`
  and `validator.py`
- [ ] New actions must be documented in `docs/EXECUTOR_SPEC.md`

### 4. Type Consistency
- [ ] Dataclass fields must match JSON schema in `docs/EXPORTER_SPEC.md`
- [ ] `Directive` dataclass must match directive format in `docs/EXECUTOR_SPEC.md`
- [ ] Any new return types must use dataclasses, not raw dicts

---

## Implementation Order

Follow this order for any feature:

1. **Types/Dataclasses** — define data structures first
2. **Core Logic** — implement the function/module
3. **Validation** — add or update validator checks
4. **Tests** — write tests covering happy path, edge cases, and fog-of-war
5. **Documentation** — update relevant spec docs
6. **Examples** — add sample JSON if the feature affects state/directive format

---

## Code Patterns

### Adding a New Ethic/Civic/Trait/Origin

```python
# In engine/ruleset_generator.py

# 1. Add to the appropriate constant dict
ETHICS_BASE["New Ethic"] = {
    "priority_key": value,
}

# 2. Verify generate_ruleset() picks it up (it does via dict lookup)
# 3. Add corresponding personality nudge in engine/personality_shards.py
# 4. Add validator constraints in engine/validator.py if needed
# 5. Add test case in tests/test_ruleset_generator.py
```

### Adding a New Validation Rule

```python
# In engine/validator.py

def validate_directive(directive: dict, ruleset: dict, state: dict) -> ValidationResult:
    errors: list[str] = []

    # ... existing checks ...

    # NEW CHECK: describe what it validates
    if condition_that_violates_rules:
        errors.append("Clear error message citing the violated rule")

    return ValidationResult(valid=len(errors) == 0, errors=errors)
```

### Adding a New State Field to Exporter

```python
# In mod/exporter (Clausewitz script) — pseudocode
# 1. Determine intel level required for this field
# 2. Add to snapshot only if empire has sufficient intel
# 3. Document in docs/EXPORTER_SPEC.md
# 4. Add to sample event JSON in examples/sample_events/
```

---

## Post-Implementation Checklist

- [ ] All new functions have type annotations
- [ ] All new modules have `from __future__ import annotations`
- [ ] No fog-of-war violations introduced
- [ ] Validator updated for any new constraints
- [ ] Tests written and passing
- [ ] Relevant docs updated
- [ ] Examples updated if format changed
