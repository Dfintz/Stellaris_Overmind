"""Tests for game_loop — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.bridge import BridgeConfig
from engine.game_loop import EmpireConfig, GameLoopController, LoopStats
from engine.llm_provider import StubProvider


@pytest.fixture
def empire() -> EmpireConfig:
    return EmpireConfig(
        ethics=["Militarist", "Materialist"],
        civics=["Technocracy"],
        traits=["Intelligent"],
        origin="Prosperous Unification",
        government="Oligarchy",
    )


@pytest.fixture
def controller(empire: EmpireConfig, tmp_path) -> GameLoopController:
    from engine.recorder import GameRecorder

    config = BridgeConfig(bridge_dir=tmp_path / "bridge")
    recorder = GameRecorder(replay_dir=tmp_path / "replays")
    return GameLoopController(
        empire=empire,
        provider=StubProvider(),
        bridge_config=config,
        recorder=recorder,
    )


class TestControllerInit:

    def test_ruleset_generated(self, controller: GameLoopController) -> None:
        assert controller._ruleset["version"] == "4.3.4"

    def test_personality_generated(self, controller: GameLoopController) -> None:
        assert "tech_focus" in controller._personality

    def test_stats_initialized(self, controller: GameLoopController) -> None:
        assert controller.stats.decisions_made == 0


class TestTickOnce:

    def test_stub_produces_consolidate(
        self, controller: GameLoopController, early_game_state: dict,
    ) -> None:
        d = controller.tick_once(early_game_state)
        assert d is not None
        assert d.action == "CONSOLIDATE"

    def test_increments_stats(
        self, controller: GameLoopController, early_game_state: dict,
    ) -> None:
        controller.tick_once(early_game_state)
        assert controller.stats.decisions_made == 1

    def test_records_decision(
        self, controller: GameLoopController, early_game_state: dict,
    ) -> None:
        # tick_once doesn't record (only _tick does), but stats update
        controller.tick_once(early_game_state)
        assert controller.stats.last_action == "CONSOLIDATE"


class TestRulesetRefresh:

    def test_refresh_on_civic_change(
        self, controller: GameLoopController, early_game_state: dict,
    ) -> None:
        # Simulate government reform
        state = dict(early_game_state)
        state["empire"] = {
            "ethics": ["Fanatic Militarist"],
            "civics": ["Distinguished Admiralty"],
            "origin": "Prosperous Unification",
            "government": "Oligarchy",
        }
        controller._maybe_refresh_ruleset(state)
        assert controller._ruleset["base"].get("fire_rate_mult") == 0.20

    def test_no_refresh_when_unchanged(
        self, controller: GameLoopController, early_game_state: dict,
    ) -> None:
        state = dict(early_game_state)
        state["empire"] = {
            "ethics": ["Materialist", "Militarist"],
            "civics": ["Technocracy"],
            "origin": "Prosperous Unification",
            "government": "Oligarchy",
        }
        old_ruleset = controller._ruleset
        controller._maybe_refresh_ruleset(state)
        # Ruleset should be the same object (not regenerated)
        assert controller._ruleset is old_ruleset
