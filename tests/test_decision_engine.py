"""Tests for decision_engine — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.decision_engine import (
    ALLOWED_ACTIONS,
    Directive,
    build_prompt,
    decide,
    parse_llm_response,
)
from engine.personality_shards import build_personality
from engine.ruleset_generator import generate_ruleset


class TestParseResponse:

    def test_valid_response(self) -> None:
        raw = "ACTION: BUILD_FLEET\nTARGET: Sol\nREASON: Militarist ethic demands fleet."
        d = parse_llm_response(raw)
        assert d.action == "BUILD_FLEET"
        assert d.target == "Sol"
        assert "Militarist" in d.reason

    def test_none_target(self) -> None:
        raw = "ACTION: CONSOLIDATE\nTARGET: NONE\nREASON: Stability needed."
        d = parse_llm_response(raw)
        assert d.target is None

    def test_invalid_action_raises(self) -> None:
        raw = "ACTION: NUKE_PLANET\nTARGET: NONE\nREASON: Test."
        with pytest.raises(ValueError, match="Invalid action"):
            parse_llm_response(raw)

    def test_case_insensitive_parsing(self) -> None:
        raw = "action: expand\ntarget: none\nreason: Need space."
        d = parse_llm_response(raw)
        assert d.action == "EXPAND"

    def test_extra_whitespace(self) -> None:
        raw = "  ACTION:  BUILD_FLEET  \n  TARGET:  Sol  \n  REASON:  Fleet needed.  "
        d = parse_llm_response(raw)
        assert d.action == "BUILD_FLEET"
        assert d.target == "Sol"


class TestBuildPrompt:

    def test_prompt_contains_meta_rules(self, une_empire: dict, early_game_state: dict) -> None:
        rs = generate_ruleset(**une_empire)
        p = build_personality(**une_empire)
        prompt = build_prompt(rs, p, early_game_state, None)
        assert "Disruptors are DEAD" in prompt
        assert "ALLOWED ACTIONS" in prompt
        assert "4.3.4" in prompt

    def test_prompt_contains_fleet_meta(self, une_empire: dict, early_game_state: dict) -> None:
        rs = generate_ruleset(**une_empire)
        p = build_personality(**une_empire)
        prompt = build_prompt(rs, p, early_game_state, None)
        assert "FLEET" in prompt
        assert "corvette" in prompt.lower()

    def test_prompt_contains_phase(self, une_empire: dict, early_game_state: dict) -> None:
        rs = generate_ruleset(**une_empire)
        p = build_personality(**une_empire)
        prompt = build_prompt(rs, p, early_game_state, None)
        assert "early" in prompt.lower()

    def test_prompt_contains_event(self, une_empire: dict, early_game_state: dict) -> None:
        rs = generate_ruleset(**une_empire)
        p = build_personality(**une_empire)
        prompt = build_prompt(rs, p, early_game_state, "WAR_DECLARED")
        assert "WAR_DECLARED" in prompt


class TestDecide:

    def test_stub_returns_consolidate(self, une_empire: dict, early_game_state: dict) -> None:
        rs = generate_ruleset(**une_empire)
        d = decide(rs, early_game_state)
        assert d.action == "CONSOLIDATE"

    def test_custom_llm_callable(self, une_empire: dict, early_game_state: dict) -> None:
        rs = generate_ruleset(**une_empire)

        def fake_llm(prompt: str) -> str:
            return "ACTION: BUILD_FLEET\nTARGET: Sol\nREASON: Militarist ethic base."

        d = decide(rs, early_game_state, llm_callable=fake_llm)
        assert d.action == "BUILD_FLEET"
        assert d.target == "Sol"

    def test_personality_passed(self, une_empire: dict, early_game_state: dict) -> None:
        rs = generate_ruleset(**une_empire)
        p = build_personality(**une_empire)
        d = decide(rs, early_game_state, personality=p)
        assert isinstance(d, Directive)

    def test_to_dict(self) -> None:
        d = Directive(action="EXPAND", target="Alpha Centauri", reason="Expansion drive.")
        dd = d.to_dict()
        assert dd["action"] == "EXPAND"
        assert dd["target"] == "Alpha Centauri"
