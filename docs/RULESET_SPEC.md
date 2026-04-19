# Stellaris 4.3.4 – Ruleset Specification
This document defines the ruleset architecture used by the LLM‑driven AI.
The ruleset ensures the AI behaves like an expert human player, without cheating, hallucinating mechanics, or using unseen information.

---

## 1. Purpose of the Ruleset
The ruleset provides:
- A **structured, deterministic foundation** for AI behavior.
- A **safe constraint layer** preventing LLM hallucinations.
- A **version‑locked meta layer** tied to Stellaris 4.3.4.
- A **modular system** that adapts to ethics, civics, traits, origins, and government type.

The LLM does not invent rules.
It **applies** the ruleset to make macro‑strategic decisions.

---

## 2. Ruleset Structure

### 2.1 Top-Level Schema
```json
{
  "game_version": "4.3.4",
  "empire_id": 0,
  "design": {},
  "base_priorities": {},
  "ethic_modifiers": {},
  "civic_modifiers": {},
  "trait_modifiers": {},
  "origin_overrides": {},
  "government_logic": {},
  "phase_adjustments": {},
  "meta_rules": {}
}
```

---

## 3. Base Priorities (Ethics Layer)
Ethics define the **core strategic identity** of an empire.

Example fields:
```json
{
  "economy": 0.5,
  "fleet": 0.5,
  "tech": 0.5,
  "unity": 0.5,
  "expansion": 0.5,
  "diplomacy": 0.5
}
```

Ethics apply additive or multiplicative modifiers.

---

## 4. Civic Modifiers
Civics apply **strong biases** or **hard constraints**.

Examples:
- Distinguished Admiralty → fleet cap usage high
- Technocracy → research priority high
- Merchant Guilds → trade value priority high

---

## 5. Trait Modifiers
Traits apply **micro‑modifiers**.

Examples:
- Intelligent → +10% tech priority
- Strong → +10% army priority
- Thrifty → +10% trade priority

---

## 6. Origin Overrides
Origins may **replace** parts of the ruleset.

Examples:
- Synthetic Fertility → robot‑first pop logic
- Void Dwellers → habitat‑first expansion
- Necrophage → prepatent pop management
- Shattered Ring → tall → megastructure arc

Origins define:
- Pop growth logic
- Early/mid/late game arcs
- Colonization rules
- Economic structure
- Diplomatic constraints

---

## 7. Government Logic
Government type defines **how decisions are made**.

Examples:
- Imperial → ruler 80% weight
- Democratic → 5–6 leader shards weighted
- Oligarchic → 2–4 strong voices
- Hive → unified voice
- Machine → logic modules

---

## 8. Phase Adjustments
Game phases:
- Early (0–40)
- Mid (40–120)
- Late (120+)

Each phase adjusts priorities.

---

## 9. Meta Rules (Version-Locked)
Patch‑specific expert strategies for 4.3.4.

The LLM must apply meta rules but cannot invent new ones.

---

## 10. Validation Requirements
A ruleset is valid if:
- It matches game version 4.3.4
- It contains no undefined mechanics
- It respects fog‑of‑war
- It contains no contradictory modifiers
