"""Tests for validator — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.ruleset_generator import generate_ruleset
from engine.validator import ALLOWED_ACTIONS, GAME_VERSION, validate_directive


@pytest.fixture
def _void_ruleset(void_dwellers_empire: dict) -> dict:
    return generate_ruleset(**void_dwellers_empire)


@pytest.fixture
def _endbringer_ruleset(endbringer_empire: dict) -> dict:
    return generate_ruleset(**endbringer_empire)


@pytest.fixture
def _inward_perfection_ruleset() -> dict:
    return generate_ruleset(
        ethics=["Fanatic Xenophobe", "Pacifist"],
        civics=["Inward Perfection"],
        traits=[],
        origin="Prosperous Unification",
        government="Democracy",
    )


@pytest.fixture
def _necrophage_ruleset(necrophage_empire: dict) -> dict:
    return generate_ruleset(**necrophage_empire)


class TestActionWhitelist:
    """Reject unknown actions."""

    def test_valid_action(self, early_game_state: dict) -> None:
        rs = generate_ruleset(
            ethics=["Militarist"], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        result = validate_directive(
            {"action": "BUILD_FLEET", "reason": "Fleet needed per militarist ethic."},
            rs, early_game_state,
        )
        assert result.valid

    def test_invalid_action_rejected(self, early_game_state: dict) -> None:
        rs = generate_ruleset(
            ethics=[], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        result = validate_directive(
            {"action": "NUKE_PLANET", "reason": "Test."},
            rs, early_game_state,
        )
        assert not result.valid
        assert any("Unknown action" in e for e in result.errors)


class TestVersionLock:
    """Reject mismatched game versions."""

    def test_version_mismatch(self, early_game_state: dict) -> None:
        rs = {"version": "3.99.0", "overrides": {}, "modifiers": {}}
        result = validate_directive(
            {"action": "CONSOLIDATE", "reason": "Test."},
            rs, early_game_state,
        )
        assert not result.valid
        assert any("version" in e.lower() for e in result.errors)


class TestFogOfWar:
    """Reject directives targeting unknown systems/empires."""

    def test_known_target_accepted(self, early_game_state: dict) -> None:
        rs = generate_ruleset(
            ethics=[], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        result = validate_directive(
            {"action": "DIPLOMACY", "target": "Tzynn Empire", "reason": "Known hostile neighbor."},
            rs, early_game_state,
        )
        assert result.valid

    def test_unknown_target_rejected(self, early_game_state: dict) -> None:
        rs = generate_ruleset(
            ethics=[], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        result = validate_directive(
            {"action": "PREPARE_WAR", "target": "Hidden Empire", "reason": "Attack."},
            rs, early_game_state,
        )
        assert not result.valid
        assert any("fog" in e.lower() for e in result.errors)

    def test_fleet_system_is_known(self, early_game_state: dict) -> None:
        """Fleet locations count as known targets."""
        rs = generate_ruleset(
            ethics=[], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        result = validate_directive(
            {"action": "BUILD_STARBASE", "target": "Sol", "reason": "Build at fleet location."},
            rs, early_game_state,
        )
        assert result.valid


class TestOriginConstraints:
    """Reject actions that violate origin rules."""

    def test_void_dwellers_planet_colonize_rejected(
        self, _void_ruleset: dict, early_game_state: dict,
    ) -> None:
        result = validate_directive(
            {
                "action": "COLONIZE",
                "reason": "Colonize continental world.",
                "parameters": {"planet_type": "continental"},
            },
            _void_ruleset, early_game_state,
        )
        assert not result.valid
        assert any("habitats only" in e.lower() for e in result.errors)

    def test_void_dwellers_habitat_accepted(
        self, _void_ruleset: dict, early_game_state: dict,
    ) -> None:
        result = validate_directive(
            {
                "action": "COLONIZE",
                "reason": "Colonize habitat per Void Dwellers origin.",
                "parameters": {"planet_type": "habitat"},
            },
            _void_ruleset, early_game_state,
        )
        assert result.valid

    def test_endbringers_non_psionic_rejected(
        self, _endbringer_ruleset: dict, early_game_state: dict,
    ) -> None:
        result = validate_directive(
            {
                "action": "FOCUS_TECH",
                "reason": "Pursue synthetic ascension.",
                "parameters": {"ascension_path": "synthetic"},
            },
            _endbringer_ruleset, early_game_state,
        )
        assert not result.valid
        assert any("psionic" in e.lower() for e in result.errors)

    def test_necrophage_primary_growth_rejected(
        self, _necrophage_ruleset: dict, early_game_state: dict,
    ) -> None:
        result = validate_directive(
            {
                "action": "IMPROVE_ECONOMY",
                "reason": "Grow necrophage pops.",
                "parameters": {"growth_target": "necrophage_primary"},
            },
            _necrophage_ruleset, early_game_state,
        )
        assert not result.valid
        assert any("necrophage" in e.lower() for e in result.errors)


class TestCivicConstraints:

    def test_inward_perfection_blocks_diplomacy(
        self, _inward_perfection_ruleset: dict, early_game_state: dict,
    ) -> None:
        result = validate_directive(
            {"action": "DIPLOMACY", "reason": "Send embassy."},
            _inward_perfection_ruleset, early_game_state,
        )
        assert not result.valid
        assert any("inward perfection" in e.lower() for e in result.errors)


class TestMetaForbidden:
    """Reject meta-forbidden patterns from META_4.3.4.md."""

    def test_disruptors_rejected(self, early_game_state: dict) -> None:
        rs = generate_ruleset(
            ethics=["Militarist"], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        result = validate_directive(
            {
                "action": "BUILD_FLEET",
                "reason": "Build disruptor corvettes.",
                "parameters": {"weapon_type": "disruptors"},
            },
            rs, early_game_state,
        )
        assert not result.valid
        assert any("dead in 4.3" in e.lower() for e in result.errors)

    def test_corvette_only_warned(self, early_game_state: dict) -> None:
        rs = generate_ruleset(
            ethics=[], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        result = validate_directive(
            {
                "action": "BUILD_FLEET",
                "reason": "Swarm with corvettes.",
                "parameters": {"composition": "corvette_only"},
            },
            rs, early_game_state,
        )
        assert len(result.warnings) > 0
        assert any("corvette" in w.lower() for w in result.warnings)


class TestReasonRequired:

    def test_empty_reason_rejected(self, early_game_state: dict) -> None:
        rs = generate_ruleset(
            ethics=[], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        result = validate_directive(
            {"action": "CONSOLIDATE", "reason": ""},
            rs, early_game_state,
        )
        assert not result.valid
        assert any("reason" in e.lower() for e in result.errors)


class TestResourceFeasibility:

    def test_build_fleet_low_alloys_warns(self) -> None:
        rs = generate_ruleset(
            ethics=[], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        state = {
            "version": "4.3.4", "year": 2230, "month": 1,
            "economy": {"alloys": 10, "monthly_net": {"alloys": -5}},
            "colonies": [], "known_empires": [], "fleets": [],
        }
        result = validate_directive(
            {"action": "BUILD_FLEET", "reason": "Need ships."},
            rs, state,
        )
        assert any("alloy" in w.lower() for w in result.warnings)

    def test_expand_low_influence_warns(self) -> None:
        rs = generate_ruleset(
            ethics=[], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        state = {
            "version": "4.3.4", "year": 2230, "month": 1,
            "economy": {"influence": 20},
            "colonies": [], "known_empires": [], "fleets": [],
        }
        result = validate_directive(
            {"action": "EXPAND", "reason": "Grow borders."},
            rs, state,
        )
        assert any("influence" in w.lower() for w in result.warnings)


class TestCapacityChecks:

    def test_starbase_at_cap_warns(self) -> None:
        rs = generate_ruleset(
            ethics=[], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        state = {
            "version": "4.3.4", "year": 2230, "month": 1,
            "economy": {}, "colonies": [], "known_empires": [], "fleets": [],
            "naval_capacity": {"starbase_capacity": 3},
            "starbases": [
                {"system": "Sol", "level": "starport"},
                {"system": "Alpha", "level": "starport"},
                {"system": "Beta", "level": "starhold"},
            ],
        }
        result = validate_directive(
            {"action": "BUILD_STARBASE", "reason": "Need more starbases."},
            rs, state,
        )
        assert any("capacity" in w.lower() for w in result.warnings)


class TestGenocidalConstraints:

    def test_genocidal_cannot_diplomacy(self) -> None:
        rs = generate_ruleset(
            ethics=["Fanatic Xenophobe", "Militarist"],
            civics=["Fanatic Purifiers"],
            traits=[], origin="Prosperous Unification", government="Dictatorial",
        )
        state = {
            "version": "4.3.4", "year": 2230, "month": 1,
            "economy": {}, "colonies": [], "known_empires": [], "fleets": [],
        }
        result = validate_directive(
            {"action": "DIPLOMACY", "reason": "Form alliance."},
            rs, state,
        )
        assert not result.valid
        assert any("genocidal" in e.lower() for e in result.errors)
