"""
Multi-Agent Council — Stellaris 4.3.4 LLM AI Overhaul

Splits the monolithic decision prompt into domain-specific sub-agents
(Domestic + Military) whose recommendations are merged by a government-
weighted arbiter.  The output is a single validated Directive, identical
to what the single-agent path produces.

Agent layout:
  - Domestic Agent  (governor + scientist shards) → economy, tech, planets
  - Military Agent  (admiral + general shards)    → fleets, wars, borders

Arbitration:
  - Imperial / Dictatorial / Hive / Machine → code-only (highest confidence)
  - Democracy / Oligarchy / Corporate       → LLM arbiter call (optional)
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from engine.decision_engine import Directive, parse_llm_response
from engine.llm_provider import LLMProvider, LLMProviderError
from engine.personality_shards import DEFAULT_WEIGHTS, GOVERNMENT_WEIGHTS
from engine.ruleset_generator import (
    ALLOWED_ACTIONS,
    get_espionage_phase_priority,
    get_fleet_template,
    get_phase_priorities,
)
from engine.strategic_knowledge import (
    get_policy_guidance,
    get_starbase_guidance,
    get_tech_priorities,
    get_tradition_guidance,
)

log = logging.getLogger(__name__)


# ======================================================================== #
# Data Structures
# ======================================================================== #

@dataclass
class Recommendation:
    """One sub-agent's recommended action."""

    agent_role: str
    action: str
    target: str | None = None
    confidence: float = 0.5
    reasoning: str = ""


@dataclass
class CouncilResult:
    """Merged output from the multi-agent council."""

    directive: Directive
    recommendations: list[Recommendation] = field(default_factory=list)
    arbitration_method: str = "code"
    total_latency_ms: float = 0.0
    agent_latencies_ms: dict[str, float] = field(default_factory=dict)


# ======================================================================== #
# Agent Role Definitions
# ======================================================================== #

# Which personality shard weights map to each agent
AGENT_SHARD_MAPPING: dict[str, list[str]] = {
    "domestic": ["governor", "scientist"],
    "military": ["admiral", "general"],
}

# Governments that use code-only arbitration (ruler decides)
CODE_ARBITER_GOVERNMENTS: set[str] = {
    "Imperial", "Dictatorial", "Hive Mind", "Machine Intelligence",
}


# ======================================================================== #
# State Filters — Each agent gets only its domain-relevant state
# ======================================================================== #

_EMPIRE_SAFE_KEYS: set[str] = {"ethics", "civics", "origin", "government", "name"}


def _filter_empire(state: dict) -> dict:
    """Return only safe empire fields — no internal IDs or raw data."""
    raw = state.get("empire", {})
    return {k: v for k, v in raw.items() if k in _EMPIRE_SAFE_KEYS}


def _domestic_state(state: dict) -> dict:
    """Extract economy/tech/planet state for the domestic agent."""
    compact: dict = {
        "year": state.get("year"),
        "month": state.get("month"),
        "empire": _filter_empire(state),
        "economy": state.get("economy", {}),
    }

    colonies = state.get("colonies", [])
    if isinstance(colonies, list):
        compact["colony_count"] = len(colonies)
        compact["colonies"] = colonies[:10]

    tech = state.get("technology", {})
    if isinstance(tech, dict):
        compact["tech_count"] = tech.get("count", 0)
        in_progress = tech.get("in_progress", {})
        if in_progress:
            compact["researching"] = in_progress

    traditions = state.get("traditions", [])
    if isinstance(traditions, list) and traditions:
        compact["traditions"] = traditions

    perks = state.get("ascension_perks", [])
    if isinstance(perks, list) and perks:
        compact["ascension_perks"] = perks

    policies = state.get("policies", [])
    if isinstance(policies, list) and policies:
        compact["policies"] = {
            p["policy"]: p["selected"]
            for p in policies
            if isinstance(p, dict) and "policy" in p
        }

    edicts = state.get("edicts", [])
    if isinstance(edicts, list) and edicts:
        compact["edicts"] = edicts

    leaders = state.get("leaders", [])
    if isinstance(leaders, list):
        compact["leaders"] = [
            {"class": ld.get("class", ""), "level": ld.get("level", 0)}
            for ld in leaders
            if isinstance(ld, dict) and ld.get("class") in ("governor", "scientist")
        ]

    # Minimal military awareness (just total power)
    fleets = state.get("fleets", [])
    if isinstance(fleets, list) and fleets:
        compact["total_fleet_power"] = sum(f.get("power", 0) for f in fleets)

    return compact


def _military_state(state: dict) -> dict:
    """Extract military/diplomatic state for the military agent."""
    compact: dict = {
        "year": state.get("year"),
        "month": state.get("month"),
        "empire": _filter_empire(state),
    }

    fleets = state.get("fleets", [])
    if isinstance(fleets, list):
        fleets_sorted = sorted(fleets, key=lambda f: f.get("power", 0), reverse=True)
        compact["fleets"] = fleets_sorted[:5]
        if len(fleets) > 5:
            compact["total_fleets"] = len(fleets)
            compact["total_fleet_power"] = sum(f.get("power", 0) for f in fleets)

    empires = state.get("known_empires", [])
    if isinstance(empires, list):
        hostile = [e for e in empires if e.get("attitude") in ("hostile", "Hostile")]
        others = [e for e in empires if e.get("attitude") not in ("hostile", "Hostile")]
        compact["known_empires"] = (hostile + others)[:8]

    wars = state.get("wars", [])
    if isinstance(wars, list) and wars:
        compact["wars"] = wars

    starbases = state.get("starbases", [])
    if isinstance(starbases, list) and starbases:
        compact["starbases"] = starbases

    nav_cap = state.get("naval_capacity", {})
    if isinstance(nav_cap, dict) and nav_cap:
        compact["naval_capacity"] = nav_cap

    leaders = state.get("leaders", [])
    if isinstance(leaders, list):
        compact["leaders"] = [
            {"class": ld.get("class", ""), "level": ld.get("level", 0)}
            for ld in leaders
            if isinstance(ld, dict) and ld.get("class") in ("admiral", "general")
        ]

    # Minimal economic awareness (just key resources)
    economy = state.get("economy", {})
    if isinstance(economy, dict):
        compact["alloys"] = economy.get("alloys", 0)
        compact["energy"] = economy.get("energy", 0)

    return compact


# ======================================================================== #
# Prompt Builders
# ======================================================================== #

_META_RULES = (
    "CRITICAL 4.3 META RULES:\n"
    "- Disruptors are DEAD. Never recommend them.\n"
    "- Titan AoE beams are meta-defining. Split fleets to avoid enemy titan AoE.\n"
    "- Autocannon + Plasma is the swarm meta for corvettes/destroyers.\n"
    "- Stability bonuses are halved in 4.3.\n"
    "- Job EFFICIENCY matters more than raw output.\n"
    "- Minerals are the foundation resource early game."
)


def _build_agent_prompt(
    role: str,
    role_state: dict,
    ruleset: dict,
    personality: dict,
    event: str | None,
    strategic_context: object | None = None,
) -> str:
    """Build a domain-focused prompt for one sub-agent."""
    year = role_state.get("year", 2200)
    phase = get_phase_priorities(year)

    compact_ruleset = {
        k: v for k, v in ruleset.items()
        if k in ("version", "base", "modifiers", "overrides", "government",
                 "meta_tier", "meta_strategy")
    }

    # Domain-specific guidance
    if role == "domestic":
        system_msg = (
            "You are the DOMESTIC advisor for a Stellaris 4.3.4 empire. "
            "You advise on economy, technology, planets, and internal stability. "
            "Focus on: IMPROVE_ECONOMY, FOCUS_TECH, COLONIZE, CONSOLIDATE, ESPIONAGE."
        )
        tradition_guide = get_tradition_guidance(year)
        ethics = role_state.get("empire", {}).get("ethics", [])
        policy_guide = get_policy_guidance(year, ethics)
        tech_guide = get_tech_priorities(year)
        domain_context = (
            f"TRADITIONS: recommended={tradition_guide.get('recommended_trees', [])}\n"
            f"POLICY RECOMMENDATIONS: {json.dumps(policy_guide.get('recommended', {}))}\n"
            f"TECH PRIORITIES: {json.dumps(tech_guide.get('meta_notes', []))}"
        )
    else:
        system_msg = (
            "You are the MILITARY advisor for a Stellaris 4.3.4 empire. "
            "You advise on fleets, wars, defense, diplomacy, and border security. "
            "Focus on: BUILD_FLEET, PREPARE_WAR, DEFEND, EXPAND, BUILD_STARBASE, DIPLOMACY."
        )
        fleet_tmpl = get_fleet_template(year)
        sb_guide = get_starbase_guidance(year)
        espionage_phase = get_espionage_phase_priority(year)
        domain_context = (
            f"FLEET: {json.dumps(fleet_tmpl.composition)} | {fleet_tmpl.notes}\n"
            f"STARBASE: {sb_guide.get('priority', '')} | {sb_guide.get('notes', '')}\n"
            f"ESPIONAGE: priority={espionage_phase.get('priority', 'low')}"
        )

    sections = [
        system_msg,
        "You must recommend exactly ONE action from the allowed list.",
        "You must include a CONFIDENCE score (0.0 to 1.0) based on how strongly you feel.",
        "You must cite ruleset elements in your reason.",
        "You must NOT reference mechanics that do not exist in Stellaris 4.3.4.",
        "",
        _META_RULES,
        "",
        f"ALLOWED ACTIONS: {', '.join(ALLOWED_ACTIONS)}",
        "",
        "EMPIRE RULESET:",
        json.dumps(compact_ruleset, indent=2),
        "",
        f"GAME PHASE: {phase['phase']} | FOCUS: {phase.get('economy_focus', '')}",
        "",
        domain_context,
    ]

    # Inject strategic planner context if available
    if strategic_context is not None and hasattr(strategic_context, "to_prompt_block"):
        sections.extend(["", strategic_context.to_prompt_block()])

    sections.extend([
        "",
        "CURRENT STATE:",
        json.dumps(role_state, indent=2),
    ])

    if event:
        sections.append(f"\nTRIGGERING EVENT: {event}")

    sections.append(
        "\nRespond in EXACTLY this format:\n"
        "ACTION: <one action from the allowed list>\n"
        "TARGET: <target or NONE>\n"
        "CONFIDENCE: <0.0 to 1.0>\n"
        "REASON: <must cite ruleset elements and meta rules>"
    )
    return "\n".join(sections)


def _parse_recommendation(raw: str, agent_role: str) -> Recommendation:
    """Parse a sub-agent's structured response into a Recommendation."""
    action = ""
    target = None
    confidence = 0.5
    reasoning = ""

    for line in raw.strip().splitlines():
        line = line.strip()
        upper = line.upper()
        if upper.startswith("ACTION:"):
            action = line.split(":", 1)[1].strip().upper()
        elif upper.startswith("TARGET:"):
            val = line.split(":", 1)[1].strip()
            target = None if val.upper() == "NONE" else val
        elif upper.startswith("CONFIDENCE:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                confidence = 0.5
        elif upper.startswith("REASON:"):
            reasoning = line.split(":", 1)[1].strip()

    if action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"Agent '{agent_role}' returned invalid action '{action}'"
        )

    return Recommendation(
        agent_role=agent_role,
        action=action,
        target=target,
        confidence=confidence,
        reasoning=reasoning,
    )


# ======================================================================== #
# Arbiter Logic
# ======================================================================== #

def _compute_agent_weight(
    agent_role: str,
    government: str,
    personality: dict,
) -> float:
    """Compute the aggregate weight for an agent from its constituent shards."""
    weights = GOVERNMENT_WEIGHTS.get(government, DEFAULT_WEIGHTS)
    shard_names = AGENT_SHARD_MAPPING.get(agent_role, [])
    return sum(weights.get(s, 0.0) for s in shard_names)


def _code_arbitrate(
    recommendations: list[Recommendation],
    government: str,
    personality: dict,
) -> Directive:
    """Pick the winning recommendation using government-weighted scoring.

    Each recommendation's confidence is multiplied by the agent's weight
    (sum of its constituent personality shard weights).  Highest score wins.
    """
    if not recommendations:
        return Directive(
            action="CONSOLIDATE",
            reason="No agent recommendations available; defaulting to safe posture.",
        )

    best_score = -1.0
    best_rec = recommendations[0]

    for rec in recommendations:
        weight = _compute_agent_weight(rec.agent_role, government, personality)
        score = rec.confidence * weight
        log.debug(
            "Agent %s: action=%s conf=%.2f weight=%.2f score=%.3f",
            rec.agent_role, rec.action, rec.confidence, weight, score,
        )
        if score > best_score:
            best_score = score
            best_rec = rec

    return Directive(
        action=best_rec.action,
        target=best_rec.target,
        reason=(
            f"[{best_rec.agent_role}] {best_rec.reasoning} "
            f"(confidence={best_rec.confidence:.2f})"
        ),
    )


def _build_arbiter_prompt(
    recommendations: list[Recommendation],
    government: str,
    personality: dict,
    state: dict,
) -> str:
    """Build the LLM arbiter prompt to merge recommendations."""
    rec_lines = []
    for rec in recommendations:
        weight = _compute_agent_weight(rec.agent_role, government, personality)
        rec_lines.append(
            f"- {rec.agent_role.upper()} (weight={weight:.2f}): "
            f"ACTION={rec.action} TARGET={rec.target or 'NONE'} "
            f"CONFIDENCE={rec.confidence:.2f} REASON={rec.reasoning}"
        )

    year = state.get("year", 2200)
    phase = get_phase_priorities(year)

    return "\n".join([
        f"You are the RULER of a {government} Stellaris 4.3.4 empire.",
        "Your advisors have submitted the following recommendations:",
        "",
        *rec_lines,
        "",
        f"GAME PHASE: {phase['phase']}",
        f"GOVERNMENT: {government}",
        json.dumps({k: v for k, v in personality.items()
                     if k in ("war_willingness", "expansion_drive", "tech_focus",
                              "economic_style", "risk_tolerance")}, indent=2),
        "",
        "Choose the BEST action considering all recommendations.",
        "You may pick one advisor's action or propose a different allowed action.",
        "You must NOT use information the empire does not know (fog-of-war).",
        f"ALLOWED ACTIONS: {', '.join(ALLOWED_ACTIONS)}",
        "",
        "Respond in EXACTLY this format:",
        "ACTION: <one action>",
        "TARGET: <target or NONE>",
        "REASON: <explain why this was chosen, cite advisors>",
    ])


# ======================================================================== #
# Council Orchestrator
# ======================================================================== #

class CouncilOrchestrator:
    """Runs the multi-agent council and produces a single Directive."""

    def __init__(
        self,
        provider: LLMProvider,
        government: str,
        personality: dict,
        ruleset: dict,
        parallel: bool = True,
        arbiter_uses_llm: bool = True,
    ) -> None:
        self._provider = provider
        self._government = government
        self._personality = personality
        self._ruleset = ruleset
        self._parallel = parallel
        self._arbiter_uses_llm = arbiter_uses_llm

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def decide(
        self, state: dict, event: str | None = None,
        strategic_context: object | None = None,
    ) -> CouncilResult:
        """Run the full multi-agent decision pipeline."""
        t0 = time.monotonic()

        # Step 1: Build domain-specific states
        dom_state = _domestic_state(state)
        mil_state = _military_state(state)

        # Step 2: Query sub-agents
        if self._parallel:
            recommendations, latencies = self._query_parallel(
                dom_state, mil_state, event, strategic_context,
            )
        else:
            recommendations, latencies = self._query_sequential(
                dom_state, mil_state, event, strategic_context,
            )

        # Step 3: Arbitrate
        use_code = (
            self._government in CODE_ARBITER_GOVERNMENTS
            or not self._arbiter_uses_llm
        )

        if use_code or len(recommendations) <= 1:
            directive = _code_arbitrate(
                recommendations, self._government, self._personality,
            )
            method = "code"
        else:
            directive, arb_latency = self._llm_arbitrate(recommendations, state)
            latencies["arbiter"] = arb_latency
            method = "llm"

        total_ms = (time.monotonic() - t0) * 1000

        log.info(
            "Council decided: action=%s method=%s agents=%d latency=%.0fms",
            directive.action, method, len(recommendations), total_ms,
        )

        return CouncilResult(
            directive=directive,
            recommendations=recommendations,
            arbitration_method=method,
            total_latency_ms=total_ms,
            agent_latencies_ms=latencies,
        )

    def update_context(
        self,
        government: str,
        personality: dict,
        ruleset: dict,
    ) -> None:
        """Refresh cached context after a mid-game empire reform."""
        self._government = government
        self._personality = personality
        self._ruleset = ruleset

    # ------------------------------------------------------------------ #
    # Internal — Sub-agent queries
    # ------------------------------------------------------------------ #

    def _query_one_agent(
        self,
        role: str,
        role_state: dict,
        event: str | None,
        strategic_context: object | None = None,
    ) -> tuple[Recommendation | None, float]:
        """Query a single sub-agent and return its recommendation + latency."""
        prompt = _build_agent_prompt(
            role, role_state, self._ruleset, self._personality, event,
            strategic_context=strategic_context,
        )
        t0 = time.monotonic()
        try:
            response = self._provider.complete(prompt)
        except LLMProviderError as exc:
            log.error("Agent '%s' LLM error: %s", role, exc)
            return None, 0.0

        latency_ms = (time.monotonic() - t0) * 1000
        log.debug(
            "Agent '%s' responded in %.0fms (tokens: %d→%d)",
            role, latency_ms, response.prompt_tokens, response.completion_tokens,
        )

        try:
            rec = _parse_recommendation(response.text, role)
            return rec, latency_ms
        except ValueError as exc:
            log.warning("Agent '%s' parse error: %s", role, exc)
            return None, latency_ms

    def _query_parallel(
        self,
        dom_state: dict,
        mil_state: dict,
        event: str | None,
        strategic_context: object | None = None,
    ) -> tuple[list[Recommendation], dict[str, float]]:
        """Query both sub-agents in parallel using threads."""
        recommendations: list[Recommendation] = []
        latencies: dict[str, float] = {}

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(
                    self._query_one_agent, "domestic", dom_state, event, strategic_context,
                ): "domestic",
                pool.submit(
                    self._query_one_agent, "military", mil_state, event, strategic_context,
                ): "military",
            }
            for future in as_completed(futures):
                role = futures[future]
                rec, lat = future.result()
                latencies[role] = lat
                if rec is not None:
                    recommendations.append(rec)

        return recommendations, latencies

    def _query_sequential(
        self,
        dom_state: dict,
        mil_state: dict,
        event: str | None,
        strategic_context: object | None = None,
    ) -> tuple[list[Recommendation], dict[str, float]]:
        """Query sub-agents one at a time."""
        recommendations: list[Recommendation] = []
        latencies: dict[str, float] = {}

        for role, role_state in [("domestic", dom_state), ("military", mil_state)]:
            rec, lat = self._query_one_agent(role, role_state, event, strategic_context)
            latencies[role] = lat
            if rec is not None:
                recommendations.append(rec)

        return recommendations, latencies

    # ------------------------------------------------------------------ #
    # Internal — Arbiter
    # ------------------------------------------------------------------ #

    def _llm_arbitrate(
        self,
        recommendations: list[Recommendation],
        state: dict,
    ) -> tuple[Directive, float]:
        """Use the LLM to merge recommendations (democratic/oligarchic govs)."""
        prompt = _build_arbiter_prompt(
            recommendations, self._government, self._personality, state,
        )
        t0 = time.monotonic()
        try:
            response = self._provider.complete(prompt)
            latency_ms = (time.monotonic() - t0) * 1000
            directive = parse_llm_response(response.text)
            return directive, latency_ms
        except (LLMProviderError, ValueError) as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            log.warning("LLM arbiter failed (%s), falling back to code", exc)
            directive = _code_arbitrate(
                recommendations, self._government, self._personality,
            )
            return directive, latency_ms
