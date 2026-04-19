"""Tests for scorer — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.scorer import OutcomeScores, score_outcome


@pytest.fixture
def basic_ruleset() -> dict:
    return {"version": "4.3.4", "base": {}, "modifiers": {}, "overrides": {}}


class TestEconomyScoring:

    def test_growing_economy_positive(self, basic_ruleset: dict) -> None:
        before = {"economy": {"energy": 100, "minerals": 200, "alloys": 50, "consumer_goods": 20, "unity": 10}}
        after = {"economy": {"energy": 200, "minerals": 400, "alloys": 100, "consumer_goods": 40, "unity": 20}}
        scores = score_outcome(before, after, {"action": "IMPROVE_ECONOMY", "reason": "test"}, basic_ruleset)
        assert scores.economy_delta > 0

    def test_shrinking_economy_negative(self, basic_ruleset: dict) -> None:
        before = {"economy": {"energy": 200, "minerals": 400, "alloys": 100, "consumer_goods": 40, "unity": 20}}
        after = {"economy": {"energy": 50, "minerals": 100, "alloys": 20, "consumer_goods": 10, "unity": 5}}
        scores = score_outcome(before, after, {"action": "CONSOLIDATE", "reason": "test"}, basic_ruleset)
        assert scores.economy_delta < 0

    def test_flat_economy_neutral(self, basic_ruleset: dict) -> None:
        eco = {"economy": {"energy": 100, "minerals": 100, "alloys": 50, "consumer_goods": 20, "unity": 10}}
        scores = score_outcome(eco, eco, {"action": "CONSOLIDATE", "reason": "test"}, basic_ruleset)
        assert scores.economy_delta == 0.0


class TestFleetScoring:

    def test_fleet_growth_positive(self, basic_ruleset: dict) -> None:
        before = {"fleets": [{"power": 1000}], "economy": {}}
        after = {"fleets": [{"power": 2000}], "economy": {}}
        scores = score_outcome(before, after, {"action": "BUILD_FLEET", "reason": "test"}, basic_ruleset)
        assert scores.fleet_delta > 0

    def test_fleet_destroyed_negative(self, basic_ruleset: dict) -> None:
        before = {"fleets": [{"power": 5000}], "economy": {}}
        after = {"fleets": [], "economy": {}}
        scores = score_outcome(before, after, {"action": "DEFEND", "reason": "test"}, basic_ruleset)
        assert scores.fleet_delta < 0


class TestStabilityScoring:

    def test_deficit_penalized(self, basic_ruleset: dict) -> None:
        before = {"economy": {"energy": 100}}
        after = {"economy": {"energy": -50}}
        scores = score_outcome(before, after, {"action": "EXPAND", "reason": "test"}, basic_ruleset)
        assert scores.stability_score < 0.5

    def test_high_alloys_rewarded(self, basic_ruleset: dict) -> None:
        before = {"economy": {}}
        after = {"economy": {"alloys": 500}}
        scores = score_outcome(before, after, {"action": "IMPROVE_ECONOMY", "reason": "test"}, basic_ruleset)
        assert scores.stability_score > 0.5


class TestMetaAlignment:

    def test_early_economy_action_rewarded(self, basic_ruleset: dict) -> None:
        state = {"year": 2210, "economy": {}}
        scores = score_outcome(state, state, {"action": "IMPROVE_ECONOMY", "reason": "minerals first per meta"}, basic_ruleset)
        assert scores.meta_alignment > 0.5

    def test_early_war_penalized(self, basic_ruleset: dict) -> None:
        state = {"year": 2205, "economy": {}}
        scores = score_outcome(state, state, {"action": "PREPARE_WAR", "reason": "test"}, basic_ruleset)
        assert scores.meta_alignment < 0.5

    def test_disruptor_in_reason_penalized(self, basic_ruleset: dict) -> None:
        state = {"year": 2250, "economy": {}}
        scores = score_outcome(state, state, {"action": "BUILD_FLEET", "reason": "build disruptor corvettes"}, basic_ruleset)
        assert scores.meta_alignment < 0.5


class TestComposite:

    def test_composite_is_weighted_sum(self, basic_ruleset: dict) -> None:
        before = {"economy": {"energy": 100, "minerals": 100, "alloys": 50, "consumer_goods": 20, "unity": 10}, "fleets": [{"power": 1000}], "colonies": ["A"]}
        after = {"economy": {"energy": 200, "minerals": 200, "alloys": 100, "consumer_goods": 40, "unity": 20}, "fleets": [{"power": 2000}], "colonies": ["A", "B"]}
        scores = score_outcome(before, after, {"action": "EXPAND", "reason": "expansion per meta"}, basic_ruleset)
        assert -1.0 <= scores.composite <= 1.0

    def test_scores_to_dict(self, basic_ruleset: dict) -> None:
        scores = OutcomeScores(economy_delta=0.5, composite=0.3)
        d = scores.to_dict()
        assert d["economy_delta"] == 0.5
        assert d["composite"] == 0.3
