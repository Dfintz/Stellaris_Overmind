"""Tests for strategic_knowledge — Stellaris 4.3.4."""

from __future__ import annotations

from engine.strategic_knowledge import (
    DISTRICT_TYPES,
    EDICTS,
    FALLEN_EMPIRE_META,
    FALLEN_EMPIRE_TYPES,
    GALACTIC_COMMUNITY,
    LEADER_TRAITS,
    PLANET_BUILDINGS,
    PLANET_BUILD_META,
    POLICIES,
    RELICS,
    SHIP_COMPONENTS,
    SHIP_DESIGN_META,
    SITUATIONS,
    STARBASE_STRATEGY,
    SUBJECT_TYPES,
    TECH_PRIORITIES,
    WAR_GOALS,
    get_edict_guidance,
    get_policy_guidance,
    get_starbase_guidance,
    get_tech_priorities,
    get_tradition_guidance,
    get_ascension_perk_guidance,
    get_megastructure_guidance,
    get_designation_for_focus,
)


class TestEdicts:

    def test_edicts_have_required_fields(self) -> None:
        for name, edict in EDICTS.items():
            assert "effect" in edict, f"{name} missing effect"
            assert "cost" in edict, f"{name} missing cost"
            assert "meta" in edict, f"{name} missing meta"

    def test_edict_guidance_early(self) -> None:
        edicts = get_edict_guidance(2210)
        names = [e["name"] for e in edicts]
        assert "map_the_stars" in names

    def test_edict_guidance_late(self) -> None:
        edicts = get_edict_guidance(2400)
        # Late game returns all edicts
        assert len(edicts) >= 5


class TestTechPriorities:

    def test_early_tech_priorities(self) -> None:
        tp = get_tech_priorities(2210)
        assert tp["phase"] == "early"
        assert "physics" in tp
        assert "society" in tp
        assert "engineering" in tp
        assert "meta_notes" in tp

    def test_mid_tech_priorities(self) -> None:
        tp = get_tech_priorities(2280)
        assert tp["phase"] == "mid"

    def test_late_tech_priorities(self) -> None:
        tp = get_tech_priorities(2380)
        assert tp["phase"] == "late"


class TestPolicies:

    def test_policies_have_options(self) -> None:
        for name, policy in POLICIES.items():
            assert "options" in policy, f"{name} missing options"
            assert len(policy["options"]) >= 2, f"{name} has too few options"

    def test_policy_guidance_early(self) -> None:
        guide = get_policy_guidance(2210)
        assert guide["phase"] == "early"
        recs = guide["recommended"]
        assert "diplomatic_stance" in recs
        assert recs["diplomatic_stance"] == "diplo_stance_expansionist"

    def test_policy_guidance_militarist(self) -> None:
        guide = get_policy_guidance(2280, ["ethic_militarist"])
        recs = guide["recommended"]
        assert recs["diplomatic_stance"] == "diplo_stance_supremacist"


class TestStarbaseStrategy:

    def test_all_phases_exist(self) -> None:
        for key in ("early_game", "mid_game", "late_game"):
            assert key in STARBASE_STRATEGY

    def test_starbase_guidance_early(self) -> None:
        sg = get_starbase_guidance(2210)
        assert "shipyard" in sg.get("priority", "")

    def test_starbase_guidance_late(self) -> None:
        sg = get_starbase_guidance(2380)
        assert "notes" in sg


class TestGalacticCommunity:

    def test_has_council_info(self) -> None:
        assert "council" in GALACTIC_COMMUNITY
        assert "custodian" in GALACTIC_COMMUNITY["council"]

    def test_has_resolution_categories(self) -> None:
        cats = GALACTIC_COMMUNITY["resolution_categories"]
        assert len(cats) >= 5
        assert "Supremacy" in cats
        assert "Commerce" in cats


class TestSubjectTypes:

    def test_has_basic_types(self) -> None:
        assert "vassal" in SUBJECT_TYPES
        assert "tributary" in SUBJECT_TYPES

    def test_has_overlord_types(self) -> None:
        assert "scholarium" in SUBJECT_TYPES
        assert "bulwark" in SUBJECT_TYPES
        assert "prospectorium" in SUBJECT_TYPES


class TestExistingAPIs:

    def test_tradition_guidance(self) -> None:
        guide = get_tradition_guidance(2210)
        assert "recommended_trees" in guide
        assert guide["phase"] == "early"

    def test_ascension_perk_guidance(self) -> None:
        perks = get_ascension_perk_guidance(tier=0)
        assert len(perks) > 0

    def test_megastructure_guidance(self) -> None:
        megas = get_megastructure_guidance(2380)
        assert len(megas) > 0

    def test_designation_for_focus(self) -> None:
        assert get_designation_for_focus("energy") == "Generator World"
        assert get_designation_for_focus("research") == "Tech-World"
        assert get_designation_for_focus("invalid") is None


class TestWarGoals:

    def test_has_basic_war_goals(self) -> None:
        assert "Conquer" in WAR_GOALS
        assert "Subjugation" in WAR_GOALS
        assert "Humiliation" in WAR_GOALS

    def test_has_genocidal_war_goals(self) -> None:
        assert "Purification" in WAR_GOALS
        assert "Absorption" in WAR_GOALS
        assert "Extermination" in WAR_GOALS
        assert "Assimilation" in WAR_GOALS

    def test_has_defensive_goals(self) -> None:
        assert "Containment" in WAR_GOALS
        assert "Independence" in WAR_GOALS

    def test_total_count(self) -> None:
        assert len(WAR_GOALS) >= 14


class TestShipComponents:

    def test_has_armor_types(self) -> None:
        assert "armor" in SHIP_COMPONENTS
        types = SHIP_COMPONENTS["armor"]["types"]
        assert "neutronium" in types
        assert "dragonscale" in types

    def test_has_shield_types(self) -> None:
        assert "shields" in SHIP_COMPONENTS
        types = SHIP_COMPONENTS["shields"]["types"]
        assert "dark_matter_deflectors" in types

    def test_has_combat_computers(self) -> None:
        assert "combat_computers" in SHIP_COMPONENTS
        types = SHIP_COMPONENTS["combat_computers"]["types"]
        assert "artillery" in types
        assert "swarm" in types

    def test_has_auras(self) -> None:
        assert "auras" in SHIP_COMPONENTS
        assert "inspiring_presence" in SHIP_COMPONENTS["auras"]

    def test_ship_design_meta_coverage(self) -> None:
        assert "corvette" in SHIP_DESIGN_META
        assert "battleship" in SHIP_DESIGN_META
        assert "titan" in SHIP_DESIGN_META
        assert "colossus" in SHIP_DESIGN_META
        assert len(SHIP_DESIGN_META) >= 7


class TestFallenEmpires:

    def test_all_types_present(self) -> None:
        assert "Holy Guardians" in FALLEN_EMPIRE_TYPES
        assert "Enigmatic Observers" in FALLEN_EMPIRE_TYPES
        assert "Keepers of Knowledge" in FALLEN_EMPIRE_TYPES
        assert "Militant Isolationists" in FALLEN_EMPIRE_TYPES
        assert "Ancient Caretakers" in FALLEN_EMPIRE_TYPES

    def test_has_required_fields(self) -> None:
        for name, fe in FALLEN_EMPIRE_TYPES.items():
            assert "ethic" in fe, f"{name} missing ethic"
            assert "fleet_power" in fe, f"{name} missing fleet_power"
            assert "counter" in fe, f"{name} missing counter"

    def test_meta_notes_exist(self) -> None:
        assert len(FALLEN_EMPIRE_META) >= 4


class TestRelics:

    def test_has_key_relics(self) -> None:
        assert "Galatron" in RELICS
        assert "Contingency Core" in RELICS
        assert "Prethoryn Brood-Queen" in RELICS

    def test_relics_have_required_fields(self) -> None:
        for name, relic in RELICS.items():
            assert "passive" in relic, f"{name} missing passive"
            assert "triumph" in relic, f"{name} missing triumph"
            assert "source" in relic, f"{name} missing source"

    def test_relic_count(self) -> None:
        assert len(RELICS) >= 10


class TestLeaderTraits:

    def test_has_all_classes(self) -> None:
        classes = {t["class"] for t in LEADER_TRAITS.values()}
        assert "scientist" in classes
        assert "commander" in classes
        assert "official" in classes

    def test_has_negative_traits(self) -> None:
        negatives = [n for n, t in LEADER_TRAITS.items() if "dismiss" in t.get("meta", "") or "avoid" in t.get("meta", "") or "replace" in t.get("meta", "")]
        assert len(negatives) >= 2

    def test_trait_count(self) -> None:
        assert len(LEADER_TRAITS) >= 18


class TestPlanetBuildings:

    def test_has_key_buildings(self) -> None:
        assert "Research Lab" in PLANET_BUILDINGS
        assert "Alloy Foundry" in PLANET_BUILDINGS
        assert "Robot Assembly Plant" in PLANET_BUILDINGS
        assert "Fortress" in PLANET_BUILDINGS

    def test_has_capital_chain(self) -> None:
        assert "Planetary Administration" in PLANET_BUILDINGS
        assert "Planetary Capital" in PLANET_BUILDINGS
        assert "System Capital-Complex" in PLANET_BUILDINGS

    def test_building_count(self) -> None:
        assert len(PLANET_BUILDINGS) >= 18

    def test_district_types(self) -> None:
        assert "City" in DISTRICT_TYPES
        assert "Industrial" in DISTRICT_TYPES
        assert "Generator" in DISTRICT_TYPES
        assert "Mining" in DISTRICT_TYPES
        assert len(DISTRICT_TYPES) >= 7

    def test_build_meta_exists(self) -> None:
        assert len(PLANET_BUILD_META) >= 5


class TestSituations:

    def test_has_key_situations(self) -> None:
        assert "food_shortage" in SITUATIONS
        assert "energy_shortage" in SITUATIONS
        assert "crime_wave" in SITUATIONS
        assert "low_stability" in SITUATIONS

    def test_situations_have_fix_actions(self) -> None:
        for name, sit in SITUATIONS.items():
            assert "fix" in sit, f"{name} missing fix"
            assert "severity" in sit, f"{name} missing severity"

    def test_situation_count(self) -> None:
        assert len(SITUATIONS) >= 7
