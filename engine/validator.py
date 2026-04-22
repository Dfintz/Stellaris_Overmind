"""
Validator — Stellaris 4.3.4 LLM AI Overhaul

Validates LLM directives against the ruleset, fog‑of‑war constraints,
game version, meta rules, and origin/civic constraints before they are
sent to the Action Executor.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.ruleset_generator import ALLOWED_ACTIONS, GAME_VERSION

# Weapons the LLM must never recommend (dead in 4.3)
FORBIDDEN_WEAPONS: list[str] = [
    "disruptor",
    "disruptors",
    "arc_emitter",
]

# Fleet compositions the LLM must never recommend
FORBIDDEN_FLEET_PATTERNS: list[str] = [
    "corvette_only",
    "all_corvettes",
]


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]


def validate_directive(
    directive: dict,
    ruleset: dict,
    state: dict,
) -> ValidationResult:
    """
    Validate a directive dict before execution.

    Checks:
    1. Action is in the allowed list.
    2. Ruleset version matches game version.
    3. Target (if any) is known to the empire (fog-of-war).
    4. Origin / civic constraints are not violated.
    5. Reason is present and cites ruleset elements.
    6. Meta-forbidden patterns are rejected.
    7. Fleet composition meta violations are flagged.
    """
    errors: list[str] = []
    warnings: list[str] = []

    action = directive.get("action", "")
    target = directive.get("target")
    reason = directive.get("reason", "")
    params = directive.get("parameters", {})
    overrides = ruleset.get("overrides", {})
    modifiers = ruleset.get("modifiers", {})

    # --- 1. Action whitelist ---
    if action not in ALLOWED_ACTIONS:
        errors.append(f"Unknown action '{action}'. Allowed: {ALLOWED_ACTIONS}")

    # --- 2. Version lock ---
    ruleset_version = ruleset.get("version", "")
    if ruleset_version != GAME_VERSION:
        errors.append(
            f"Ruleset version '{ruleset_version}' does not match "
            f"game version '{GAME_VERSION}'"
        )

    # --- 3. Fog-of-war: target visibility ---
    # In AI mode, targets are guidance for the native AI, not direct commands.
    # Only EXPAND truly needs spatial validation (claiming specific systems).
    # COLONIZE targets are planet suggestions the native AI interprets.
    _SPATIAL_ACTIONS = {"EXPAND", "BUILD_STARBASE", "COLONIZE"}
    # Empire-targeting actions must reference known empires
    _EMPIRE_ACTIONS = {"DIPLOMACY", "ESPIONAGE", "PREPARE_WAR"}
    if target is not None and action in _SPATIAL_ACTIONS:
        raw_colonies = state.get("colonies", [])
        known_systems: set[str] = set()
        for c in raw_colonies:
            if isinstance(c, dict):
                name = c.get("name") or c.get("system") or c.get("planet")
                if name:
                    known_systems.add(str(name))
            elif c:
                known_systems.add(str(c))
        known_empires = {
            e.get("name") for e in state.get("known_empires", [])
            if isinstance(e, dict) and e.get("name")
        }
        # Also accept systems from known starbases and fleet locations
        known_fleet_systems = {
            f.get("location_system")
            for f in state.get("fleets", [])
            if f.get("location_system")
        }
        known_targets = known_systems | known_empires | known_fleet_systems
        if target not in known_targets:
            errors.append(
                f"Target '{target}' is not in known systems or empires — "
                "possible fog-of-war violation"
            )

    # --- 3b. Empire-targeting actions must reference known empires ---
    # Skip if target contains unresolved localization keys (%ADJ% etc.)
    if (
        target is not None
        and action in _EMPIRE_ACTIONS
        and "%" not in target
    ):
        known_empires = {
            e.get("name") for e in state.get("known_empires", [])
            if isinstance(e, dict) and e.get("name")
        }
        if target not in known_empires:
            errors.append(
                f"Target empire '{target}' is not known — "
                "possible fog-of-war violation"
            )

    # --- 4. Origin constraints ---
    _validate_origin_constraints(action, params, overrides, errors)

    # --- 5. Civic constraints ---
    _validate_civic_constraints(action, params, modifiers, errors)

    # --- 6. Reason must not be empty ---
    if not reason.strip():
        errors.append("Directive reason is empty — LLM must cite ruleset elements")

    # --- 7. Meta-forbidden patterns ---
    _validate_meta_forbidden(action, params, reason, errors, warnings)

    # --- 8. Phase-appropriate checks ---
    _validate_phase_logic(action, state, ruleset, warnings)

    # --- 9. Resource feasibility ---
    _validate_resource_feasibility(action, state, warnings)

    # --- 10. Capacity checks ---
    _validate_capacity(action, state, warnings)

    # --- 11. Genocidal diplomacy block ---
    _validate_genocidal_constraints(action, modifiers, overrides, errors)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _validate_origin_constraints(
    action: str,
    params: dict,
    overrides: dict,
    errors: list[str],
) -> None:
    """Check origin-specific hard constraints."""
    # Void Dwellers can only colonize habitats
    if action == "COLONIZE" and overrides.get("colonization_rules") == "habitats_only":
        if params.get("planet_type") and params["planet_type"] != "habitat":
            errors.append(
                "Void Dwellers origin restricts colonization to habitats only"
            )

    # Life-Seeded early colonization restricted to gaia
    if action == "COLONIZE" and overrides.get("colonization_rules") == "gaia_only_early":
        if params.get("planet_type") and params["planet_type"] not in ("gaia", "habitat"):
            errors.append(
                "Life-Seeded origin restricts early colonization to Gaia worlds"
            )

    # Endbringers can only pursue psionic ascension
    if overrides.get("ascension_lock") == "psionic":
        if params.get("ascension_path") and params["ascension_path"] != "psionic":
            errors.append(
                "Endbringers origin blocks all ascension paths except Psionic"
            )

    # Cybernetic Creed can only pursue cybernetic ascension
    if overrides.get("ascension_lock") == "cybernetic":
        if params.get("ascension_path") and params["ascension_path"] != "cybernetic":
            errors.append(
                "Cybernetic Creed origin blocks all ascension paths except Cybernetic"
            )

    # Necrophage growth logic
    if overrides.get("chambers_block_necrophage_growth"):
        if params.get("growth_target") == "necrophage_primary":
            errors.append(
                "Necrophage Chambers of Elevation block pop growth for "
                "necrophage species in 4.3 — grow secondary species instead"
            )


def _validate_civic_constraints(
    action: str,
    params: dict,
    modifiers: dict,
    errors: list[str],
) -> None:
    """Check civic-specific hard constraints."""
    # Inward Perfection blocks diplomacy
    if action == "DIPLOMACY" and modifiers.get("diplomacy_blocked"):
        errors.append("Inward Perfection civic blocks diplomatic actions")

    # Barbaric Despoilers can only do raiding wars
    if action == "PREPARE_WAR" and modifiers.get("war_type") == "raiding_only":
        if params.get("war_goal") and params["war_goal"] != "raiding":
            errors.append(
                "Barbaric Despoilers civic restricts wars to raiding type only"
            )

    # Augmentation Bazaars locks ascension to cybernetic
    if modifiers.get("ascension_lock") == "cybernetic":
        if params.get("ascension_path") and params["ascension_path"] != "cybernetic":
            errors.append(
                "Augmentation Bazaars civic blocks all ascension except Cybernetic"
            )


def _validate_meta_forbidden(
    action: str,
    params: dict,
    reason: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Reject meta-forbidden patterns from META_4.3.4.md §10."""
    reason_lower = reason.lower()

    # Disruptors are dead in 4.3
    if action == "BUILD_FLEET":
        weapon = params.get("weapon_type", "").lower()
        if weapon in FORBIDDEN_WEAPONS:
            errors.append(
                f"Weapon '{weapon}' is dead in 4.3 — ~300 days to kill a corvette. "
                "Use autocannon+plasma, kinetic artillery, or tachyon lance instead."
            )
        # Also check if disruptors mentioned in reason
        for fw in FORBIDDEN_WEAPONS:
            if fw in reason_lower:
                warnings.append(
                    f"Reason mentions '{fw}' which is dead in 4.3. "
                    "Reconsider weapon choice."
                )

    # Corvette-only fleets are punished by titan AoE
    if action == "BUILD_FLEET":
        composition = params.get("composition", "")
        if isinstance(composition, str) and composition.lower() in FORBIDDEN_FLEET_PATTERNS:
            warnings.append(
                "Corvette-only fleets are punished by titan AoE in 4.3. "
                "Consider mixed composition with fleet splitting."
            )

    # Pre-4.3 assumptions in reason
    pre43_red_flags = [
        "resources from jobs",
        "25% planetary ascension",
        "+20% stability",
        "demotion time",
    ]
    for flag in pre43_red_flags:
        if flag in reason_lower:
            warnings.append(
                f"Reason references '{flag}' which may be a pre-4.3 mechanic. "
                "Verify against 4.3.4 rules."
            )


def _validate_phase_logic(
    action: str,
    state: dict,
    ruleset: dict,
    warnings: list[str],
) -> None:
    """Warn about phase-inappropriate actions."""
    year = state.get("year", 2200)

    # Late game: should be preparing for crisis
    if year >= 2350:
        economy = state.get("economy", {})
        alloys = economy.get("alloys", 0)
        if alloys < 100 and action not in ("IMPROVE_ECONOMY", "CONSOLIDATE"):
            warnings.append(
                "Year 2350+: alloy production is low. "
                "Consider IMPROVE_ECONOMY or CONSOLIDATE for crisis preparation."
            )


def _validate_resource_feasibility(
    action: str,
    state: dict,
    warnings: list[str],
) -> None:
    """Warn when the empire likely cannot afford an action."""
    economy = state.get("economy", {})
    monthly = economy.get("monthly_net", {})

    if action == "BUILD_FLEET":
        alloys = economy.get("alloys", 0)
        alloy_income = monthly.get("alloys", 0)
        if alloys < 50 and alloy_income <= 0:
            warnings.append(
                "BUILD_FLEET: alloy stockpile is very low and income is negative. "
                "Consider IMPROVE_ECONOMY first."
            )

    elif action == "BUILD_STARBASE":
        influence = economy.get("influence", 0)
        if influence < 75:
            warnings.append(
                "BUILD_STARBASE: influence stockpile is low (<75). "
                "Starbases cost 75-200 influence."
            )

    elif action == "COLONIZE":
        food = economy.get("food", 0)
        food_income = monthly.get("food", 0)
        if food < 50 and food_income <= 0:
            warnings.append(
                "COLONIZE: food stockpile and income are low. "
                "New colonies consume food for growth."
            )

    elif action == "EXPAND":
        influence = economy.get("influence", 0)
        if influence < 50:
            warnings.append(
                "EXPAND: influence is low (<50). "
                "Outposts and claims require influence."
            )


def _validate_capacity(
    action: str,
    state: dict,
    warnings: list[str],
) -> None:
    """Warn about capacity limits."""
    nav_cap = state.get("naval_capacity", {})

    if action == "BUILD_FLEET":
        used = nav_cap.get("used_naval_capacity", 0)
        # Naval cap is not directly in state; warn if already high usage
        if used > 0:
            fleet_power = sum(f.get("power", 0) for f in state.get("fleets", []))
            if used > 200 and fleet_power > 50000:
                warnings.append(
                    "Naval capacity usage is very high. "
                    "Consider anchorage starbases or traditions for more cap."
                )

    if action == "BUILD_STARBASE":
        sb_cap = nav_cap.get("starbase_capacity", 0)
        current_starbases = len(state.get("starbases", []))
        if sb_cap > 0 and current_starbases >= sb_cap:
            warnings.append(
                f"Starbase capacity is full ({current_starbases}/{sb_cap}). "
                "Upgrade existing outpost or increase cap via tech/traditions."
            )


def _validate_genocidal_constraints(
    action: str,
    modifiers: dict,
    overrides: dict,
    errors: list[str],
) -> None:
    """Block diplomatic actions for genocidal empires."""
    is_genocidal = modifiers.get("genocidal", False) or modifiers.get("no_diplomacy", False)
    if not is_genocidal:
        return

    blocked_actions = ("DIPLOMACY",)
    if action in blocked_actions:
        errors.append(
            "Genocidal empire (Fanatic Purifiers / Devouring Swarm / "
            "Determined Exterminator) cannot perform diplomatic actions."
        )
