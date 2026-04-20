# Stellaris 4.3.4 – Personality System
Defines how the LLM simulates human‑like strategic behavior using personality shards,
multi-agent council, and Clausewitz AI personality overrides.

---

## 1. Purpose
- Give each empire a unique strategic identity.
- Reflect ethics, civics, traits, origins, and government.
- Enable adaptive, believable behavior.
- Control Stellaris' built-in AI via native personality system.

---

## 2. Personality Layers

### 2.1 Empire Personality
Generated from:
- Ethics
- Civics
- Traits
- Origin
- Government

Defines:
- Core values
- Strategic priorities
- Diplomatic tendencies
- War philosophy
- Economic philosophy
- Risk tolerance

---

## 3. Leader Personality Shards

### 3.1 Ruler
- Long‑term goals
- Empire‑wide direction

### 3.2 Admirals
- War logic
- Fleet aggression
- Risk tolerance

### 3.3 Governors
- Economy
- Stability
- Planet development

### 3.4 Scientists
- Tech priorities
- Exploration

### 3.5 Generals
- Ground warfare
- Invasion logic

---

## 4. Government Weighting

### Imperial
- Ruler: 80%
- Others: 20%

### Democratic
- 5–6 voices weighted
- High internal debate

### Oligarchic
- 2–4 strong voices

### Hive Mind
- Unified voice

### Machine Intelligence
- Logic modules (war, economy, tech)

---

## 5. Decision Synthesis
Each shard outputs an opinion:

```
<ROLE>: <recommendation>
<reason>
```

Government logic merges them into:

```
ACTION: <one>
TARGET: <optional>
REASON: <merged reasoning>
```

---

## 6. Adaptation Over Time
Personalities evolve with:
- Game phase (early/mid/late)
- Threats
- Opportunities
- Economic state
- Diplomatic landscape

---

## 7. Anti‑Poisoning
Personalities must:
- Obey ruleset
- Obey meta
- Use only known information
- Never invent mechanics
