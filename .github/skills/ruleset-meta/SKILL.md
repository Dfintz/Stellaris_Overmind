# Ruleset & Meta Authoring

> **Use when:** Adding or modifying rulesets, ethics, civics, traits, origins, or patch meta
> in `docs/META_4.3.4.md`, `docs/RULESET_SPEC.md`, or the constants in `engine/ruleset_generator.py`.

Your full coding standards are in `.github/copilot-instructions.md` and `CLAUDE.md`.

---

## Quick Start Checklist

- [ ] Verify the mechanic exists in Stellaris 4.3.4
- [ ] Meta entries must be tested in real 4.3.4 gameplay
- [ ] LLM does NOT invent meta — all meta is human-curated
- [ ] Check `docs/META_4.3.4.md` Section 5 (Forbidden Meta) before adding

---

## Ruleset Hierarchy

Priority order (highest first):

1. **Origin Overrides** — hard rewrites, can replace any lower layer
2. **Ethics Base** — core strategic identity (war frequency, diplomacy, risk)
3. **Civic Modifiers** — strong biases or hard constraints
4. **Trait Micro-Modifiers** — small nudges (+5-10%)
5. **Patch Meta** — curated strategies, version-locked to 4.3.4

When layers conflict, higher priority wins.

---

## Adding New Entries

### New Ethic
1. Add to `ETHICS_BASE` in `engine/ruleset_generator.py`
2. Add personality nudge in `engine/personality_shards.py`
3. Add test case
4. Verify no fog-of-war implications

### New Civic
1. Add to `CIVIC_MODIFIERS` in `engine/ruleset_generator.py`
2. If civic creates hard constraints (e.g., "diplomacy blocked"), add validator check
3. Add personality nudge if applicable
4. Add test case

### New Origin
1. Add to `ORIGIN_OVERRIDES` in `engine/ruleset_generator.py`
2. Add validator constraints for colonization/war/diplomacy rules
3. Add origin-specific meta in `docs/META_4.3.4.md` Section 4
4. Add test case covering the override behavior

### New Meta Rule
1. Add to appropriate section in `docs/META_4.3.4.md` (Early/Mid/Late/Origin-specific)
2. **Must** be tested in a real 4.3.4 game
3. **Must not** be LLM-generated or speculative
4. Check it doesn't contradict existing meta

---

## Forbidden Patterns

- Battleship rush before year 20
- Colonizing low-habitability worlds without tech
- Ignoring fleet cap entirely
- Using unseen information (god mode)
- Referencing mechanics from other Stellaris versions
- Adding untested or speculative meta

---

## Phase Definitions

| Phase | Years | Focus |
|-------|-------|-------|
| Early | 0–40 | Economy foundation, chokepoints, first contacts |
| Mid | 40–120 | Expansion, diplomacy, fleet building, traditions |
| Late | 120+ | Repeatables, megastructures, crisis prep |

---

## Validation

A ruleset/meta entry is valid if:
- It matches game version 4.3.4
- It references real mechanics (not invented)
- It respects fog-of-war
- It has no contradictory modifiers
- It has been tested in gameplay (for meta)
