"""Tests for personality_shards — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.personality_shards import build_personality


class TestGovernmentWeights:

    def test_imperial_ruler_dominant(self, cybernetic_creed_empire: dict) -> None:
        p = build_personality(**cybernetic_creed_empire)
        assert p["leader_weights"]["ruler"] == 0.80

    def test_democracy_balanced(self, une_empire: dict) -> None:
        p = build_personality(**une_empire)
        assert p["leader_weights"]["ruler"] == 0.20

    def test_oligarchy_ruler_moderate(self, void_dwellers_empire: dict) -> None:
        p = build_personality(**void_dwellers_empire)
        assert p["leader_weights"]["ruler"] == 0.40

    def test_dictatorial_weights(self, uor_empire: dict) -> None:
        p = build_personality(**uor_empire)
        assert p["leader_weights"]["ruler"] == 0.70

    def test_hive_mind_unified(self, hive_mind_empire: dict) -> None:
        p = build_personality(**hive_mind_empire)
        assert p["leader_weights"]["ruler"] == 1.0

    def test_machine_unified(self, machine_empire: dict) -> None:
        p = build_personality(**machine_empire)
        assert p["leader_weights"]["ruler"] == 1.0


class TestEthicsInfluence:

    def test_militarist_increases_war(self) -> None:
        p = build_personality(
            ethics=["Militarist"], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        assert p["war_willingness"] > 0.5

    def test_fanatic_stronger_than_normal(self) -> None:
        normal = build_personality(
            ethics=["Militarist"], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        fanatic = build_personality(
            ethics=["Fanatic Militarist"], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        assert fanatic["war_willingness"] > normal["war_willingness"]

    def test_pacifist_decreases_war(self) -> None:
        p = build_personality(
            ethics=["Pacifist"], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        assert p["war_willingness"] < 0.5

    def test_xenophile_increases_diplomacy(self) -> None:
        p = build_personality(
            ethics=["Xenophile"], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        assert p["diplomatic_openness"] > 0.5

    def test_materialist_increases_tech(self) -> None:
        p = build_personality(
            ethics=["Materialist"], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        assert p["tech_focus"] > 0.5

    def test_spiritualist_increases_unity(self) -> None:
        p = build_personality(
            ethics=["Spiritualist"], civics=[], traits=[],
            origin="Prosperous Unification", government="Democracy",
        )
        assert p["unity_focus"] > 0.5


class TestAscensionPreference:

    def test_cybernetic_creed_prefers_cybernetic(self, cybernetic_creed_empire: dict) -> None:
        p = build_personality(**cybernetic_creed_empire)
        assert p["ascension_preference"] == "cybernetic"

    def test_uor_prefers_synthetic(self, uor_empire: dict) -> None:
        p = build_personality(**uor_empire)
        assert p["ascension_preference"] == "synthetic"


class TestExpandedCivics:

    def test_genocidal_maxes_war_willingness(self) -> None:
        p = build_personality(
            ethics=["Fanatic Xenophobe", "Militarist"],
            civics=["Fanatic Purifiers"],
            traits=[], origin="Prosperous Unification", government="Dictatorial",
        )
        assert p["war_willingness"] == 1.0
        assert p["diplomatic_openness"] == 0.0
        assert p["fleet_doctrine"] == "aggressive"

    def test_corporate_increases_trade(self) -> None:
        p = build_personality(
            ethics=["Xenophile"], civics=["Corporate Authority"],
            traits=[], origin="Prosperous Unification", government="Corporate",
        )
        assert p["trade_focus"] > 0.5
        assert p["economic_style"] == "trade_focused"

    def test_diplomatic_corps_increases_openness(self) -> None:
        p = build_personality(
            ethics=["Xenophile"], civics=["Diplomatic Corps"],
            traits=[], origin="Prosperous Unification", government="Democracy",
        )
        assert p["diplomatic_openness"] > 0.7


class TestExpandedTraits:

    def test_ingenious_sets_energy_focus(self) -> None:
        p = build_personality(
            ethics=[], civics=[], traits=["Ingenious"],
            origin="Prosperous Unification", government="Democracy",
        )
        assert p["economic_style"] == "energy_focused"

    def test_lithoid_sets_mineral_focus(self) -> None:
        p = build_personality(
            ethics=[], civics=[], traits=["Lithoid"],
            origin="Prosperous Unification", government="Democracy",
        )
        assert p["economic_style"] == "mineral_focused"

    def test_natural_scientists_boost_tech(self) -> None:
        p = build_personality(
            ethics=[], civics=[], traits=["Natural Physicists"],
            origin="Prosperous Unification", government="Democracy",
        )
        assert p["tech_focus"] > 0.5


class TestExpandedOrigins:

    def test_necrophage_increases_war(self) -> None:
        p = build_personality(
            ethics=["Xenophobe"], civics=[], traits=[],
            origin="Necrophage", government="Imperial",
        )
        assert p["war_willingness"] > 0.5

    def test_hegemon_increases_diplomacy(self) -> None:
        p = build_personality(
            ethics=[], civics=[], traits=[],
            origin="Hegemon", government="Imperial",
        )
        assert p["diplomatic_openness"] > 0.5

    def test_shattered_ring_boosts_tech(self) -> None:
        p = build_personality(
            ethics=[], civics=[], traits=[],
            origin="Shattered Ring", government="Democracy",
        )
        assert p["tech_focus"] > 0.6

    def test_endbringers_prefers_psionic(self, endbringer_empire: dict) -> None:
        p = build_personality(**endbringer_empire)
        assert p["ascension_preference"] == "psionic"

    def test_standard_origin_any(self, une_empire: dict) -> None:
        p = build_personality(**une_empire)
        assert p["ascension_preference"] == "any"


class TestValuesClamped:

    def test_all_values_in_range(self, cybernetic_creed_empire: dict) -> None:
        p = build_personality(**cybernetic_creed_empire)
        for key in ("war_willingness", "expansion_drive", "tech_focus",
                     "unity_focus", "diplomatic_openness", "trade_focus",
                     "risk_tolerance", "crisis_preparedness"):
            assert 0.0 <= p[key] <= 1.0, f"{key}={p[key]} out of range"

    def test_extreme_ethics_still_clamped(self) -> None:
        p = build_personality(
            ethics=["Fanatic Militarist", "Xenophobe"],
            civics=["Distinguished Admiralty", "Citizen Service"],
            traits=["Strong", "Very Strong"],
            origin="Doomsday",
            government="Imperial",
        )
        assert p["war_willingness"] <= 1.0
        assert p["risk_tolerance"] <= 1.0
