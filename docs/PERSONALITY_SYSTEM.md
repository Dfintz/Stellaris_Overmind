# Stellaris 4.3.4 – Personality System
Defines how the LLM simulates human‑like strategic behavior using personality shards,
multi-agent council, and Clausewitz AI personality overrides.

For **AI empires**, the personality system steers Stellaris’ native AI via personality
overrides + stat modifiers — the LLM decides macro strategy while the native AI
handles micro (build queues, research, fleets).

For the **player**, the personality system produces strategic suggestions displayed
in the Rich TUI.

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

## 8. Clausewitz AI Personality Overrides

The mod includes four Clausewitz personality variants that Stellaris’ native AI reads
directly.  The LLM’s decision sets stance flags, and the mod event switches the
active personality:

| Personality | Aggression | Combat Bravery | Use Case |
|---|---|---|---|
| `overmind_controlled` | 1.0 | 1.5 | Balanced (default) |
| `overmind_controlled_aggressive` | 2.0 | 2.0 | BUILD_FLEET, PREPARE_WAR |
| `overmind_controlled_defensive` | 0.25 | 1.0 | DEFEND, CONSOLIDATE |
| `overmind_controlled_assault` | 3.0 | 3.0 | Active war (rarely retreat) |

All variants use 4.3.4 weapon meta: kinetic weapons, shields > armor,
autocannon+plasma for anti-corvette.

---

## 9. Player Mode: Strategic Advisor

In player mode, the personality system produces a **suggestion** instead of
override flags.  The suggestion includes:
- The recommended macro action (e.g. FOCUS_TECH)
- Reasoning citing ruleset elements
- Specific tips (e.g. “Build research labs on your capital”)

Displayed in the TUI’s yellow “Suggestion” panel and saved to `overmind_suggestion.txt`.
