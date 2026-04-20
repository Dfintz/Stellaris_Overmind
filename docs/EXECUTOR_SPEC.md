# Stellaris 4.3.4 – Action Executor Specification
The executor applies LLM decisions inside the game via Clausewitz scripted effects,
AI personality overrides, and automated policy enforcement.

---

## 1. Purpose
- Convert LLM macro actions into Clausewitz script actions.
- Override AI personality (aggressiveness, weapon preferences, combat bravery) based on directive.
- Enforce policies and edicts matching the strategic directive.
- Prevent modifier stacking (clear all previous modifiers before each action).
- Support per-country scoping for multi-empire AI mode.

---

## 2. Accepted Actions
The LLM may output only:

```
EXPAND
BUILD_FLEET
IMPROVE_ECONOMY
FOCUS_TECH
DIPLOMACY
ESPIONAGE
PREPARE_WAR
DEFEND
CONSOLIDATE
COLONIZE
BUILD_STARBASE
```

---

## 3. Execution Pipeline

### 3.1 Directive → Console Commands
The Python engine writes `ai_commands.txt` to the Stellaris user data directory:
```
effect set_variable = { which = overmind_action value = N }
effect set_country_flag = overmind_directive_ready
```

### 3.2 Mod Event (Monthly Pulse)
Event `overmind.100` fires on `on_monthly_pulse_country`:
1. Checks `has_country_flag = overmind_directive_ready` (per-country, not global)
2. Reads `overmind_action` variable (country-scoped)
3. Calls the matching scripted effect
4. Clears the flag + variable

### 3.3 Scripted Effect
Each action effect:
1. Calls `overmind_clear_modifiers` (removes all 11 previous modifiers + personality flags)
2. Sets personality stance flag (`overmind_aggressive` / `overmind_defensive` / `overmind_full_assault`)
3. Applies temporary modifier (180 days)
4. Enforces relevant policies (if available for the empire type)

### 3.4 AI Personality Override
Four Clausewitz personality variants (weight 10000–30000):
- `overmind_controlled` — balanced (kinetic weapons, shields > armor, combat_bravery=1.5)
- `overmind_controlled_aggressive` — aggressiveness=2.0, military_spending=1.5, conqueror+dominator
- `overmind_controlled_defensive` — aggressiveness=0.25, high diplomatic acceptance
- `overmind_controlled_assault` — combat_bravery=3.0 (rarely retreat), during active wars

---

## 4. Action Details

### 4.1 BUILD_FLEET
- Modifier: +10% naval cap, +5% ship speed
- Personality: aggressive (aggressiveness=2.0)
- Sub-action: 0=balanced, 1=corvette swarm, 2=battleship focus

### 4.2 PREPARE_WAR
- Modifier: +10% alloy production, +5% fire rate
- Personality: aggressive → full assault if `is_at_war`
- Policy: Unrestricted Wars + Militarist economy

### 4.3 FOCUS_TECH
- Modifier: +5% research speed, +1 tech alternatives
- Policy: Academic Privilege living standard

### 4.4 DIPLOMACY
- Modifier: +1 envoy, +10% diplo weight
- Policy: Cooperative diplomatic stance

### 4.5 CONSOLIDATE
- Modifier: +5 stability, +10% amenities
- Personality: defensive (aggressiveness=0.25)
- Policy: Civilian economic policy

### 4.6 COLONIZE
- Modifier: +25% colony dev speed, +5% pop growth
- Sub-action: 0=any, 1=habitats only, 2=gaia preferred

---

## 5. Validation Layer
Reject actions if:
- They violate fog‑of‑war
- They contradict origin/civic rules
- They require unseen information
- They reference forbidden weapons (disruptors, arc emitters)

---

## 6. Execution Timing
- Actions applied live (no pausing)
- Console commands auto-written after each LLM decision
- In-game: `run ai_commands.txt` or `scripts/auto_execute.py` for full automation
- Cooldown: mod event fires monthly; engine polls every 2s for new saves
