# Stellaris 4.3.4 – Action Executor Specification
The executor influences Stellaris’ native AI via Clausewitz personality overrides, stat
modifiers, and automated policy enforcement.  It does **not** bypass the native AI’s
build queues, research picks, or fleet construction — those remain under native control.

For the **player**, the engine acts as a strategic advisor: it displays suggestions
in the Rich TUI and writes `overmind_suggestion.txt`, but never executes actions.

---

## 1. Purpose
- Convert LLM macro actions into Clausewitz personality stance flags + stat modifiers.
- Override AI personality (aggressiveness, weapon preferences, combat bravery) based on directive.
- Enforce policies and edicts matching the strategic directive.
- Prevent modifier stacking (clear all previous modifiers before each action).
- Support per-country scoping for multi-empire AI mode.
- In **player mode**, display human-readable suggestions (no direct execution).

**Key principle**: the LLM decides *what* to prioritise; Stellaris’ native AI decides
*how* to execute it (which districts to build, which techs to pick, etc.).

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

### 3.1 AI Mode: Directive → Personality Override
The Python engine writes a directive JSON per AI country.
The mod event reads the directive and:
1. Clears all previous modifiers and stance flags (`overmind_clear_modifiers`)
2. Sets the new personality stance flag (aggressive / defensive / full assault)
3. Applies a temporary stat modifier (180 days) that nudges native AI priorities
4. Enforces relevant policies (if available for the empire type)

Stellar’s native AI then uses these personality weights + modifiers to make its own
micro-decisions (build order, research queue, fleet composition, colonisation order).

### 3.2 Player Mode: Directive → Suggestion
The engine writes `overmind_suggestion.txt` with:
- The recommended action and reason
- Specific tips for what the player should do (e.g. “Build research labs on your capital”)
- Displayed prominently in the Rich TUI’s yellow “Suggestion” panel

No console commands or mod effects are executed for the player.

### 3.3 Mod Event (Monthly Pulse)
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
- Personality overrides applied live via mod events (no pausing)
- AI empires: directive JSON written per country; mod reads on monthly pulse
- Player: suggestion displayed after each LLM decision (~3s with Ollama)
- Cooldown: mod event fires monthly; engine polls every 2s for new saves
- Empire config auto-detected from save file (no manual setup needed)
