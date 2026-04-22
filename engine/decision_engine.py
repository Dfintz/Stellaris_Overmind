"""
Decision Engine — Stellaris 4.3.4 LLM AI Overhaul

Receives a ruleset + personality + known game state + triggering event,
queries the LLM, and produces exactly one validated macro action.

The prompt includes:
  - Composite ruleset (ethics/civics/traits/origin)
  - Personality profile (war willingness, trade focus, etc.)
  - Game-phase priorities (economy, fleet, expansion guidance)
  - Fleet composition meta (weapon verdicts, fleet templates)
  - Current game state (fog-of-war filtered)
  - Triggering event (if any)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from engine.ruleset_generator import (
    ALLOWED_ACTIONS,
    get_espionage_phase_priority,
    get_fleet_template,
    get_phase_priorities,
    get_weapon_meta,
)
from engine.strategic_knowledge import (
    get_ascension_perk_guidance,
    get_edict_guidance,
    get_megastructure_guidance,
    get_policy_guidance,
    get_starbase_guidance,
    get_tech_priorities,
    get_tradition_guidance,
)

# Prompt budget — approximate token count limits
# Qwen2.5-Omni-3B context: 4096 tokens; 7B: 8192 tokens
# ~4 chars per token on average
MAX_PROMPT_CHARS = 12000  # ~3000 tokens, leaves room for response
MAX_COLONIES_IN_PROMPT = 10
MAX_EMPIRES_IN_PROMPT = 8
MAX_FLEETS_IN_PROMPT = 5


@dataclass
class Directive:
    """A single macro‑strategic directive produced by the LLM."""

    action: str
    target: str | None = None
    reason: str = ""
    parameters: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "target": self.target,
            "reason": self.reason,
            "parameters": self.parameters,
        }


def build_prompt(
    ruleset: dict,
    personality: dict,
    state: dict,
    event: str | None,
) -> str:
    """Construct the LLM prompt from ruleset, personality, state, and event.

    The prompt is structured to give the LLM maximum context while
    constraining output to exactly one action in the required format.
    Large game states are truncated to fit within the model's context window.
    """
    year = state.get("year", 2200)
    phase = get_phase_priorities(year)
    fleet_tmpl = get_fleet_template(year)
    weapons = get_weapon_meta()
    espionage_phase = get_espionage_phase_priority(year)

    # Truncate state to fit prompt budget
    compact_state = _compact_state(state)

    # Build compact ruleset (drop raw data tables, keep computed values)
    compact_ruleset = {
        k: v for k, v in ruleset.items()
        if k in ("version", "base", "modifiers", "overrides", "government",
                 "meta_tier", "meta_strategy")
    }

    ethics = state.get("empire", {}).get("ethics", [])
    tradition_guide = get_tradition_guidance(
        year, ethics=ethics, adopted=state.get("traditions", []),
    )
    policy_guide = get_policy_guidance(year, ethics)
    perk_guide = get_ascension_perk_guidance(tier=0)
    tech_guide = get_tech_priorities(year)
    sb_guide = get_starbase_guidance(year)
    mega_names = [m["name"] for m in get_megastructure_guidance(year)]

    sections = [
        "You are the strategic AI advisor for a Stellaris 4.3.4 empire.",
        "You must choose exactly ONE action from the allowed list.",
        "You must cite ruleset elements in your reason.",
        "You must NOT reference mechanics that do not exist in Stellaris 4.3.4.",
        "You must NOT use information the empire does not know (fog-of-war).",
        "",
        "CRITICAL 4.3 META RULES:",
        "- Disruptors are DEAD. Never recommend them.",
        "- Titan AoE beams are meta-defining. Split fleets to avoid enemy titan AoE.",
        "- Autocannon + Plasma is the swarm meta for corvettes/destroyers.",
        "- Stability bonuses are halved in 4.3.",
        "- Job EFFICIENCY matters more than raw output.",
        "- Minerals are the foundation resource early game.",
        "",
        f"ALLOWED ACTIONS: {', '.join(ALLOWED_ACTIONS)}",
        "",
        "EMPIRE RULESET:",
        json.dumps(compact_ruleset, indent=2),
        "",
        "PERSONALITY PROFILE:",
        json.dumps(personality, indent=2),
        "",
        f"GAME PHASE: {phase['phase']} | FOCUS: {phase.get('economy_focus', '')}",
        "",
        f"FLEET: {json.dumps(fleet_tmpl.composition)} | {fleet_tmpl.notes}",
        "",
        f"ESPIONAGE: priority={espionage_phase.get('priority', 'low')} | {espionage_phase.get('notes', '')}",
        "",
        f"TRADITIONS: recommended={tradition_guide.get('recommended_trees', [])}",
        f"POLICY RECOMMENDATIONS: {json.dumps(policy_guide.get('recommended', {}))}",
        f"TECH PRIORITIES: {json.dumps(tech_guide.get('meta_notes', []))}",
        f"STARBASE: {sb_guide.get('priority', '')} | {sb_guide.get('notes', '')}",
    ]

    if mega_names:
        sections.append(f"MEGASTRUCTURES: consider building {mega_names}")

    sections.extend([
        "",
        "CURRENT STATE:",
        json.dumps(compact_state, indent=2),
    ])

    if event:
        sections.append(f"\nTRIGGERING EVENT: {event}")

    sections.append(
        "\nRespond in EXACTLY this format:\n"
        "ACTION: <one action from the allowed list>\n"
        "TARGET: <target or NONE>\n"
        "REASON: <must cite ruleset elements and meta rules>"
    )
    return "\n".join(sections)


def _compact_state(state: dict) -> dict:
    """Truncate game state to fit within prompt budget.

    Keeps the most strategically relevant data:
    - Full economy (with monthly net)
    - Top N fleets by power
    - Top N known empires (hostile first)
    - Colony details (first N with stats)
    - Technology summary
    - Active policies, edicts, traditions, wars
    """
    compact: dict = {
        "year": state.get("year"),
        "month": state.get("month"),
        "empire": state.get("empire", {}),
        "economy": state.get("economy", {}),
    }

    # Fleets: keep top N by power
    fleets = state.get("fleets", [])
    if isinstance(fleets, list):
        fleets_sorted = sorted(fleets, key=lambda f: f.get("power", 0), reverse=True)
        compact["fleets"] = fleets_sorted[:MAX_FLEETS_IN_PROMPT]
        if len(fleets) > MAX_FLEETS_IN_PROMPT:
            compact["total_fleets"] = len(fleets)
            compact["total_fleet_power"] = sum(f.get("power", 0) for f in fleets)

    # Colonies: count + first N
    colonies = state.get("colonies", [])
    if isinstance(colonies, list):
        compact["colony_count"] = len(colonies)
        compact["colonies"] = colonies[:MAX_COLONIES_IN_PROMPT]

    # Known empires: prioritize hostile, keep top N
    empires = state.get("known_empires", [])
    if isinstance(empires, list):
        # Sort: hostile first, then by name
        hostile = [e for e in empires if e.get("attitude") in ("hostile", "Hostile")]
        others = [e for e in empires if e.get("attitude") not in ("hostile", "Hostile")]
        sorted_empires = hostile + others
        compact["known_empires"] = sorted_empires[:MAX_EMPIRES_IN_PROMPT]
        if len(empires) > MAX_EMPIRES_IN_PROMPT:
            compact["total_known_empires"] = len(empires)

    # Technology: count + current research
    tech = state.get("technology", {})
    if isinstance(tech, dict):
        compact["tech_count"] = tech.get("count", 0)
        in_progress = tech.get("in_progress", {})
        if in_progress:
            compact["researching"] = in_progress

    # Traditions
    traditions = state.get("traditions", [])
    if isinstance(traditions, list) and traditions:
        compact["traditions"] = traditions

    # Ascension perks
    perks = state.get("ascension_perks", [])
    if isinstance(perks, list) and perks:
        compact["ascension_perks"] = perks

    # Active policies (compact: just policy→selected map)
    policies = state.get("policies", [])
    if isinstance(policies, list) and policies:
        compact["policies"] = {
            p["policy"]: p["selected"]
            for p in policies
            if isinstance(p, dict) and "policy" in p
        }

    # Edicts
    edicts = state.get("edicts", [])
    if isinstance(edicts, list) and edicts:
        compact["edicts"] = edicts

    # Wars
    wars = state.get("wars", [])
    if isinstance(wars, list) and wars:
        compact["wars"] = wars

    # Starbases (upgraded only — outposts excluded in save_reader)
    starbases = state.get("starbases", [])
    if isinstance(starbases, list) and starbases:
        compact["starbases"] = starbases

    # Leaders (compact: class + level only)
    leaders = state.get("leaders", [])
    if isinstance(leaders, list) and leaders:
        compact["leaders"] = [
            {"class": ld.get("class", ""), "level": ld.get("level", 0)}
            for ld in leaders
            if isinstance(ld, dict)
        ]

    # Naval capacity
    nav_cap = state.get("naval_capacity", {})
    if isinstance(nav_cap, dict) and nav_cap:
        compact["naval_capacity"] = nav_cap

    return compact


def parse_llm_response(raw: str) -> Directive:
    """Parse the LLM's structured response into a Directive."""
    action = ""
    target = None
    reason = ""

    for line in raw.strip().splitlines():
        line = line.strip()
        upper = line.upper()
        if upper.startswith("ACTION:"):
            action = line.split(":", 1)[1].strip().upper()
        elif upper.startswith("TARGET:"):
            val = line.split(":", 1)[1].strip()
            target = None if val.upper() == "NONE" else val
        elif upper.startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()

    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"Invalid action '{action}'. Must be one of {ALLOWED_ACTIONS}"
        )

    return Directive(action=action, target=target, reason=reason)


def decide(
    ruleset: dict,
    state: dict,
    event: str | None = None,
    *,
    personality: dict | None = None,
    llm_callable=None,
    provider: "LLMProvider | None" = None,
) -> Directive:
    """Run one decision cycle.

    Parameters
    ----------
    ruleset : dict
        Composite ruleset from ``ruleset_generator.generate_ruleset``.
    state : dict
        JSON‑serialisable game state snapshot (fog‑of‑war filtered).
    event : str | None
        Optional triggering event identifier.
    personality : dict | None
        Personality profile from ``personality_shards.build_personality``.
        If *None*, a neutral profile is used.
    llm_callable : callable | None
        Legacy: ``llm_callable(prompt: str) -> str``.
        Prefer *provider* instead.
    provider : LLMProvider | None
        An ``LLMProvider`` instance.  Takes precedence over *llm_callable*.
        If neither is given, a stub response is used.
    """
    if personality is None:
        personality = {
            "war_willingness": 0.5,
            "expansion_drive": 0.5,
            "tech_focus": 0.5,
            "unity_focus": 0.5,
            "diplomatic_openness": 0.5,
            "trade_focus": 0.3,
            "economic_style": "balanced",
            "risk_tolerance": 0.5,
            "ascension_preference": "any",
            "crisis_preparedness": 0.3,
            "fleet_doctrine": "balanced",
            "leader_weights": {},
        }

    prompt = build_prompt(ruleset, personality, state, event)

    if provider is not None:
        # Use the provider interface (preferred path)
        from engine.llm_provider import LLMProviderError

        try:
            response = provider.complete(prompt)
            raw_response = response.text
        except LLMProviderError:
            raw_response = (
                "ACTION: CONSOLIDATE\n"
                "TARGET: NONE\n"
                "REASON: LLM provider error; defaulting to safe posture."
            )
    elif llm_callable is not None:
        raw_response = llm_callable(prompt)
    else:
        raw_response = (
            "ACTION: CONSOLIDATE\n"
            "TARGET: NONE\n"
            "REASON: No LLM connected; defaulting to safe posture "
            "per 4.3 meta (stability is scarce, consolidate first)."
        )

    return parse_llm_response(raw_response)
