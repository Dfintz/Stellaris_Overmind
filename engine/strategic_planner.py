"""
Strategic Planner — Stellaris 4.3.4 LLM AI Overhaul

Runs periodically (every N in-game years or on phase transitions) to
produce a high-level strategic assessment.  The output is a structured
``StrategicContext`` that persists between ticks and is injected into
sub-agent prompts to provide long-term direction.

Design:
  - Separated from the per-tick decision loop (runs infrequently)
  - Can use a different (larger) LLM provider via config
  - Falls back to a code-only assessment if no LLM is available
  - Never directly produces a Directive — only advisory context
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field

from engine.llm_provider import LLMProvider, LLMProviderError
from engine.ruleset_generator import (
    ALLOWED_ACTIONS,
    GamePhase,
    phase_from_year,
)

log = logging.getLogger(__name__)


# ======================================================================== #
# Data Structures
# ======================================================================== #

@dataclass
class StrategicContext:
    """Long-term strategic assessment, refreshed every N years."""

    phase: str = "early"
    previous_phase: str = ""
    phase_changed: bool = False

    # Threat assessment
    threat_level: str = "low"          # low | moderate | high | critical
    primary_threat: str = ""           # empire name or "crisis"
    defensive_priority: float = 0.3    # 0–1

    # Economic assessment
    economy_health: str = "stable"     # deficit | fragile | stable | strong | booming
    economy_bottleneck: str = ""       # e.g. "minerals", "alloys", "energy"

    # Strategic priorities (ordered)
    priorities: list[str] = field(default_factory=lambda: [
        "IMPROVE_ECONOMY", "FOCUS_TECH", "EXPAND",
    ])

    # Arc guidance
    arc_summary: str = ""              # one-sentence strategic direction
    recommended_focus: str = ""        # e.g. "tech rush", "war preparation", "federation"

    # Meta
    year_generated: int = 0
    generation_latency_ms: float = 0.0
    source: str = "code"               # "code" | "llm"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_prompt_block(self) -> str:
        """Compact string for injection into sub-agent prompts."""
        lines = [
            f"STRATEGIC PLAN (generated year {self.year_generated}):",
            f"  Phase: {self.phase}"
            + (f" (was {self.previous_phase})" if self.phase_changed else ""),
            f"  Threat: {self.threat_level}"
            + (f" — {self.primary_threat}" if self.primary_threat else ""),
            f"  Economy: {self.economy_health}"
            + (f" (bottleneck: {self.economy_bottleneck})" if self.economy_bottleneck else ""),
            f"  Priorities: {', '.join(self.priorities[:3])}",
            f"  Focus: {self.recommended_focus}" if self.recommended_focus else "",
            f"  Arc: {self.arc_summary}" if self.arc_summary else "",
        ]
        return "\n".join(line for line in lines if line)


# ======================================================================== #
# Code-Only Assessment (no LLM needed)
# ======================================================================== #

def _assess_threats(state: dict) -> tuple[str, str, float]:
    """Evaluate threat level from known empires and wars."""
    wars = state.get("wars", [])
    known = state.get("known_empires", [])
    hostile_count = sum(
        1 for e in known
        if isinstance(e, dict) and e.get("attitude") in ("hostile", "Hostile")
    )

    if wars:
        return "critical", "active war", 0.9
    if hostile_count >= 3:
        return "high", f"{hostile_count} hostile empires", 0.7
    if hostile_count >= 1:
        return "moderate", "hostile neighbour", 0.5
    return "low", "", 0.3


def _assess_economy(state: dict) -> tuple[str, str]:
    """Evaluate economic health from resource stockpiles."""
    economy = state.get("economy", {})
    if not isinstance(economy, dict) or not economy:
        return "stable", ""

    energy = economy.get("energy", 0)
    minerals = economy.get("minerals", 0)
    alloys = economy.get("alloys", 0)
    food = economy.get("food", 0)

    # Check for deficits (negative stockpiles or very low)
    if energy < 0 or minerals < 0 or food < 0:
        bottleneck = "energy" if energy < 0 else ("minerals" if minerals < 0 else "food")
        return "deficit", bottleneck

    if energy < 20 or minerals < 50:
        bottleneck = "energy" if energy < minerals else "minerals"
        return "fragile", bottleneck

    if alloys < 10:
        return "fragile", "alloys"

    year = state.get("year", 2200)
    if year >= 2280:
        if alloys >= 200 and minerals >= 500:
            return "booming", ""
        if alloys >= 100:
            return "strong", ""
    else:
        if minerals >= 300 and alloys >= 50:
            return "strong", ""

    return "stable", ""


def _code_priorities(
    phase: GamePhase,
    threat_level: str,
    economy_health: str,
    personality: dict,
) -> list[str]:
    """Determine priority ordering using code logic."""
    war_will = personality.get("war_willingness", 0.5)
    tech_focus = personality.get("tech_focus", 0.5)

    if threat_level == "critical":
        return ["DEFEND", "BUILD_FLEET", "IMPROVE_ECONOMY"]

    if economy_health in ("deficit", "fragile"):
        return ["IMPROVE_ECONOMY", "CONSOLIDATE", "FOCUS_TECH"]

    if phase == GamePhase.EARLY:
        base = ["IMPROVE_ECONOMY", "EXPAND", "FOCUS_TECH"]
        if war_will > 0.7:
            base = ["IMPROVE_ECONOMY", "BUILD_FLEET", "EXPAND"]
        return base

    if phase == GamePhase.MID:
        if threat_level == "high":
            return ["BUILD_FLEET", "IMPROVE_ECONOMY", "FOCUS_TECH"]
        if tech_focus > 0.6:
            return ["FOCUS_TECH", "IMPROVE_ECONOMY", "BUILD_FLEET"]
        return ["IMPROVE_ECONOMY", "FOCUS_TECH", "BUILD_FLEET"]

    # Late game
    if threat_level in ("high", "moderate"):
        return ["BUILD_FLEET", "FOCUS_TECH", "IMPROVE_ECONOMY"]
    return ["FOCUS_TECH", "IMPROVE_ECONOMY", "BUILD_FLEET"]


def _code_focus(
    phase: GamePhase,
    personality: dict,
    economy_health: str,
    threat_level: str,
) -> str:
    """Determine recommended focus as a short label."""
    if threat_level == "critical":
        return "emergency defense"
    if economy_health in ("deficit", "fragile"):
        return "economic recovery"

    if phase == GamePhase.EARLY:
        if personality.get("tech_focus", 0.5) > 0.6:
            return "tech rush"
        return "expansion and minerals"

    if phase == GamePhase.MID:
        if personality.get("war_willingness", 0.5) > 0.7:
            return "war preparation"
        if personality.get("diplomatic_openness", 0.5) > 0.6:
            return "federation building"
        return "alloy megafactories"

    # Late
    return "repeatables and crisis prep"


def assess_code(
    state: dict,
    personality: dict,
    previous_context: StrategicContext | None = None,
) -> StrategicContext:
    """Generate a strategic context using code-only analysis (no LLM)."""
    year = state.get("year", 2200)
    phase = phase_from_year(year)

    threat_level, primary_threat, def_priority = _assess_threats(state)
    econ_health, econ_bottleneck = _assess_economy(state)
    priorities = _code_priorities(phase, threat_level, econ_health, personality)
    focus = _code_focus(phase, personality, econ_health, threat_level)

    prev_phase = ""
    phase_changed = False
    if previous_context is not None:
        prev_phase = previous_context.phase
        phase_changed = prev_phase != phase.value

    colony_count = len(state.get("colonies", []))
    fleet_power = sum(
        f.get("power", 0) for f in state.get("fleets", []) if isinstance(f, dict)
    )

    arc = (
        f"Year {year}, {phase.value} game. "
        f"{colony_count} colonies, {fleet_power} fleet power. "
        f"Focus: {focus}."
    )

    return StrategicContext(
        phase=phase.value,
        previous_phase=prev_phase,
        phase_changed=phase_changed,
        threat_level=threat_level,
        primary_threat=primary_threat,
        defensive_priority=def_priority,
        economy_health=econ_health,
        economy_bottleneck=econ_bottleneck,
        priorities=priorities,
        arc_summary=arc,
        recommended_focus=focus,
        year_generated=year,
        source="code",
    )


# ======================================================================== #
# LLM-Based Assessment
# ======================================================================== #

_PLANNER_PROMPT_TEMPLATE = """\
You are a long-term strategic planner for a Stellaris 4.3.4 empire.
Analyze the empire's position and produce a strategic assessment.

EMPIRE CONTEXT:
{empire_context}

PERSONALITY:
{personality}

CURRENT STATE SUMMARY:
- Year: {year} ({phase} game)
- Colonies: {colony_count}
- Total fleet power: {fleet_power}
- Economy: {economy}
- Known threats: {threats}
- Wars: {wars}
- Tech count: {tech_count}

PREVIOUS PLAN: {previous_plan}

Respond in EXACTLY this format:
THREAT_LEVEL: <low | moderate | high | critical>
ECONOMY_HEALTH: <deficit | fragile | stable | strong | booming>
BOTTLENECK: <resource name or NONE>
PRIORITY_1: <action from {actions}>
PRIORITY_2: <action from {actions}>
PRIORITY_3: <action from {actions}>
FOCUS: <short label, e.g. "tech rush", "war preparation", "economic recovery">
ARC: <one sentence describing the empire's strategic direction>"""


def _build_planner_prompt(
    state: dict,
    ruleset: dict,
    personality: dict,
    previous_context: StrategicContext | None,
) -> str:
    """Build the strategic planner prompt."""
    year = state.get("year", 2200)
    phase = phase_from_year(year)
    economy = state.get("economy", {})
    colonies = state.get("colonies", [])
    fleets = state.get("fleets", [])
    known = state.get("known_empires", [])
    wars = state.get("wars", [])
    tech = state.get("technology", {})

    fleet_power = sum(f.get("power", 0) for f in fleets if isinstance(f, dict))
    hostile = [e.get("name", "?") for e in known
               if isinstance(e, dict) and e.get("attitude") in ("hostile", "Hostile")]

    compact_ruleset = {
        k: v for k, v in ruleset.items()
        if k in ("version", "base", "modifiers", "overrides", "government",
                 "meta_tier", "meta_strategy")
    }

    prev_plan = "none"
    if previous_context is not None:
        prev_plan = (
            f"phase={previous_context.phase} focus={previous_context.recommended_focus} "
            f"priorities={previous_context.priorities[:3]}"
        )

    return _PLANNER_PROMPT_TEMPLATE.format(
        empire_context=json.dumps(compact_ruleset, indent=2),
        personality=json.dumps(
            {k: v for k, v in personality.items()
             if k in ("war_willingness", "expansion_drive", "tech_focus",
                       "economic_style", "risk_tolerance", "fleet_doctrine")},
            indent=2,
        ),
        year=year,
        phase=phase.value,
        colony_count=len(colonies),
        fleet_power=fleet_power,
        economy=json.dumps(economy),
        threats=", ".join(hostile) if hostile else "none detected",
        wars=f"{len(wars)} active" if wars else "none",
        tech_count=tech.get("count", 0) if isinstance(tech, dict) else 0,
        previous_plan=prev_plan,
        actions=", ".join(ALLOWED_ACTIONS),
    )


def _parse_planner_response(
    raw: str,
    state: dict,
    previous_context: StrategicContext | None,
) -> StrategicContext:
    """Parse the LLM planner output into a StrategicContext."""
    year = state.get("year", 2200)
    phase = phase_from_year(year)

    ctx = StrategicContext(
        phase=phase.value,
        year_generated=year,
        source="llm",
    )

    if previous_context is not None:
        ctx.previous_phase = previous_context.phase
        ctx.phase_changed = previous_context.phase != phase.value

    for line in raw.strip().splitlines():
        line = line.strip()
        upper = line.upper()

        if upper.startswith("THREAT_LEVEL:"):
            val = line.split(":", 1)[1].strip().lower()
            if val in ("low", "moderate", "high", "critical"):
                ctx.threat_level = val

        elif upper.startswith("ECONOMY_HEALTH:"):
            val = line.split(":", 1)[1].strip().lower()
            if val in ("deficit", "fragile", "stable", "strong", "booming"):
                ctx.economy_health = val

        elif upper.startswith("BOTTLENECK:"):
            val = line.split(":", 1)[1].strip()
            ctx.economy_bottleneck = "" if val.upper() == "NONE" else val

        elif upper.startswith("PRIORITY_1:"):
            action = line.split(":", 1)[1].strip().upper()
            if action in ALLOWED_ACTIONS:
                ctx.priorities = [action]

        elif upper.startswith("PRIORITY_2:"):
            action = line.split(":", 1)[1].strip().upper()
            if action in ALLOWED_ACTIONS:
                ctx.priorities.append(action)

        elif upper.startswith("PRIORITY_3:"):
            action = line.split(":", 1)[1].strip().upper()
            if action in ALLOWED_ACTIONS:
                ctx.priorities.append(action)

        elif upper.startswith("FOCUS:"):
            ctx.recommended_focus = line.split(":", 1)[1].strip()

        elif upper.startswith("ARC:"):
            ctx.arc_summary = line.split(":", 1)[1].strip()

    # Compute defensive priority from threat level
    threat_to_def = {"low": 0.3, "moderate": 0.5, "high": 0.7, "critical": 0.9}
    ctx.defensive_priority = threat_to_def.get(ctx.threat_level, 0.3)

    # Infer primary threat
    known = state.get("known_empires", [])
    hostile = [e.get("name", "?") for e in known
               if isinstance(e, dict) and e.get("attitude") in ("hostile", "Hostile")]
    if state.get("wars"):
        ctx.primary_threat = "active war"
    elif hostile:
        ctx.primary_threat = hostile[0]

    return ctx


# ======================================================================== #
# Strategic Planner
# ======================================================================== #

class StrategicPlanner:
    """Generates and caches long-term strategic assessments."""

    def __init__(
        self,
        provider: LLMProvider | None,
        ruleset: dict,
        personality: dict,
        interval_years: int = 5,
    ) -> None:
        self._provider = provider
        self._ruleset = ruleset
        self._personality = personality
        self._interval_years = interval_years
        self._context: StrategicContext | None = None

    @property
    def context(self) -> StrategicContext | None:
        """The current strategic context, or *None* if never generated."""
        return self._context

    def should_replan(self, year: int) -> bool:
        """Return *True* if a new plan is needed."""
        if self._context is None:
            return True

        # Re-plan on phase transitions
        current_phase = phase_from_year(year).value
        if current_phase != self._context.phase:
            return True

        # Re-plan every N years
        years_since = year - self._context.year_generated
        return years_since >= self._interval_years

    def plan(self, state: dict) -> StrategicContext:
        """Generate a new strategic context.

        Tries the LLM first, falls back to code-only on failure.
        """
        t0 = time.monotonic()

        if self._provider is not None:
            try:
                ctx = self._plan_llm(state)
                ctx.generation_latency_ms = (time.monotonic() - t0) * 1000
                self._context = ctx
                log.info(
                    "Strategic plan (LLM): phase=%s focus=%s threats=%s latency=%.0fms",
                    ctx.phase, ctx.recommended_focus, ctx.threat_level,
                    ctx.generation_latency_ms,
                )
                return ctx
            except (LLMProviderError, ValueError) as exc:
                log.warning("LLM planner failed (%s), falling back to code", exc)

        ctx = assess_code(state, self._personality, self._context)
        ctx.generation_latency_ms = (time.monotonic() - t0) * 1000
        self._context = ctx
        log.info(
            "Strategic plan (code): phase=%s focus=%s threats=%s",
            ctx.phase, ctx.recommended_focus, ctx.threat_level,
        )
        return ctx

    def update_context(self, ruleset: dict, personality: dict) -> None:
        """Refresh cached ruleset/personality after mid-game reform."""
        self._ruleset = ruleset
        self._personality = personality

    def _plan_llm(self, state: dict) -> StrategicContext:
        """Generate context using the LLM."""
        prompt = _build_planner_prompt(
            state, self._ruleset, self._personality, self._context,
        )
        response = self._provider.complete(prompt)
        return _parse_planner_response(response.text, state, self._context)
