---
name: ruleset-meta
description: "Use when adding or modifying rulesets, ethics, civics, traits, origins, or patch meta for Stellaris 4.3.4."
---

# Ruleset & Meta Authoring

> **Use when:** Adding or modifying rulesets, ethics, civics, traits, origins, or patch meta
> in `docs/META_4.3.4.md`, `docs/RULESET_SPEC.md`, or the constants in `engine/ruleset_generator.py`.

---

## Ruleset Hierarchy (highest first)

1. **Origin Overrides** — hard rewrites
2. **Ethics Base** — core strategic identity
3. **Civic Modifiers** — strong biases or hard constraints
4. **Trait Micro-Modifiers** — small nudges
5. **Patch Meta** — curated 4.3.4 strategies

## Adding New Entries

### New Ethic → `ETHICS_BASE` + personality nudge + test
### New Civic → `CIVIC_MODIFIERS` + validator constraint (if hard rule) + test
### New Origin → `ORIGIN_OVERRIDES` + validator constraints + origin meta in `META_4.3.4.md` + test
### New Meta Rule → `META_4.3.4.md` (must be tested in real 4.3.4 gameplay, not LLM-generated)

## Forbidden

- Referencing mechanics from other Stellaris versions
- Adding untested or speculative meta
- LLM-generated meta entries
