# Clausewitz Mod Development

> **Use when:** Creating or modifying Stellaris Clausewitz mod files in the `mod/` directory —
> state exporter, action executor, event hooks, or the game ↔ Python bridge.

Your full coding standards are in `.github/copilot-instructions.md` and `CLAUDE.md`.
Spec docs: `docs/EXPORTER_SPEC.md` and `docs/EXECUTOR_SPEC.md`.

---

## Quick Start Checklist

- [ ] Read `docs/EXPORTER_SPEC.md` for state snapshot format
- [ ] Read `docs/EXECUTOR_SPEC.md` for directive format and action mapping
- [ ] Verify fog-of-war compliance for any state being exported
- [ ] Check intel-level filtering rules

---

## Clausewitz Scripting Fundamentals

### File Structure
- Mod folder: `Documents/Paradox Interactive/Stellaris/mod/`
- Two descriptor files required: `modname.mod` (root) + `descriptor.mod` (inside mod folder)
- Encoding: **UTF-8** for all files; **UTF-8 with BOM** for localisation/name lists
- Indentation: **1 tab** per level (vanilla convention)
- Comments: `#` character

### Descriptor Format
```
name="Stellaris Overmind"
path="mod/stellaris_overmind"
tags={
	"AI"
	"Gameplay"
}
picture="thumbnail.png"
supported_version="v4.3.*"
```

### Clausewitz Script Syntax
The `=` operator is used for boolean checks, assignments, scope changes, and effect activation:
```
capital_scope = {                       # scope change to capital planet
	every_deposit = {                   # iterate all deposits
		limit = {                       # filter condition
			category = deposit_cat_blockers  # boolean comparison
		}
		remove_deposit = yes            # activate effect
	}
}
```

---

## Scopes (CRITICAL)

### System Scopes
- `THIS` — current scope
- `PREV` — previous scope (chainable: `prevprev`, up to `prevprevprevprev`)
- `FROM` — scope from which current script was called (chainable up to ×4)
- `ROOT` — main scope of the script (e.g., the planet in a `planet_event`)

### Scope Chaining (dot notation)
```
owner.capital_scope.solar_system = { ... }
# equivalent to:
owner = { capital_scope = { solar_system = { ... } } }
```

### Scope Types
| Type | Examples | Description |
|------|----------|-------------|
| `country` | `owner`, `controller`, `space_owner`, `overlord` | An empire |
| `planet` | `capital_scope`, `home_planet`, `orbit`, `star` | Planet, star, habitat, ringworld |
| `galactic_object` | `solar_system` | A solar system |
| `fleet` | `fleet`, `last_created_fleet` | A fleet (every ship belongs to one) |
| `ship` | `starbase`, `last_created_ship` | A ship, including starbases |
| `pop` | `pop`, `unhappiest_pop` | A pop |
| `leader` | `leader`, `ruler` | A leader |
| `species` | `species`, `owner_species` | A species |
| `army` | `last_created_army` | An army |
| `war` | `war` | A war (`attacker`, `defender` subscopes) |
| `federation` | `federation`, `alliance` | A federation |

### Scope Existence Check
Always check scope exists before using:
```
planet = {
	exists = owner
	owner = { ... }
}
```

### Scope-Changing Triggers and Effects
- `any_*` triggers — iterate and return yes if any match: `any_owned_planet = { is_planet_class = pc_gaia }`
- `every_*` effects — apply to all matching: `every_owned_planet = { limit = { ... } ... }`
- `random_*` effects — apply to one random match

---

## Events

### Event Types
- `country_event` — fires for a country scope
- `planet_event` — fires for a planet scope
- `fleet_event` — fires for a fleet scope
- `ship_event` — fires for a ship scope
- `pop_event` — fires for a pop scope

### Event Structure
```
namespace = overmind

country_event = {
	id = overmind.1
	title = "overmind.1.title"
	desc = "overmind.1.desc"
	picture = GFX_evt_ai_01
	is_triggered_only = yes    # fired from on_action or other event
	hide_window = yes          # no popup — silent event

	trigger = {
		# conditions that must be true
		is_ai = yes
	}

	immediate = {
		# effects that run immediately when event fires
	}

	option = {
		name = "overmind.1.option.a"
		# effects when this option is chosen
	}
}
```

### Event Targets (saving scopes for later)
```
save_event_target_as = my_target
# later:
event_target:my_target = { ... }
```

---

## On Actions (Event Triggers)

### Key On Actions for Overmind
| On Action | Scope | Use For |
|-----------|-------|---------|
| `on_game_start` | none | Initial mod setup |
| `on_monthly_pulse_country` | `this = country` | Regular AI tick (heartbeat) |
| `on_yearly_pulse_country` | `this = country` | Annual strategy review |
| `on_war_beginning` | `root = country, from = war` | War declared trigger |
| `on_war_ended` | `root = loser, from = winner` | Peace signed |
| `on_first_contact` | `this = empire1, from = empire2` | New empire discovered |
| `on_fleet_detected` | `this = country, from = fleet` | Enemy fleet spotted |
| `on_colonized` | `scope = planet` | Colony established |
| `on_tech_increased` | `this = country` | Tech researched |
| `on_policy_changed` | `this = country` | Policy changed |
| `on_entering_system_fleet` | `scope = fleet, from = system` | Fleet enters system |
| `on_space_battle_won/lost` | `this = winner/loser` | Battle result |

### Firing Behavior
- `events = { }` — fires ALL events whose triggers pass
- `random_events = { }` — fires ONE random event from those whose triggers pass

### Adding to On Actions
On actions use MERGE — you can add events by creating a new file:
```
# mod/common/on_actions/overmind_on_actions.txt
on_monthly_pulse_country = {
	events = {
		overmind.100   # our heartbeat event
	}
}
```

---

## File Override Rules

| Type | Meaning |
|------|---------|
| **FIOS** | First In, Only Served — first loaded file wins |
| **LIOS** | Last In, Only Served — last loaded file wins (can override) |
| **DUPL** | Duplicates — creates copies, can't individually override |
| **NO** | Cannot individually overwrite |
| **MERGE** | Entries are merged (on_actions only) |

Files load in ASCIIbetical order of filename. Prefix with `zzz_` to load last (LIOS override).

### Key Override Types
- Events: **FIOS** (first version loaded wins)
- On actions: **MERGE**
- Defines: **LIOS** (our overrides win)
- Decisions: **LIOS**
- Policies: **LIOS**
- Technologies: **LIOS** (mostly)

---

## Bridge Architecture

### File Locations
```
mod/ai_bridge/state_snapshot.json    ← Exporter writes (Clausewitz → Python)
mod/ai_bridge/directive.json         ← Engine writes, Executor reads (Python → Clausewitz)
```

### State Export (Clausewitz → Python)
The exporter uses events + on_actions to gather known game state and write JSON.
Key mechanism: use `log = "..."` or scripted effects to write to files.

### Directive Execution (Python → Clausewitz)
The executor reads directive.json using `on_monthly_pulse_country` and applies
the appropriate Clausewitz effects.

---

## Fog-of-War Rules (CRITICAL)

### Always Visible (own empire)
- Own resources, fleets, planets, starbases, diplomatic relations

### Intel-Gated (other empires)
| Intel Level | Visible |
|---|---|
| None | Name, attitude only |
| Low | Government type, ethics |
| Medium | Fleet power estimate, economy class |
| High | Detailed fleet comp, tech level, economy values |
| Full | Everything |

### Never Visible
- Hidden fleets (outside sensor range)
- Unknown systems (not surveyed/explored)
- Crisis spawn info
- AI personality flags / internal Stellaris AI data

---

## Mod File Structure
```
mod/stellaris_overmind/
	descriptor.mod
	thumbnail.png
	common/
		on_actions/
			overmind_on_actions.txt     # event triggers
		scripted_effects/
			overmind_effects.txt        # reusable effect blocks
		scripted_triggers/
			overmind_triggers.txt       # reusable trigger blocks
		defines/
			overmind_defines.txt        # game constant overrides
	events/
		overmind_events.txt             # all mod events
	localisation/english/
		overmind_l_english.yml          # text strings
	ai_bridge/
		state_snapshot.json             # exporter output
		directive.json                  # engine output
```

---

## Testing & Debugging

### Console Commands
- `observe` — switch to observer mode (see all empires)
- `run <filename.txt>` — execute script from Documents folder
- `reloadevents` — reload all events (hot reload)
- `reload text` — reload localisation
- `trigger_docs` — generate `scopes.log` with all scope documentation

### Error Log
- Location: `Documents/Paradox Interactive/Stellaris/logs/error.log`
- Check after every change — scope errors, missing files, syntax errors

---

## Rules for Overmind Mod

- State exporter must filter ALL data through intel-level checks
- Action executor must validate against the action whitelist before executing
- JSON output must be deterministic (sorted keys, consistent formatting)
- One JSON file per empire (overwritten each tick)
- Export triggers: war, borders, fleets, economy thresholds, diplomacy, 90-day heartbeat
- Prefix all mod files with `overmind_` to avoid conflicts
- Use `is_triggered_only = yes` + `hide_window = yes` for silent AI events
- Always check `is_ai = yes` in triggers — our events should only fire for AI empires
