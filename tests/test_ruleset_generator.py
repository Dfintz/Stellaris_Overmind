"""Tests for ruleset_generator — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.ruleset_generator import (
    CIVIC_MODIFIERS,
    ETHICS_BASE,
    GAME_VERSION,
    ORIGIN_OVERRIDES,
    TRAIT_MICRO,
    GamePhase,
    generate_ruleset,
    get_crisis_counter,
    get_fleet_template,
    get_phase_priorities,
    get_weapon_meta,
)


class TestGenerateRuleset:
    """Test composite ruleset generation."""

    def test_version_is_434(self, une_empire: dict) -> None:
        rs = generate_ruleset(**une_empire)
        assert rs["version"] == "4.3.4"

    def test_ethics_applied(self, une_empire: dict) -> None:
        rs = generate_ruleset(**une_empire)
        # Militarist should set war_frequency
        assert rs["base"].get("war_frequency") == "high"

    def test_civics_applied(self, une_empire: dict) -> None:
        rs = generate_ruleset(**une_empire)
        assert "egalitarian_attraction" in rs["modifiers"]

    def test_traits_applied(self, une_empire: dict) -> None:
        rs = generate_ruleset(**une_empire)
        assert "researcher_job_efficiency" in rs["micro_modifiers"]

    def test_origin_overrides_applied(self, void_dwellers_empire: dict) -> None:
        rs = generate_ruleset(**void_dwellers_empire)
        assert rs["overrides"].get("colonization_rules") == "habitats_only"

    def test_meta_tier_from_origin(self, cybernetic_creed_empire: dict) -> None:
        rs = generate_ruleset(**cybernetic_creed_empire)
        assert rs["meta_tier"] == "S"

    def test_meta_strategy_from_origin(self, uor_empire: dict) -> None:
        rs = generate_ruleset(**uor_empire)
        assert rs["meta_strategy"] == "synthetic_ascension_snowball"

    def test_standard_origin_meta_tier(self, une_empire: dict) -> None:
        rs = generate_ruleset(**une_empire)
        assert rs["meta_tier"] == "C"

    def test_hierarchy_origin_overrides_ethics(self) -> None:
        """Origin overrides should be set even if ethics set conflicting values."""
        rs = generate_ruleset(
            ethics=["Materialist"],
            civics=[],
            traits=[],
            origin="Cybernetic Creed",
            government="Imperial",
        )
        # Origin sets worker_stacking, which is not in ethics
        assert rs["overrides"].get("worker_stacking") is True

    def test_fanatic_ethics(self) -> None:
        rs = generate_ruleset(
            ethics=["Fanatic Militarist"],
            civics=[],
            traits=[],
            origin="Prosperous Unification",
            government="Democracy",
        )
        assert rs["base"]["fire_rate_mult"] == 0.20


class TestEthicsData:
    """Verify ethics data covers all meta-relevant ethics."""

    @pytest.mark.parametrize("ethic", [
        "Militarist", "Fanatic Militarist",
        "Pacifist", "Fanatic Pacifist",
        "Xenophile", "Fanatic Xenophile",
        "Xenophobe", "Fanatic Xenophobe",
        "Egalitarian", "Fanatic Egalitarian",
        "Authoritarian", "Fanatic Authoritarian",
        "Materialist", "Fanatic Materialist",
        "Spiritualist", "Fanatic Spiritualist",
    ])
    def test_ethic_exists(self, ethic: str) -> None:
        assert ethic in ETHICS_BASE

    def test_authoritarian_worker_job_efficiency(self) -> None:
        """4.3 changed authoritarian worker bonus to job efficiency."""
        assert "worker_job_efficiency" in ETHICS_BASE["Authoritarian"]

    def test_egalitarian_specialist_job_efficiency(self) -> None:
        """4.3 changed egalitarian specialist bonus to job efficiency."""
        assert "specialist_job_efficiency" in ETHICS_BASE["Egalitarian"]


class TestCivicsData:
    """Verify civic data covers meta civics."""

    @pytest.mark.parametrize("civic", [
        "Technocracy", "Masterful Crafters", "Distinguished Admiralty",
        "Citizen Service", "Slaver Guilds", "Byzantine Bureaucracy",
        "Corvée System", "Worker Cooperative",
    ])
    def test_meta_civic_exists(self, civic: str) -> None:
        assert civic in CIVIC_MODIFIERS

    def test_distinguished_admiralty_command_limit(self) -> None:
        """4.3: Distinguished Admiralty gives +20% command limit (multiplicative)."""
        assert CIVIC_MODIFIERS["Distinguished Admiralty"]["command_limit_mult"] == 0.20


class TestOriginData:
    """Verify origin data covers meta origins."""

    @pytest.mark.parametrize("origin,expected_tier", [
        ("Cybernetic Creed", "S"),
        ("Under One Rule", "S"),
        ("Void Dwellers", "S"),
        ("Necrophage", "A"),
        ("Endbringers", "A"),
        ("Synthetic Fertility", "A"),
        ("Doomsday", "B"),
    ])
    def test_origin_tier(self, origin: str, expected_tier: str) -> None:
        assert ORIGIN_OVERRIDES[origin]["meta_tier"] == expected_tier

    def test_endbringers_psionic_lock(self) -> None:
        assert ORIGIN_OVERRIDES["Endbringers"]["ascension_lock"] == "psionic"

    def test_cybernetic_creed_cybernetic_lock(self) -> None:
        assert ORIGIN_OVERRIDES["Cybernetic Creed"]["ascension_lock"] == "cybernetic"

    def test_void_dwellers_habitats_only(self) -> None:
        assert ORIGIN_OVERRIDES["Void Dwellers"]["colonization_rules"] == "habitats_only"


class TestPhaseAndFleet:
    """Test game-phase priorities and fleet templates."""

    def test_early_phase(self) -> None:
        p = get_phase_priorities(2210)
        assert p["phase"] == "early"
        assert p["economy_focus"] == "minerals_first"

    def test_mid_phase(self) -> None:
        p = get_phase_priorities(2280)
        assert p["phase"] == "mid"

    def test_late_phase(self) -> None:
        p = get_phase_priorities(2380)
        assert p["phase"] == "late"
        assert "repeatables" in p["research_priority"]

    def test_fleet_template_early(self) -> None:
        tmpl = get_fleet_template(2210)
        assert tmpl.phase == GamePhase.EARLY
        assert "corvette" in tmpl.composition

    def test_fleet_template_late(self) -> None:
        tmpl = get_fleet_template(2380)
        assert tmpl.phase == GamePhase.LATE
        assert "battleship" in tmpl.composition

    def test_weapon_meta_disruptors_dead(self) -> None:
        weapons = get_weapon_meta()
        disruptor = next(w for w in weapons if "Disruptor" in w["name"])
        assert disruptor["verdict"] == "DEAD"

    def test_crisis_counter_unbidden(self) -> None:
        counter = get_crisis_counter("Unbidden")
        assert counter is not None
        assert "armor" in counter["loadout"]

    def test_crisis_counter_unknown(self) -> None:
        assert get_crisis_counter("NonexistentCrisis") is None
