"""Tests for strategic_planner — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.llm_provider import LLMProvider, LLMProviderError, LLMResponse, StubProvider
from engine.personality_shards import build_personality
from engine.ruleset_generator import ALLOWED_ACTIONS, generate_ruleset
from engine.strategic_planner import (
    StrategicContext,
    StrategicPlanner,
    _assess_economy,
    _assess_threats,
    _build_planner_prompt,
    _code_focus,
    _code_priorities,
    _parse_planner_response,
    assess_code,
)
from engine.ruleset_generator import GamePhase


# ======================================================================== #
# Fixtures
# ======================================================================== #

@pytest.fixture
def personality() -> dict:
    return build_personality(
        ethics=["Militarist", "Materialist"],
        civics=["Technocracy"],
        traits=["Intelligent"],
        origin="Prosperous Unification",
        government="Oligarchy",
    )


@pytest.fixture
def ruleset() -> dict:
    return generate_ruleset(
        ethics=["Militarist", "Materialist"],
        civics=["Technocracy"],
        traits=["Intelligent"],
        origin="Prosperous Unification",
        government="Oligarchy",
    )


class PlannerStubProvider(LLMProvider):
    """Returns a well-formed planner response."""

    def complete(self, prompt: str) -> LLMResponse:
        return LLMResponse(
            text=(
                "THREAT_LEVEL: moderate\n"
                "ECONOMY_HEALTH: strong\n"
                "BOTTLENECK: NONE\n"
                "PRIORITY_1: FOCUS_TECH\n"
                "PRIORITY_2: BUILD_FLEET\n"
                "PRIORITY_3: IMPROVE_ECONOMY\n"
                "FOCUS: tech rush with fleet backup\n"
                "ARC: Materialist empire should rush tech while building a deterrent fleet."
            ),
            model="planner-stub",
        )

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "planner-stub"


class FailingPlannerProvider(LLMProvider):
    """Always fails."""

    def complete(self, prompt: str) -> LLMResponse:
        raise LLMProviderError("Planner test failure")

    def is_available(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return "failing-planner"


# ======================================================================== #
# Threat Assessment
# ======================================================================== #


class TestAssessThreats:

    def test_no_threats(self) -> None:
        state = {"known_empires": [{"name": "Friend", "attitude": "Cordial"}]}
        level, threat, priority = _assess_threats(state)
        assert level == "low"
        assert priority < 0.5

    def test_one_hostile(self) -> None:
        state = {"known_empires": [{"name": "Enemy", "attitude": "Hostile"}]}
        level, threat, priority = _assess_threats(state)
        assert level == "moderate"
        assert "hostile" in threat.lower()

    def test_many_hostile(self) -> None:
        state = {
            "known_empires": [
                {"name": f"Enemy{i}", "attitude": "Hostile"} for i in range(4)
            ],
        }
        level, _, _ = _assess_threats(state)
        assert level == "high"

    def test_active_war(self) -> None:
        state = {"wars": [{"id": 1}], "known_empires": []}
        level, threat, priority = _assess_threats(state)
        assert level == "critical"
        assert priority >= 0.9


# ======================================================================== #
# Economy Assessment
# ======================================================================== #


class TestAssessEconomy:

    def test_deficit(self) -> None:
        state = {"economy": {"energy": -5, "minerals": 100, "alloys": 50, "food": 50}}
        health, bottleneck = _assess_economy(state)
        assert health == "deficit"
        assert bottleneck == "energy"

    def test_fragile(self) -> None:
        state = {"economy": {"energy": 10, "minerals": 30, "alloys": 50, "food": 50}}
        health, bottleneck = _assess_economy(state)
        assert health == "fragile"

    def test_stable(self) -> None:
        state = {"economy": {"energy": 100, "minerals": 200, "alloys": 30, "food": 80}}
        health, _ = _assess_economy(state)
        assert health == "stable"

    def test_strong_early(self) -> None:
        state = {
            "year": 2220,
            "economy": {"energy": 200, "minerals": 400, "alloys": 60, "food": 100},
        }
        health, _ = _assess_economy(state)
        assert health == "strong"

    def test_booming_late(self) -> None:
        state = {
            "year": 2300,
            "economy": {"energy": 500, "minerals": 800, "alloys": 250, "food": 200},
        }
        health, _ = _assess_economy(state)
        assert health == "booming"

    def test_missing_economy(self) -> None:
        state = {}
        health, _ = _assess_economy(state)
        assert health == "stable"  # no economy dict → early return


# ======================================================================== #
# Code Priorities
# ======================================================================== #


class TestCodePriorities:

    def test_critical_threat_defends(self) -> None:
        p = _code_priorities(GamePhase.MID, "critical", "stable", {})
        assert p[0] == "DEFEND"

    def test_deficit_economy_first(self) -> None:
        p = _code_priorities(GamePhase.EARLY, "low", "deficit", {})
        assert p[0] == "IMPROVE_ECONOMY"

    def test_early_game_default(self) -> None:
        p = _code_priorities(GamePhase.EARLY, "low", "stable", {"war_willingness": 0.5})
        assert "IMPROVE_ECONOMY" in p
        assert "EXPAND" in p

    def test_aggressive_early(self) -> None:
        p = _code_priorities(GamePhase.EARLY, "low", "stable", {"war_willingness": 0.8})
        assert "BUILD_FLEET" in p

    def test_late_game_tech_focus(self) -> None:
        p = _code_priorities(GamePhase.LATE, "low", "stable", {})
        assert p[0] == "FOCUS_TECH"


# ======================================================================== #
# Code Focus
# ======================================================================== #


class TestCodeFocus:

    def test_emergency_defense(self) -> None:
        f = _code_focus(GamePhase.MID, {}, "stable", "critical")
        assert f == "emergency defense"

    def test_economic_recovery(self) -> None:
        f = _code_focus(GamePhase.EARLY, {}, "deficit", "low")
        assert f == "economic recovery"

    def test_early_tech_rush(self) -> None:
        f = _code_focus(GamePhase.EARLY, {"tech_focus": 0.8}, "stable", "low")
        assert f == "tech rush"

    def test_late_crisis_prep(self) -> None:
        f = _code_focus(GamePhase.LATE, {}, "stable", "low")
        assert "crisis" in f


# ======================================================================== #
# Code Assessment (full pipeline)
# ======================================================================== #


class TestAssessCode:

    def test_produces_valid_context(self, early_game_state: dict, personality: dict) -> None:
        ctx = assess_code(early_game_state, personality)
        assert isinstance(ctx, StrategicContext)
        assert ctx.phase == "early"
        assert ctx.source == "code"
        assert ctx.year_generated == 2210
        assert all(p in ALLOWED_ACTIONS for p in ctx.priorities)

    def test_phase_transition_detected(self, personality: dict) -> None:
        prev = StrategicContext(phase="early", year_generated=2235)
        state = {"year": 2250, "economy": {"energy": 200, "minerals": 300, "alloys": 50, "food": 100}}
        ctx = assess_code(state, personality, previous_context=prev)
        assert ctx.phase == "mid"
        assert ctx.phase_changed is True
        assert ctx.previous_phase == "early"

    def test_no_phase_change(self, personality: dict) -> None:
        prev = StrategicContext(phase="early", year_generated=2205)
        state = {"year": 2210, "economy": {"energy": 100, "minerals": 200, "alloys": 30, "food": 80}}
        ctx = assess_code(state, personality, previous_context=prev)
        assert ctx.phase_changed is False

    def test_war_state_critical(self, personality: dict) -> None:
        state = {
            "year": 2250,
            "wars": [{"id": 1}],
            "known_empires": [],
            "economy": {"energy": 100, "minerals": 200, "alloys": 50, "food": 80},
        }
        ctx = assess_code(state, personality)
        assert ctx.threat_level == "critical"
        assert ctx.priorities[0] == "DEFEND"


# ======================================================================== #
# Strategic Context
# ======================================================================== #


class TestStrategicContext:

    def test_to_prompt_block(self) -> None:
        ctx = StrategicContext(
            phase="mid",
            threat_level="moderate",
            primary_threat="Tzynn Empire",
            economy_health="strong",
            priorities=["FOCUS_TECH", "BUILD_FLEET"],
            recommended_focus="tech rush",
            arc_summary="Rush tech while building fleet.",
            year_generated=2260,
        )
        block = ctx.to_prompt_block()
        assert "STRATEGIC PLAN" in block
        assert "mid" in block
        assert "moderate" in block
        assert "Tzynn Empire" in block
        assert "strong" in block
        assert "FOCUS_TECH" in block
        assert "tech rush" in block

    def test_to_dict_roundtrip(self) -> None:
        ctx = StrategicContext(phase="late", threat_level="high")
        d = ctx.to_dict()
        assert d["phase"] == "late"
        assert d["threat_level"] == "high"


# ======================================================================== #
# LLM Planner Response Parsing
# ======================================================================== #


class TestParsePlannerResponse:

    def test_valid_response(self) -> None:
        raw = (
            "THREAT_LEVEL: high\n"
            "ECONOMY_HEALTH: stable\n"
            "BOTTLENECK: alloys\n"
            "PRIORITY_1: BUILD_FLEET\n"
            "PRIORITY_2: IMPROVE_ECONOMY\n"
            "PRIORITY_3: FOCUS_TECH\n"
            "FOCUS: war preparation\n"
            "ARC: Build fleet to counter hostile neighbours."
        )
        state = {"year": 2260, "known_empires": [{"name": "Enemy", "attitude": "Hostile"}]}
        ctx = _parse_planner_response(raw, state, None)
        assert ctx.threat_level == "high"
        assert ctx.economy_health == "stable"
        assert ctx.economy_bottleneck == "alloys"
        assert ctx.priorities == ["BUILD_FLEET", "IMPROVE_ECONOMY", "FOCUS_TECH"]
        assert ctx.recommended_focus == "war preparation"
        assert "fleet" in ctx.arc_summary.lower()
        assert ctx.source == "llm"
        assert ctx.primary_threat == "Enemy"

    def test_phase_change_detected(self) -> None:
        raw = "THREAT_LEVEL: low\nECONOMY_HEALTH: strong\nBOTTLENECK: NONE\nPRIORITY_1: FOCUS_TECH\nPRIORITY_2: IMPROVE_ECONOMY\nPRIORITY_3: EXPAND\nFOCUS: tech\nARC: Tech focus."
        prev = StrategicContext(phase="early")
        state = {"year": 2260}
        ctx = _parse_planner_response(raw, state, prev)
        assert ctx.phase == "mid"
        assert ctx.phase_changed is True

    def test_invalid_values_ignored(self) -> None:
        raw = (
            "THREAT_LEVEL: apocalyptic\n"  # invalid
            "ECONOMY_HEALTH: perfect\n"     # invalid
            "PRIORITY_1: NUKE_PLANET\n"     # invalid action
        )
        state = {"year": 2210}
        ctx = _parse_planner_response(raw, state, None)
        # Should keep defaults
        assert ctx.threat_level == "low"
        assert ctx.economy_health == "stable"

    def test_war_sets_primary_threat(self) -> None:
        raw = "THREAT_LEVEL: critical\nECONOMY_HEALTH: stable\nBOTTLENECK: NONE\nPRIORITY_1: DEFEND\nPRIORITY_2: BUILD_FLEET\nPRIORITY_3: IMPROVE_ECONOMY\nFOCUS: defense\nARC: Survive."
        state = {"year": 2250, "wars": [{"id": 1}], "known_empires": []}
        ctx = _parse_planner_response(raw, state, None)
        assert ctx.primary_threat == "active war"


# ======================================================================== #
# Planner Prompt
# ======================================================================== #


class TestPlannerPrompt:

    def test_contains_key_elements(self, ruleset: dict, personality: dict) -> None:
        state = {
            "year": 2260,
            "economy": {"energy": 200, "minerals": 300, "alloys": 80, "food": 100},
            "colonies": ["Earth", "Mars"],
            "fleets": [{"power": 5000}],
            "known_empires": [{"name": "Enemy", "attitude": "Hostile"}],
            "wars": [],
            "technology": {"count": 25},
        }
        prompt = _build_planner_prompt(state, ruleset, personality, None)
        assert "strategic planner" in prompt.lower()
        assert "4.3.4" in prompt
        assert "2260" in prompt
        assert "Enemy" in prompt
        assert "ALLOWED" not in prompt or "PRIORITY" in prompt  # format block

    def test_includes_previous_plan(self, ruleset: dict, personality: dict) -> None:
        prev = StrategicContext(
            phase="early",
            recommended_focus="expansion",
            priorities=["EXPAND", "IMPROVE_ECONOMY"],
        )
        state = {"year": 2250, "economy": {}, "colonies": [], "fleets": [],
                 "known_empires": [], "wars": [], "technology": {}}
        prompt = _build_planner_prompt(state, ruleset, personality, prev)
        assert "expansion" in prompt
        assert "EXPAND" in prompt


# ======================================================================== #
# Strategic Planner Class
# ======================================================================== #


class TestStrategicPlanner:

    def test_should_replan_initially(self, ruleset: dict, personality: dict) -> None:
        planner = StrategicPlanner(None, ruleset, personality)
        assert planner.should_replan(2200) is True

    def test_should_replan_on_phase_change(self, ruleset: dict, personality: dict) -> None:
        planner = StrategicPlanner(None, ruleset, personality)
        state = {"year": 2210, "economy": {"energy": 100, "minerals": 200, "alloys": 30, "food": 80}}
        planner.plan(state)
        # Same phase, within interval → no replan
        assert planner.should_replan(2212) is False
        # Phase transition → replan
        assert planner.should_replan(2250) is True

    def test_should_replan_on_interval(self, ruleset: dict, personality: dict) -> None:
        planner = StrategicPlanner(None, ruleset, personality, interval_years=5)
        state = {"year": 2210, "economy": {"energy": 100, "minerals": 200, "alloys": 30, "food": 80}}
        planner.plan(state)
        assert planner.should_replan(2214) is False
        assert planner.should_replan(2215) is True

    def test_code_fallback_no_provider(self, ruleset: dict, personality: dict) -> None:
        planner = StrategicPlanner(None, ruleset, personality)
        state = {"year": 2210, "economy": {"energy": 100, "minerals": 200, "alloys": 30, "food": 80}}
        ctx = planner.plan(state)
        assert ctx.source == "code"
        assert ctx.phase == "early"

    def test_llm_planner(
        self, ruleset: dict, personality: dict, early_game_state: dict,
    ) -> None:
        planner = StrategicPlanner(PlannerStubProvider(), ruleset, personality)
        ctx = planner.plan(early_game_state)
        assert ctx.source == "llm"
        assert ctx.threat_level == "moderate"
        assert "FOCUS_TECH" in ctx.priorities

    def test_llm_failure_falls_back_to_code(
        self, ruleset: dict, personality: dict, early_game_state: dict,
    ) -> None:
        planner = StrategicPlanner(FailingPlannerProvider(), ruleset, personality)
        ctx = planner.plan(early_game_state)
        assert ctx.source == "code"

    def test_context_persists(self, ruleset: dict, personality: dict) -> None:
        planner = StrategicPlanner(None, ruleset, personality)
        state = {"year": 2210, "economy": {"energy": 100, "minerals": 200, "alloys": 30, "food": 80}}
        planner.plan(state)
        assert planner.context is not None
        assert planner.context.year_generated == 2210

    def test_update_context(self, ruleset: dict, personality: dict) -> None:
        planner = StrategicPlanner(None, ruleset, personality)
        new_personality = {**personality, "war_willingness": 1.0}
        planner.update_context(ruleset, new_personality)
        assert planner._personality["war_willingness"] == 1.0

    def test_latency_recorded(
        self, ruleset: dict, personality: dict, early_game_state: dict,
    ) -> None:
        planner = StrategicPlanner(None, ruleset, personality)
        ctx = planner.plan(early_game_state)
        assert ctx.generation_latency_ms >= 0


# ======================================================================== #
# Integration: Planner + Multi-Agent
# ======================================================================== #


class TestPlannerMultiAgentIntegration:

    def test_strategic_context_in_agent_prompt(
        self, ruleset: dict, personality: dict,
    ) -> None:
        """Strategic context block appears in sub-agent prompts."""
        from engine.multi_agent import _build_agent_prompt

        ctx = StrategicContext(
            phase="mid",
            threat_level="high",
            recommended_focus="war preparation",
            priorities=["BUILD_FLEET", "IMPROVE_ECONOMY"],
            year_generated=2260,
        )
        state = {"year": 2260, "economy": {"energy": 200, "minerals": 300}}
        prompt = _build_agent_prompt(
            "domestic", state, ruleset, personality, None,
            strategic_context=ctx,
        )
        assert "STRATEGIC PLAN" in prompt
        assert "war preparation" in prompt

    def test_no_strategic_context_still_works(
        self, ruleset: dict, personality: dict,
    ) -> None:
        """Sub-agent prompt works without strategic context."""
        from engine.multi_agent import _build_agent_prompt

        state = {"year": 2210}
        prompt = _build_agent_prompt(
            "military", state, ruleset, personality, None,
            strategic_context=None,
        )
        assert "STRATEGIC PLAN" not in prompt
        assert "MILITARY advisor" in prompt

    def test_council_with_strategic_context(
        self, ruleset: dict, personality: dict, early_game_state: dict,
    ) -> None:
        """Council.decide() accepts and uses strategic_context."""
        from engine.multi_agent import CouncilOrchestrator

        ctx = StrategicContext(
            phase="early", recommended_focus="expansion", priorities=["EXPAND"],
        )
        council = CouncilOrchestrator(
            provider=StubProvider(),
            government="Imperial",
            personality=personality,
            ruleset=ruleset,
            parallel=False,
        )
        result = council.decide(early_game_state, strategic_context=ctx)
        assert result.directive.action in ALLOWED_ACTIONS
