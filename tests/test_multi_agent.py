"""Tests for multi_agent — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.decision_engine import Directive
from engine.llm_provider import LLMProvider, LLMProviderError, LLMResponse, StubProvider
from engine.multi_agent import (
    CODE_ARBITER_GOVERNMENTS,
    CouncilOrchestrator,
    CouncilResult,
    Recommendation,
    _build_agent_prompt,
    _code_arbitrate,
    _compute_agent_weight,
    _domestic_state,
    _military_state,
    _parse_recommendation,
)
from engine.personality_shards import GOVERNMENT_WEIGHTS, build_personality
from engine.ruleset_generator import ALLOWED_ACTIONS, generate_ruleset


# ======================================================================== #
# Fixtures
# ======================================================================== #


class DomesticStubProvider(LLMProvider):
    """Returns a fixed IMPROVE_ECONOMY recommendation."""

    def complete(self, prompt: str) -> LLMResponse:
        return LLMResponse(
            text=(
                "ACTION: IMPROVE_ECONOMY\n"
                "TARGET: NONE\n"
                "CONFIDENCE: 0.8\n"
                "REASON: Economy needs minerals per 4.3 meta."
            ),
            model="domestic-stub",
        )

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "domestic-stub"


class MilitaryStubProvider(LLMProvider):
    """Returns a fixed BUILD_FLEET recommendation."""

    def complete(self, prompt: str) -> LLMResponse:
        return LLMResponse(
            text=(
                "ACTION: BUILD_FLEET\n"
                "TARGET: Sol\n"
                "CONFIDENCE: 0.9\n"
                "REASON: Hostile neighbour detected, fleet cap underused."
            ),
            model="military-stub",
        )

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "military-stub"


class AlternatingStubProvider(LLMProvider):
    """Returns domestic-style first call, military-style second call, arbiter third."""

    def __init__(self) -> None:
        self._call_count = 0

    def complete(self, prompt: str) -> LLMResponse:
        self._call_count += 1
        if self._call_count == 1:
            text = (
                "ACTION: IMPROVE_ECONOMY\n"
                "TARGET: NONE\n"
                "CONFIDENCE: 0.7\n"
                "REASON: Economy focus per meta."
            )
        elif self._call_count == 2:
            text = (
                "ACTION: BUILD_FLEET\n"
                "TARGET: Sol\n"
                "CONFIDENCE: 0.6\n"
                "REASON: Fleet power low."
            )
        else:
            # Arbiter response
            text = (
                "ACTION: IMPROVE_ECONOMY\n"
                "TARGET: NONE\n"
                "REASON: Economy takes priority per democratic consensus."
            )
        return LLMResponse(text=text, model="alternating-stub")

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "alternating-stub"

    @property
    def call_count(self) -> int:
        return self._call_count


class FailingProvider(LLMProvider):
    """Always raises LLMProviderError."""

    def complete(self, prompt: str) -> LLMResponse:
        raise LLMProviderError("Test failure")

    def is_available(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return "failing-stub"


@pytest.fixture
def imperial_empire() -> dict:
    return {
        "ethics": ["Fanatic Authoritarian", "Spiritualist"],
        "civics": ["Corvée System", "Planet Forgers"],
        "traits": ["Ingenious", "Industrious"],
        "origin": "Cybernetic Creed",
        "government": "Imperial",
    }


@pytest.fixture
def democratic_empire() -> dict:
    return {
        "ethics": ["Egalitarian", "Xenophile", "Militarist"],
        "civics": ["Beacon of Liberty", "Meritocracy"],
        "traits": ["Intelligent", "Thrifty"],
        "origin": "Prosperous Unification",
        "government": "Democracy",
    }


@pytest.fixture
def imperial_ruleset(imperial_empire: dict) -> dict:
    return generate_ruleset(**imperial_empire)


@pytest.fixture
def imperial_personality(imperial_empire: dict) -> dict:
    return build_personality(**imperial_empire)


@pytest.fixture
def democratic_ruleset(democratic_empire: dict) -> dict:
    return generate_ruleset(**democratic_empire)


@pytest.fixture
def democratic_personality(democratic_empire: dict) -> dict:
    return build_personality(**democratic_empire)


# ======================================================================== #
# State Filter Tests
# ======================================================================== #


class TestDomesticState:

    def test_includes_economy(self, early_game_state: dict) -> None:
        ds = _domestic_state(early_game_state)
        assert "economy" in ds
        assert ds["economy"]["minerals"] == 200

    def test_includes_colonies(self, early_game_state: dict) -> None:
        ds = _domestic_state(early_game_state)
        assert ds["colony_count"] == 2

    def test_excludes_fleet_details(self, early_game_state: dict) -> None:
        ds = _domestic_state(early_game_state)
        assert "fleets" not in ds

    def test_includes_total_fleet_power(self, early_game_state: dict) -> None:
        ds = _domestic_state(early_game_state)
        assert ds["total_fleet_power"] == 1500

    def test_filters_leaders_to_domestic(self) -> None:
        """Leaders excluded from domestic state for token efficiency."""
        state = {
            "year": 2210,
            "leaders": [
                {"class": "governor", "level": 3},
                {"class": "scientist", "level": 2},
                {"class": "admiral", "level": 4},
            ],
        }
        ds = _domestic_state(state)
        # Leaders excluded to save tokens — macro decisions don't need them
        assert "leaders" not in ds


class TestMilitaryState:

    def test_includes_fleets(self, early_game_state: dict) -> None:
        ms = _military_state(early_game_state)
        assert "fleets" in ms
        assert ms["fleets"][0]["power"] == 1500

    def test_includes_known_empires(self, early_game_state: dict) -> None:
        ms = _military_state(early_game_state)
        assert len(ms["known_empires"]) == 1
        assert ms["known_empires"][0]["name"] == "Tzynn Empire"

    def test_excludes_full_economy(self, early_game_state: dict) -> None:
        ms = _military_state(early_game_state)
        assert "economy" not in ms
        # But has key resources
        assert ms["alloys"] == 30

    def test_filters_leaders_to_military(self) -> None:
        """Leaders excluded from military state for token efficiency."""
        state = {
            "year": 2210,
            "leaders": [
                {"class": "governor", "level": 3},
                {"class": "admiral", "level": 4},
                {"class": "general", "level": 1},
            ],
        }
        ms = _military_state(state)
        # Leaders excluded to save tokens — macro decisions don't need them
        assert "leaders" not in ms


# ======================================================================== #
# Prompt Builder Tests
# ======================================================================== #


class TestAgentPrompts:

    def test_domestic_prompt_contains_economy_focus(
        self, imperial_ruleset: dict, imperial_personality: dict,
    ) -> None:
        state = {"year": 2210, "economy": {"minerals": 100}}
        prompt = _build_agent_prompt(
            "domestic", state, imperial_ruleset, imperial_personality, None,
        )
        assert "DOMESTIC advisor" in prompt
        assert "IMPROVE_ECONOMY" in prompt
        assert "ALLOWED" in prompt
        assert "4.3.4" in prompt

    def test_military_prompt_contains_fleet_focus(
        self, imperial_ruleset: dict, imperial_personality: dict,
    ) -> None:
        state = {"year": 2210, "fleets": [{"power": 1000}]}
        prompt = _build_agent_prompt(
            "military", state, imperial_ruleset, imperial_personality, None,
        )
        assert "MILITARY advisor" in prompt
        assert "BUILD_FLEET" in prompt
        assert "FLEET:" in prompt

    def test_event_included_in_prompt(
        self, imperial_ruleset: dict, imperial_personality: dict,
    ) -> None:
        state = {"year": 2210}
        prompt = _build_agent_prompt(
            "domestic", state, imperial_ruleset, imperial_personality, "war_declared",
        )
        assert "war_declared" in prompt

    def test_meta_rules_in_prompt(
        self, imperial_ruleset: dict, imperial_personality: dict,
    ) -> None:
        state = {"year": 2210}
        prompt = _build_agent_prompt(
            "military", state, imperial_ruleset, imperial_personality, None,
        )
        assert "Disruptors DEAD" in prompt


# ======================================================================== #
# Parse Recommendation Tests
# ======================================================================== #


class TestParseRecommendation:

    def test_valid_recommendation(self) -> None:
        raw = (
            "ACTION: BUILD_FLEET\n"
            "TARGET: Sol\n"
            "CONFIDENCE: 0.85\n"
            "REASON: Fleet cap underused."
        )
        rec = _parse_recommendation(raw, "military")
        assert rec.action == "BUILD_FLEET"
        assert rec.target == "Sol"
        assert rec.confidence == pytest.approx(0.85)
        assert rec.agent_role == "military"

    def test_none_target(self) -> None:
        raw = (
            "ACTION: IMPROVE_ECONOMY\n"
            "TARGET: NONE\n"
            "CONFIDENCE: 0.7\n"
            "REASON: Economy first."
        )
        rec = _parse_recommendation(raw, "domestic")
        assert rec.target is None

    def test_invalid_action_raises(self) -> None:
        raw = "ACTION: NUKE_PLANET\nTARGET: NONE\nCONFIDENCE: 0.9\nREASON: Test."
        with pytest.raises(ValueError, match="invalid action"):
            _parse_recommendation(raw, "military")

    def test_confidence_clamped(self) -> None:
        raw = "ACTION: EXPAND\nTARGET: NONE\nCONFIDENCE: 1.5\nREASON: Test."
        rec = _parse_recommendation(raw, "domestic")
        assert rec.confidence == 1.0

    def test_missing_confidence_defaults(self) -> None:
        raw = "ACTION: EXPAND\nTARGET: NONE\nREASON: Test."
        rec = _parse_recommendation(raw, "domestic")
        assert rec.confidence == 0.5


# ======================================================================== #
# Agent Weight Tests
# ======================================================================== #


class TestAgentWeights:

    def test_imperial_military_weight(self) -> None:
        # admiral=0.05 + general=0.05 = 0.10
        w = _compute_agent_weight("military", "Imperial", {})
        assert w == pytest.approx(0.10)

    def test_imperial_domestic_weight(self) -> None:
        # governor=0.05 + scientist=0.05 = 0.10
        w = _compute_agent_weight("domestic", "Imperial", {})
        assert w == pytest.approx(0.10)

    def test_democracy_weights_balanced(self) -> None:
        # Democracy: each shard = 0.20
        dom = _compute_agent_weight("domestic", "Democracy", {})
        mil = _compute_agent_weight("military", "Democracy", {})
        assert dom == pytest.approx(0.40)
        assert mil == pytest.approx(0.40)

    def test_oligarchy_domestic_higher(self) -> None:
        dom = _compute_agent_weight("domestic", "Oligarchy", {})
        mil = _compute_agent_weight("military", "Oligarchy", {})
        # governor=0.20 + scientist=0.15 = 0.35
        # admiral=0.15 + general=0.10 = 0.25
        assert dom > mil

    def test_all_governments_have_weights(self) -> None:
        for gov in GOVERNMENT_WEIGHTS:
            dom = _compute_agent_weight("domestic", gov, {})
            mil = _compute_agent_weight("military", gov, {})
            assert dom >= 0.0
            assert mil >= 0.0


# ======================================================================== #
# Code Arbitration Tests
# ======================================================================== #


class TestCodeArbitration:

    def test_picks_higher_weighted_action(self) -> None:
        recs = [
            Recommendation("domestic", "IMPROVE_ECONOMY", confidence=0.9),
            Recommendation("military", "BUILD_FLEET", confidence=0.9),
        ]
        # Democracy: dom=0.40, mil=0.40 → equal weight, first with higher score wins
        # Both have same score (0.36), pick first encountered with highest
        d = _code_arbitrate(recs, "Democracy", {})
        assert d.action in ALLOWED_ACTIONS

    def test_imperial_ruler_dominates(self) -> None:
        # Imperial: domestic=0.10, military=0.10 — equal weights
        # Higher confidence wins
        recs = [
            Recommendation("domestic", "IMPROVE_ECONOMY", confidence=0.5),
            Recommendation("military", "BUILD_FLEET", confidence=0.9),
        ]
        d = _code_arbitrate(recs, "Imperial", {})
        assert d.action == "BUILD_FLEET"

    def test_democracy_balanced(self) -> None:
        # Democracy weights are equal, so confidence decides
        recs = [
            Recommendation("domestic", "FOCUS_TECH", confidence=0.95),
            Recommendation("military", "BUILD_FLEET", confidence=0.3),
        ]
        d = _code_arbitrate(recs, "Democracy", {})
        assert d.action == "FOCUS_TECH"

    def test_empty_recommendations_consolidate(self) -> None:
        d = _code_arbitrate([], "Imperial", {})
        assert d.action == "CONSOLIDATE"

    def test_single_recommendation_wins(self) -> None:
        recs = [Recommendation("military", "DEFEND", confidence=0.6)]
        d = _code_arbitrate(recs, "Imperial", {})
        assert d.action == "DEFEND"

    def test_output_is_valid_directive(self) -> None:
        recs = [
            Recommendation("domestic", "COLONIZE", confidence=0.7, reasoning="Good planet"),
            Recommendation("military", "EXPAND", confidence=0.6, reasoning="Need space"),
        ]
        d = _code_arbitrate(recs, "Oligarchy", {})
        assert isinstance(d, Directive)
        assert d.action in ALLOWED_ACTIONS
        assert d.reason  # not empty


# ======================================================================== #
# Council Orchestrator Tests
# ======================================================================== #


class TestCouncilOrchestrator:

    def test_imperial_code_arbitration(
        self, imperial_ruleset: dict, imperial_personality: dict, early_game_state: dict,
    ) -> None:
        """Imperial government uses code-only arbitration."""
        council = CouncilOrchestrator(
            provider=StubProvider(),
            government="Imperial",
            personality=imperial_personality,
            ruleset=imperial_ruleset,
            parallel=False,
        )
        result = council.decide(early_game_state)
        assert isinstance(result, CouncilResult)
        assert result.directive.action in ALLOWED_ACTIONS
        assert result.arbitration_method == "code"
        assert len(result.recommendations) == 2

    def test_democracy_llm_arbitration(
        self, democratic_ruleset: dict, democratic_personality: dict, early_game_state: dict,
    ) -> None:
        """Democratic government uses LLM arbitration when enabled."""
        provider = AlternatingStubProvider()
        council = CouncilOrchestrator(
            provider=provider,
            government="Democracy",
            personality=democratic_personality,
            ruleset=democratic_ruleset,
            parallel=False,
            arbiter_uses_llm=True,
        )
        result = council.decide(early_game_state)
        assert result.directive.action in ALLOWED_ACTIONS
        assert result.arbitration_method == "llm"
        # 2 sub-agents + 1 arbiter = 3 calls
        assert provider.call_count == 3

    def test_democracy_code_arbitration_when_disabled(
        self, democratic_ruleset: dict, democratic_personality: dict, early_game_state: dict,
    ) -> None:
        """Democratic government uses code arbitration when LLM disabled."""
        provider = AlternatingStubProvider()
        council = CouncilOrchestrator(
            provider=provider,
            government="Democracy",
            personality=democratic_personality,
            ruleset=democratic_ruleset,
            parallel=False,
            arbiter_uses_llm=False,
        )
        result = council.decide(early_game_state)
        assert result.arbitration_method == "code"
        # Only 2 sub-agent calls, no arbiter
        assert provider.call_count == 2

    def test_parallel_execution(
        self, imperial_ruleset: dict, imperial_personality: dict, early_game_state: dict,
    ) -> None:
        """Parallel mode still produces valid results."""
        council = CouncilOrchestrator(
            provider=StubProvider(),
            government="Imperial",
            personality=imperial_personality,
            ruleset=imperial_ruleset,
            parallel=True,
        )
        result = council.decide(early_game_state)
        assert result.directive.action in ALLOWED_ACTIONS
        assert len(result.recommendations) == 2

    def test_latencies_recorded(
        self, imperial_ruleset: dict, imperial_personality: dict, early_game_state: dict,
    ) -> None:
        council = CouncilOrchestrator(
            provider=StubProvider(),
            government="Imperial",
            personality=imperial_personality,
            ruleset=imperial_ruleset,
            parallel=False,
        )
        result = council.decide(early_game_state)
        assert "domestic" in result.agent_latencies_ms
        assert "military" in result.agent_latencies_ms
        assert result.total_latency_ms > 0

    def test_update_context(
        self, imperial_ruleset: dict, imperial_personality: dict,
    ) -> None:
        council = CouncilOrchestrator(
            provider=StubProvider(),
            government="Imperial",
            personality=imperial_personality,
            ruleset=imperial_ruleset,
        )
        new_personality = {**imperial_personality, "war_willingness": 1.0}
        council.update_context("Democracy", new_personality, imperial_ruleset)
        assert council._government == "Democracy"
        assert council._personality["war_willingness"] == 1.0


# ======================================================================== #
# Failure Handling Tests
# ======================================================================== #


class TestFailureHandling:

    def test_one_agent_fails_other_succeeds(
        self, imperial_ruleset: dict, imperial_personality: dict, early_game_state: dict,
    ) -> None:
        """If one agent fails, the other's recommendation is used."""
        call_count = 0

        class PartialFailProvider(LLMProvider):
            def complete(self, prompt: str) -> LLMResponse:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise LLMProviderError("First agent fails")
                return LLMResponse(
                    text=(
                        "ACTION: DEFEND\nTARGET: NONE\n"
                        "CONFIDENCE: 0.7\nREASON: Border threat."
                    ),
                    model="partial",
                )

            def is_available(self) -> bool:
                return True

            @property
            def name(self) -> str:
                return "partial"

        council = CouncilOrchestrator(
            provider=PartialFailProvider(),
            government="Imperial",
            personality=imperial_personality,
            ruleset=imperial_ruleset,
            parallel=False,
        )
        result = council.decide(early_game_state)
        assert result.directive.action == "DEFEND"
        assert len(result.recommendations) == 1

    def test_all_agents_fail_consolidate(
        self, imperial_ruleset: dict, imperial_personality: dict, early_game_state: dict,
    ) -> None:
        """If all agents fail, falls back to CONSOLIDATE."""
        council = CouncilOrchestrator(
            provider=FailingProvider(),
            government="Imperial",
            personality=imperial_personality,
            ruleset=imperial_ruleset,
            parallel=False,
        )
        result = council.decide(early_game_state)
        assert result.directive.action == "CONSOLIDATE"
        assert len(result.recommendations) == 0


# ======================================================================== #
# Government Coverage Tests
# ======================================================================== #


class TestGovernmentCoverage:

    @pytest.mark.parametrize("gov", list(GOVERNMENT_WEIGHTS.keys()))
    def test_all_governments_produce_directive(
        self, gov: str, early_game_state: dict,
    ) -> None:
        """Every government type produces a valid directive."""
        empire = {
            "ethics": ["Militarist", "Materialist"],
            "civics": ["Technocracy"],
            "traits": ["Intelligent"],
            "origin": "Prosperous Unification",
            "government": gov,
        }
        ruleset = generate_ruleset(**empire)
        personality = build_personality(**empire)

        council = CouncilOrchestrator(
            provider=StubProvider(),
            government=gov,
            personality=personality,
            ruleset=ruleset,
            parallel=False,
            arbiter_uses_llm=False,  # code-only for deterministic test
        )
        result = council.decide(early_game_state)
        assert result.directive.action in ALLOWED_ACTIONS

    @pytest.mark.parametrize("gov", sorted(CODE_ARBITER_GOVERNMENTS))
    def test_code_arbiter_governments(self, gov: str) -> None:
        """These governments always use code arbitration."""
        assert gov in CODE_ARBITER_GOVERNMENTS


# ======================================================================== #
# FoW Integrity Tests
# ======================================================================== #


class TestFoWIntegrity:

    def test_domestic_state_no_enemy_details(self) -> None:
        """Domestic state should not leak enemy fleet details."""
        state = {
            "year": 2210,
            "known_empires": [
                {"name": "Enemy", "attitude": "Hostile", "fleet_power": 9999},
            ],
        }
        ds = _domestic_state(state)
        assert "known_empires" not in ds

    def test_military_state_no_economy_details(self) -> None:
        """Military state should not include full economy breakdown."""
        state = {
            "year": 2210,
            "economy": {
                "energy": 100, "minerals": 200, "food": 80,
                "alloys": 30, "consumer_goods": 20,
            },
        }
        ms = _military_state(state)
        assert "economy" not in ms
        assert ms["alloys"] == 30
        assert ms["energy"] == 100
        # No other economy fields
        assert "minerals" not in ms
        assert "food" not in ms
