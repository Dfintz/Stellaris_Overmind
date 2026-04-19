---
name: clausewitz-mod
description: "Use when creating or modifying Clausewitz mod files — state exporter, action executor, event hooks, scopes, on_actions, or the game-Python bridge."
---

# Clausewitz Mod Development

> **Use when:** Creating or modifying Stellaris Clausewitz mod files in the `mod/` directory.

Read `.github/skills/clausewitz-mod/SKILL.md` for the full reference including
scope types, on_actions, event structure, override rules, and bridge architecture.

---

## Key Concepts

### Scopes
- `THIS`, `PREV` (×4), `FROM` (×4), `ROOT` — system scopes
- Types: country, planet, fleet, ship, pop, leader, galactic_object, army, species, war, federation
- Chaining: `owner.capital_scope.solar_system = { ... }`
- Always `exists = <scope>` before using

### Events
- Types: `country_event`, `planet_event`, `fleet_event`, `ship_event`, `pop_event`
- Use `is_triggered_only = yes` + `hide_window = yes` for silent AI events
- Namespace: `overmind`

### On Actions (key ones for this mod)
- `on_monthly_pulse_country` — heartbeat (this = country)
- `on_yearly_pulse_country` — annual review
- `on_war_beginning`, `on_war_ended` — war triggers
- `on_first_contact`, `on_fleet_detected` — contact/intel
- `on_colonized`, `on_tech_increased`, `on_policy_changed`

### Override Rules
- Events: FIOS (first in wins)
- On actions: MERGE (additive)
- Defines: LIOS (last in wins)
- Most common/: LIOS

### Fog-of-War
- CRITICAL: never export hidden data
- Filter by intel level: None → Low → Medium → High → Full
- Never visible: hidden fleets, unknown systems, crisis info, AI personality flags

### Bridge
```
mod/ai_bridge/state_snapshot.json    ← Exporter (Clausewitz → Python)
mod/ai_bridge/directive.json         ← Engine (Python → Clausewitz)
```
