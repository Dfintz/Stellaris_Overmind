"""
Ruleset Generator — Stellaris 4.3.4 LLM AI Overhaul

Builds a composite ruleset from an empire's ethics, civics, traits, origin,
and government type.  The output is a structured dict consumed by the
Decision Engine and the Validator.

Ruleset hierarchy (highest → lowest priority):
  1. Origin Overrides
  2. Ethics Base
  3. Civic Modifiers
  4. Trait Micro-Modifiers
  5. Patch Meta (game-phase + fleet + weapon)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

GAME_VERSION = "4.3.4"

ALLOWED_ACTIONS: list[str] = [
    "EXPAND",
    "BUILD_FLEET",
    "IMPROVE_ECONOMY",
    "FOCUS_TECH",
    "DIPLOMACY",
    "ESPIONAGE",
    "PREPARE_WAR",
    "DEFEND",
    "CONSOLIDATE",
    "COLONIZE",
    "BUILD_STARBASE",
]


# ======================================================================== #
# Game‑Phase Enum
# ======================================================================== #

class GamePhase(Enum):
    EARLY = "early"    # years 0–40
    MID = "mid"        # years 40–120
    LATE = "late"      # years 120+


def _phase_from_year(year: int) -> GamePhase:
    if year < 2240:
        return GamePhase.EARLY
    if year < 2320:
        return GamePhase.MID
    return GamePhase.LATE


# Public alias for cross-module use
phase_from_year = _phase_from_year


# ======================================================================== #
# Ethics → Base Priorities
# ======================================================================== #

ETHICS_BASE: dict[str, dict] = {
    # --- Militarist ---
    "Militarist": {
        "war_frequency": "high",
        "fleet_budget_share": 0.40,
        "diplomacy_tendency": "aggressive",
        "risk_tolerance": 0.7,
        "claim_cost_mult": -0.10,
        "fire_rate_mult": 0.10,
    },
    "Fanatic Militarist": {
        "war_frequency": "very_high",
        "fleet_budget_share": 0.55,
        "diplomacy_tendency": "hostile",
        "risk_tolerance": 0.85,
        "claim_cost_mult": -0.20,
        "fire_rate_mult": 0.20,
    },
    # --- Pacifist ---
    "Pacifist": {
        "war_frequency": "low",
        "fleet_budget_share": 0.20,
        "diplomacy_tendency": "peaceful",
        "risk_tolerance": 0.3,
        "empire_size_pops_mult": -0.10,
        "stability_add": 5,
    },
    "Fanatic Pacifist": {
        "war_frequency": "very_low",
        "fleet_budget_share": 0.10,
        "diplomacy_tendency": "diplomatic",
        "risk_tolerance": 0.15,
        "empire_size_pops_mult": -0.20,
        "stability_add": 10,
    },
    # --- Xenophile ---
    "Xenophile": {
        "diplomacy_tendency": "friendly",
        "federation_interest": 0.8,
        "trade_focus": 0.6,
        "trade_job_produces_mult": 0.10,
        "envoys_add": 1,
    },
    "Fanatic Xenophile": {
        "diplomacy_tendency": "federation_builder",
        "federation_interest": 1.0,
        "trade_focus": 0.8,
        "trade_job_produces_mult": 0.20,
        "envoys_add": 2,
    },
    # --- Xenophobe ---
    "Xenophobe": {
        "diplomacy_tendency": "isolationist",
        "expansion_drive": 0.8,
        "closed_borders_preference": True,
        "starbase_influence_cost_mult": -0.20,
        "founder_species_growth_mult": 0.10,
    },
    "Fanatic Xenophobe": {
        "diplomacy_tendency": "supremacist",
        "expansion_drive": 1.0,
        "closed_borders_preference": True,
        "starbase_influence_cost_mult": -0.40,
        "founder_species_growth_mult": 0.20,
    },
    # --- Egalitarian (4.3: specialist bonus → job efficiency) ---
    "Egalitarian": {
        "economic_style": "consumer_balanced",
        "faction_management": "priority",
        "living_standards": "decent_conditions",
        "specialist_job_efficiency": 0.05,
        "faction_output_mult": 0.15,
    },
    "Fanatic Egalitarian": {
        "economic_style": "consumer_balanced",
        "faction_management": "high_priority",
        "living_standards": "utopian_abundance",
        "specialist_job_efficiency": 0.10,
        "faction_output_mult": 0.30,
    },
    # --- Authoritarian (4.3: worker bonus → job efficiency) ---
    "Authoritarian": {
        "economic_style": "alloy_focused",
        "living_standards": "stratified",
        "stability_focus": 0.7,
        "worker_job_efficiency": 0.10,
        "influence_produces_add": 0.5,
    },
    "Fanatic Authoritarian": {
        "economic_style": "alloy_focused",
        "living_standards": "stratified",
        "stability_focus": 0.9,
        "worker_job_efficiency": 0.20,
        "influence_produces_add": 1.0,
    },
    # --- Materialist ---
    "Materialist": {
        "tech_focus": 0.8,
        "robot_usage": "encouraged",
        "research_speed_mult": 0.05,
        "robot_upkeep_mult": -0.10,
    },
    "Fanatic Materialist": {
        "tech_focus": 1.0,
        "robot_usage": "mandatory",
        "research_speed_mult": 0.10,
        "robot_upkeep_mult": -0.20,
    },
    # --- Spiritualist ---
    "Spiritualist": {
        "unity_focus": 0.7,
        "robot_usage": "discouraged",
        "temple_building": True,
        "unity_produces_mult": 0.10,
        "edict_cost_mult": -0.10,
    },
    "Fanatic Spiritualist": {
        "unity_focus": 1.0,
        "robot_usage": "forbidden",
        "temple_building": True,
        "unity_produces_mult": 0.20,
        "edict_cost_mult": -0.20,
    },
    # --- Gestalt ---
    "Gestalt Consciousness": {
        "personality_type": "unified_voice",
        "diplomacy_tendency": "variable",
    },
}


# ======================================================================== #
# Civics → Modifiers (all meta‑relevant civics from META_4.3.4.md)
# ======================================================================== #

CIVIC_MODIFIERS: dict[str, dict] = {
    # --- S-Tier ---
    "Technocracy": {
        "research_priority": "high",
        "science_director_weight": 0.3,
        "scientist_cap_add": 1,
        "official_cap_add": -1,
        "research_alternatives_add": 1,
    },
    "Masterful Crafters": {
        "engineering_research_bonus": True,
        "trade_value_focus": "moderate",
        "consumer_goods_efficiency": 0.1,
    },
    "Distinguished Admiralty": {
        "fleet_cap_usage": "maximize",
        "command_limit_mult": 0.20,
        "fire_rate_mult": 0.10,
        "commander_upkeep_mult": -0.25,
        "commander_initial_skill": 2,
    },
    "Citizen Service": {
        "naval_cap_mult": 0.15,
        "soldier_unity_add": 2,
        "fleet_cap_bonus": True,
    },
    # --- Strong ---
    "Slaver Guilds": {
        "slave_specialist_bonus": True,
        "unity_from_slaves": True,
        "research_from_slaves": True,
    },
    "Byzantine Bureaucracy": {
        "bureaucrat_unity_add": 1,
        "bureaucrat_stability_add": 1,
    },
    "Corvée System": {
        "resettlement_cost": "free",
        "worker_produces_mult": 0.10,
        "resettlement_unemployed_mult": 0.15,
    },
    "Worker Cooperative": {
        "employee_ownership": True,
        "executive_swap": "stewards",
        "trade_scaling": True,
    },
    "Idealistic Foundation": {
        "citizen_happiness": 0.10,
        "refugee_attraction": 0.10,
    },
    # --- Other meta civics ---
    "Merchant Guilds": {
        "trade_value_focus": "high",
        "commercial_zones": True,
    },
    "Beacon of Liberty": {
        "unity_from_factions": True,
        "egalitarian_attraction": 0.3,
    },
    "Meritocracy": {
        "leader_experience": 0.1,
        "specialist_output": 0.1,
    },
    "Barbaric Despoilers": {
        "war_type": "raiding_only",
        "diplomacy_tendency": "hostile",
    },
    "Inward Perfection": {
        "diplomacy_blocked": True,
        "unity_bonus": 0.2,
        "growth_bonus": 0.1,
    },
    "Reanimators": {
        "soldier_swap": "necromancers",
        "undead_armies": True,
        "soldier_bonus_workforce_mult": 0.10,
    },
    "Planet Forgers": {
        "volcanic_world_start": True,
        "volcanic_max_districts_add": 3,
        "volcanic_habitability": 0.20,
    },
    "Augmentation Bazaars": {
        "ascension_lock": "cybernetic",
        "universal_augmentations": True,
        "augmentor_trade_add": 4,
    },
    "Aristocratic Elite": {
        "elite_job_efficiency": 0.10,
        "leader_upkeep_mult": 0.10,
    },
    "Police State": {
        "enforcer_job_efficiency": 0.10,
    },
    # --- Genocidal ---
    "Fanatic Purifiers": {
        "genocidal": True,
        "fire_rate_mult": 0.33,
        "army_damage_mult": 0.33,
        "naval_cap_mult": 0.33,
        "ship_cost_mult": -0.15,
        "no_diplomacy": True,
        "requires": "Fanatic Xenophobe + Militarist/Spiritualist",
    },
    "Devouring Swarm": {
        "genocidal": True,
        "hull_mult": 0.25,
        "army_damage_mult": 0.40,
        "naval_cap_mult": 0.33,
        "ship_cost_mult": -0.25,
        "no_diplomacy": True,
        "requires": "Hive Mind",
    },
    "Determined Exterminator": {
        "genocidal": True,
        "fire_rate_mult": 0.25,
        "army_damage_mult": 0.25,
        "naval_cap_mult": 0.33,
        "ship_cost_mult": -0.15,
        "no_diplomacy": True,
        "requires": "Machine Intelligence",
    },
    # --- Machine Intelligence ---
    "Rogue Servitor": {
        "bio_trophy_pops": True,
        "unity_from_bio_trophies": True,
        "organic_sanctuary": True,
        "requires": "Machine Intelligence",
    },
    "Driven Assimilator": {
        "assimilation": True,
        "cyborg_assimilation": True,
        "fire_rate_mult": 0.10,
        "requires": "Machine Intelligence",
    },
    # --- Hive Mind ---
    "Empath": {
        "diplomacy_tendency": "cooperative",
        "opinion_bonus": 50,
        "requires": "Hive Mind",
    },
    "Subsumed Will": {
        "pop_growth_speed": 0.10,
        "worker_output_mult": 0.05,
        "requires": "Hive Mind",
    },
    # --- Corporate ---
    "Corporate Authority": {
        "branch_offices": True,
        "commercial_pacts": True,
        "no_rivals": True,
    },
    "Gospel of the Masses": {
        "trade_value_from_unity": True,
        "spiritualist_ethics_attraction": 0.50,
        "requires": "Corporate + Spiritualist",
    },
    "Indentured Assets": {
        "slave_specialist_bonus": True,
        "slave_trade": True,
        "requires": "Corporate + Authoritarian",
    },
    "Criminal Heritage": {
        "criminal_branch_offices": True,
        "crime_lord_deal": True,
        "no_commercial_pacts": True,
        "requires": "Corporate",
    },
    "Private Prospectors": {
        "mining_station_output": 0.10,
        "asteroid_mining": True,
        "requires": "Corporate",
    },
    "Free Traders": {
        "trade_value_mult": 0.10,
        "branch_office_value": 0.10,
        "requires": "Corporate",
    },
    # --- Standard civics ---
    "Philosopher King": {
        "ruler_experience_gain": 0.20,
        "ruler_initial_skill": 1,
        "edict_fund_add": 50,
    },
    "Exalted Priesthood": {
        "high_priest_unity": True,
        "edict_fund_add": 50,
        "requires": "Spiritualist + not Egalitarian",
    },
    "Free Haven": {
        "pop_growth_from_immigration": 0.15,
        "refugee_pop_growth": 0.30,
        "requires": "Xenophile",
    },
    "Nationalistic Zeal": {
        "claim_cost_mult": -0.10,
        "war_exhaustion_mult": -0.10,
        "requires": "Militarist",
    },
    "Mining Guilds": {
        "miner_minerals_add": 1,
    },
    "Agrarian Idyll": {
        "housing_from_farms": True,
        "farmer_amenities_add": 2,
        "requires": "Pacifist + not Corporate",
    },
    "Functional Architecture": {
        "building_upkeep_mult": -0.10,
        "district_upkeep_mult": -0.10,
    },
    "Shadow Council": {
        "election_influence_cost_mult": -0.75,
        "ruler_skill_levels": 1,
    },
    "Parliamentary System": {
        "faction_influence_mult": 0.40,
        "requires": "Democratic authority",
    },
    "Diplomatic Corps": {
        "envoy_add": 2,
        "trust_growth_mult": 0.20,
        "requires": "not Fanatic Xenophobe/Purifiers",
    },
    "Death Cult": {
        "mortal_initiate_jobs": True,
        "sacrifice_pop_bonuses": True,
        "requires": "Spiritualist + not Pacifist",
    },
    "Memorialist": {
        "memorial_building": True,
        "unity_from_memorials": True,
    },
    "Catalytic Processing": {
        "alloy_from_food": True,
        "no_mineral_alloys": True,
    },
    "Pleasure Seekers": {
        "entertainer_efficiency": 0.20,
        "pop_happiness": 0.05,
        "requires": "not Spiritualist/Militarist",
    },
    "Media Conglomerate": {
        "war_exhaustion_mult": -0.05,
        "edict_fund_add": 25,
    },
    "Shared Burdens": {
        "stratified_economy_penalty": "none",
        "living_standard_forced": "shared_burden",
        "requires": "Fanatic Egalitarian",
    },
    "Techno-Organicist": {
        "cyborg_assimilation": True,
        "organic_pop_assembly": True,
        "requires": "Hive Mind",
    },
    "Individual Machine Replication": {
        "pop_assembly_speed": 0.10,
        "mechanical_pop_growth": True,
        "requires": "Machine Intelligence",
    },
}


# ======================================================================== #
# Traits → Micro‑Modifiers (meta‑relevant from META_4.3.4.md)
# ======================================================================== #

TRAIT_MICRO: dict[str, dict] = {
    # --- Positive ---
    "Intelligent": {"researcher_job_efficiency": 0.10},
    "Thrifty": {"trader_job_efficiency": 0.25},
    "Rapid Breeders": {"logistic_growth_mult": 0.10},
    "Traditional": {"bureaucrat_job_efficiency": 0.10},
    "Strong": {"army_damage": 0.05, "miner_job_efficiency": 0.025, "soldier_job_efficiency": 0.05},
    "Very Strong": {"army_damage": 0.10, "miner_job_efficiency": 0.05, "soldier_job_efficiency": 0.10},
    "Ingenious": {"technician_job_efficiency": 0.15},
    "Industrious": {"miner_job_efficiency": 0.15},
    "Natural Engineers": {"engineering_research": 0.05},
    "Natural Physicists": {"physics_research": 0.05},
    "Natural Sociologists": {"society_research": 0.05},
    "Resilient": {"defense_army_hp": 0.5},
    "Unbreakable Resolve": {"stability_per_100_pops": 0.2, "stability_cap": 15},
    "Familial": {"happiness_per_100_pops": 0.001, "happiness_cap": 0.20},
    # --- Negative ---
    "Deviants": {"governing_ethics_attraction": -0.15},
    "Unruly": {"empire_size_mult": 0.10},
    "Quarrelsome": {"bureaucrat_job_efficiency": -0.10},
    "Wasteful": {"consumer_goods_upkeep_mult": 0.10},
    "Brittle": {"amenities_usage_add": 0.5},
    "Psychological Infertility": {"logistic_growth_war_penalty": -0.30},
    "Weak": {"army_damage": -0.05, "soldier_job_efficiency": -0.05},
    # --- Cyborg ---
    "Trading Algorithms": {"trader_job_efficiency": 0.25},
    "Universal Augmentations": {"auto_modding": True},
    # --- Overtuned ---
    "Overtuned": {"triple_stacking_vocational": True},
    # --- Machine ---
    "Rapid Replicators": {"robot_assembly_speed": 0.15},
    "Mass Produced": {"robot_assembly_speed": 0.10, "robot_cost_mult": -0.10},
    # --- Additional Positive ---
    "Adaptive": {"habitability_add": 0.10},
    "Extremely Adaptive": {"habitability_add": 0.20},
    "Communal": {"housing_usage_mult": -0.10},
    "Nomadic": {"resettle_speed_mult": 0.25, "pop_growth_from_immigration": 0.15},
    "Quick Learners": {"leader_experience_gain": 0.25},
    "Charismatic": {"amenities_from_jobs": 0.20},
    "Enduring": {"leader_age_add": 20},
    "Venerable": {"leader_age_add": 50},
    "Conservational": {"pop_food_upkeep_mult": -0.10},
    "Fertile": {"pop_growth_speed": 0.10},
    "Docile": {"empire_size_from_pops_mult": -0.10},
    "Robust": {"leader_age_add": 10, "pop_food_upkeep_mult": -0.05},
    # --- Additional Negative ---
    "Slow Learners": {"leader_experience_gain": -0.25},
    "Repugnant": {"amenities_from_jobs": -0.20},
    "Sedentary": {"resettlement_cost_mult": 0.25, "pop_growth_from_immigration": -0.15},
    "Solitary": {"housing_usage_mult": 0.10},
    "Nonadaptive": {"habitability_add": -0.10},
    "Fleeting": {"leader_age_add": -10},
    "Decadent": {"worker_happiness": -0.10},
    # --- Lithoid ---
    "Lithoid": {"food_to_minerals": True, "habitability_add": 0.50, "pop_growth_speed": -0.25},
    "Scintillating Skin": {"rare_crystals_from_miners": True},
    "Gaseous Byproducts": {"exotic_gases_from_miners": True},
    "Volatile Excretions": {"volatile_motes_from_miners": True},
}


# ======================================================================== #
# Origins → Overrides (all meta origins from META_4.3.4.md)
# ======================================================================== #

ORIGIN_OVERRIDES: dict[str, dict] = {
    # --- Tier S ---
    "Cybernetic Creed": {
        "ascension_lock": "cybernetic",
        "worker_stacking": True,
        "toil_faction": True,
        "creed_worker_buff": 0.40,
        "imperial_creed_bonus": 0.10,
        "labored_masses_edict": 0.20,
        "meta_tier": "S",
        "meta_strategy": "worker_stacking",
    },
    "Under One Rule": {
        "ruler_centric": True,
        "luminary_leader": True,
        "synth_awareness_bonus": 0.25,
        "pop_assembly_bonus": 1,
        "meta_tier": "S",
        "meta_strategy": "synthetic_ascension_snowball",
    },
    "Void Dwellers": {
        "colonization_rules": "habitats_only",
        "planet_habitability": "ignore",
        "habitat_construction": "priority",
        "habitat_specializations": ["rare_crystal", "exotic_gas", "volatile_mote"],
        "meta_tier": "S",
        "meta_strategy": "virtual_ascension_rush",
    },
    # --- Tier A ---
    "Synthetic Fertility": {
        "pop_growth_logic": "synth_assembly",
        "robot_usage": "mandatory",
        "computing_research_speed": 0.15,
        "pop_dieoff_halved": True,
        "meta_tier": "A",
        "meta_strategy": "robot_pop_scaling",
    },
    "Necrophage": {
        "pop_growth_logic": "necrophage_conversion",
        "chambers_block_necrophage_growth": True,
        "necrophyte_boosts_secondary_growth": True,
        "war_frequency": "moderate_for_pops",
        "purge_type": "necrophage",
        "meta_tier": "A",
        "meta_strategy": "pop_snowball",
    },
    "Endbringers": {
        "ascension_lock": "psionic",
        "stability_penalty": True,
        "crisis_origin": True,
        "ascension_speed": "accelerated",
        "meta_tier": "A",
        "meta_strategy": "psionic_crisis_rush",
    },
    "Rogue Servitor": {
        "biotrophies": True,
        "unity_stability_loop": True,
        "meta_tier": "A",
        "meta_strategy": "unity_alloy_loop",
    },
    "Teachers of the Shroud": {
        "psionic_start": True,
        "unity_stacking": True,
        "meta_tier": "A",
        "meta_strategy": "psionic_ascension",
    },
    "Clone Army": {
        "pop_growth_cap": True,
        "early_pop_burst": True,
        "meta_tier": "A",
        "meta_strategy": "early_unity_rush",
    },
    "Shroud-Forged": {
        "psionic_pops": True,
        "meta_tier": "A",
        "meta_strategy": "psionic_economy",
    },
    # --- Tier B ---
    "Doomsday": {
        "homeworld_destruction": True,
        "forced_early_conquest": True,
        "meta_tier": "B",
        "meta_strategy": "early_conquest",
    },
    "Ocean Paradise": {
        "tall_build": True,
        "food_to_trade_scaling": True,
        "meta_tier": "B",
        "meta_strategy": "tall_trade",
    },
    "Subterranean": {
        "extra_mining_housing": True,
        "urbanization_zone": True,
        "meta_tier": "B",
        "meta_strategy": "underground_economy",
    },
    "Knights of the Toxic God": {
        "knight_order": True,
        "quest_chain": True,
        "politician_swap": "knightly_order",
        "meta_tier": "B",
        "meta_strategy": "trade_megacorp",
    },
    # --- Standard ---
    "Prosperous Unification": {
        "meta_tier": "C",
        "meta_strategy": "standard",
    },
    "Shattered Ring": {
        "early_research": "boosted",
        "colonization_rules": "delayed",
        "ringworld_restoration": "priority",
        "meta_tier": "B",
        "meta_strategy": "tall_research",
    },
    "Life-Seeded": {
        "homeworld_size": 25,
        "colonization_rules": "gaia_only_early",
        "terraforming": "priority_mid",
        "meta_tier": "C",
    },
    "Scion": {
        "fallen_empire_patron": True,
        "diplomacy_constraints": "patron_aligned",
        "early_fleet": "gifted",
        "meta_tier": "C",
    },
    "Machine Intelligence": {
        "pop_growth_logic": "assembly_only",
        "food_irrelevant": True,
        "personality_type": "logic_modules",
    },
    "Hive Mind": {
        "pop_growth_logic": "hive_spawning",
        "personality_type": "unified_voice",
        "consumer_goods_irrelevant": True,
    },
    # --- Missing origins (P2) ---
    "Hegemon": {
        "start_federation": "hegemony",
        "early_subjects": 2,
        "meta_tier": "B",
        "meta_strategy": "early_dominance",
    },
    "Common Ground": {
        "start_federation": "galactic_union",
        "early_allies": 2,
        "meta_tier": "B",
        "meta_strategy": "federation_play",
    },
    "Remnants": {
        "ruined_ecumenopolis": True,
        "restoration_chain": True,
        "meta_tier": "B",
        "meta_strategy": "ecumenopolis_restoration",
    },
    "Galactic Doorstep": {
        "gateway_start": True,
        "early_gateway_tech": True,
        "meta_tier": "C",
        "meta_strategy": "standard",
    },
    "Tree of Life": {
        "food_bonus": True,
        "homeworld_growth_bonus": 0.15,
        "requires": "Hive Mind",
        "meta_tier": "B",
        "meta_strategy": "hive_growth",
    },
    "Progenitor Hive": {
        "queen_mechanic": True,
        "offspring_bonuses": True,
        "requires": "Hive Mind",
        "meta_tier": "A",
        "meta_strategy": "hive_queen_economy",
    },
    "Lost Colony": {
        "parent_empire": True,
        "colonist_bonuses": True,
        "meta_tier": "C",
        "meta_strategy": "standard",
    },
    "Broken Shackles": {
        "diverse_species": True,
        "refugee_pops": True,
        "meta_tier": "B",
        "meta_strategy": "pop_diversity",
    },
    "Payback": {
        "pre_ftl_start": True,
        "advanced_ship_tech": True,
        "meta_tier": "B",
        "meta_strategy": "early_fleet_advantage",
    },
    "Fear of the Dark": {
        "sensor_penalty": True,
        "first_contact_bonus": True,
        "meta_tier": "C",
        "meta_strategy": "standard",
    },
    "Imperial Fiefdom": {
        "start_as_subject": True,
        "overlord_protection": True,
        "independence_chain": True,
        "meta_tier": "C",
        "meta_strategy": "liberation_play",
    },
    "Overtuned": {
        "triple_trait_stacking": True,
        "vocational_traits": True,
        "meta_tier": "A",
        "meta_strategy": "trait_stacking",
    },
    "Resource Consolidation": {
        "machine_world_start": True,
        "requires": "Machine Intelligence",
        "meta_tier": "B",
        "meta_strategy": "machine_world_economy",
    },
    "Survivor": {
        "post_apocalyptic": True,
        "tomb_world_habitability": 0.70,
        "meta_tier": "C",
        "meta_strategy": "tomb_world",
    },
    "On the Shoulders of Giants": {
        "archaeology_chain": True,
        "minor_artifacts": True,
        "meta_tier": "C",
        "meta_strategy": "standard",
    },
    "Calamitous Birth": {
        "lithoid_meteor": True,
        "colonization_speed": "fast",
        "requires": "Lithoid",
        "meta_tier": "C",
        "meta_strategy": "fast_expansion",
    },
}


# ======================================================================== #
# Fleet Composition Meta (from META_4.3.4.md §4)
# ======================================================================== #

@dataclass
class WeaponLoadout:
    """A tested weapon combination with its meta verdict."""
    name: str
    slot_config: str
    verdict: str
    notes: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "slot_config": self.slot_config,
            "verdict": self.verdict,
            "notes": self.notes,
        }


@dataclass
class FleetTemplate:
    """A phase-appropriate fleet composition recommendation."""
    phase: GamePhase
    composition: dict[str, int]  # ship_type -> ratio (out of 100)
    weapons: list[WeaponLoadout]
    notes: str

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "composition": self.composition,
            "weapons": [w.to_dict() for w in self.weapons],
            "notes": self.notes,
        }


WEAPON_META: list[WeaponLoadout] = [
    WeaponLoadout(
        name="Autocannon + Plasma",
        slot_config="S: autocannon, M: plasma",
        verdict="SWARM_META",
        notes="~23 days to kill a corvette. Best for corvette/destroyer builds.",
    ),
    WeaponLoadout(
        name="Kinetic Artillery + Neutron Launchers",
        slot_config="L: kinetic_artillery + neutron",
        verdict="CRUISER_META",
        notes="Best mid-game cruiser loadout.",
    ),
    WeaponLoadout(
        name="Tachyon Lance + Kinetic Artillery",
        slot_config="X: tachyon_lance, L: kinetic_artillery",
        verdict="LONG_RANGE_BATTLESHIP_META",
        notes="Best artillery battleship. Long-range dominance.",
    ),
    WeaponLoadout(
        name="Giga Cannon + Plasma",
        slot_config="X: giga_cannon, L: plasma",
        verdict="CLOSE_RANGE_BATTLESHIP_META",
        notes="Best brawler battleship.",
    ),
    WeaponLoadout(
        name="Titan Perdition Beam",
        slot_config="T: perdition_beam",
        verdict="META_DEFINING",
        notes="500 dmg, 40 range, AoE. Punishes massed small fleets.",
    ),
    WeaponLoadout(
        name="Disruptors",
        slot_config="S/M: disruptors",
        verdict="DEAD",
        notes="~300 days to kill a corvette. Armor/shield hardening kills bypass. DO NOT USE.",
    ),
]

FLEET_TEMPLATES: list[FleetTemplate] = [
    FleetTemplate(
        phase=GamePhase.EARLY,
        composition={"corvette": 80, "destroyer": 20},
        weapons=[WEAPON_META[0]],  # autocannon + plasma
        notes="Fill 50 naval cap. Corvettes with autocannon+plasma. Add destroyers for PD.",
    ),
    FleetTemplate(
        phase=GamePhase.MID,
        composition={"cruiser": 50, "destroyer": 20, "corvette": 30},
        weapons=[WEAPON_META[1], WEAPON_META[0]],
        notes="Cruisers with kinetic artillery + neutron. Corvette screen with autocannon+plasma.",
    ),
    FleetTemplate(
        phase=GamePhase.LATE,
        composition={"battleship": 60, "titan": 5, "cruiser": 20, "destroyer": 15},
        weapons=[WEAPON_META[2], WEAPON_META[3], WEAPON_META[4]],
        notes="Battleship artillery core + titan for AoE. Split fleets to avoid enemy titan AoE.",
    ),
]

CRISIS_COUNTERS: dict[str, dict] = {
    "Unbidden": {
        "loadout": "armor_heavy_plasma",
        "fleet_style": "battleship_artillery",
        "notes": "They bypass shields. Stack armor + plasma.",
    },
    "Contingency": {
        "loadout": "kinetic_artillery",
        "fleet_style": "long_range_battleship",
        "notes": "They are armor-heavy. Kinetic + artillery.",
    },
    "Prethoryn Scourge": {
        "loadout": "high_evasion_autocannons",
        "fleet_style": "corvette_destroyer_swarm",
        "notes": "Swarm tactics. High evasion + autocannons.",
    },
}


# ======================================================================== #
# Game-Phase Economy Priorities
# ======================================================================== #

PHASE_PRIORITIES: dict[GamePhase, dict] = {
    GamePhase.EARLY: {
        "economy_focus": "minerals_first",
        "alloy_priority": "high",
        "consumer_goods_priority": "low",
        "expansion_style": "chokepoints_first",
        "fleet_target": "fill_naval_cap",
        "colony_limit": 3,
        "research_priority": "moderate",
        "unity_priority": "moderate",
        "notes": "Minerals > everything. Never stop building. Specialize planets.",
    },
    GamePhase.MID: {
        "economy_focus": "alloy_megafactories",
        "alloy_priority": "very_high",
        "consumer_goods_priority": "moderate",
        "expansion_style": "strategic",
        "fleet_target": "naval_superiority",
        "research_priority": "high",
        "unity_priority": "high",
        "notes": "District specializations. Automation buildings. Planetary ascension.",
    },
    GamePhase.LATE: {
        "economy_focus": "megastructures",
        "alloy_priority": "maximum",
        "consumer_goods_priority": "moderate",
        "expansion_style": "consolidate",
        "fleet_target": "crisis_ready",
        "research_priority": "repeatables",
        "unity_priority": "maximum",
        "notes": "Repeatables (+20 naval cap). Dyson Sphere + Matter Decompressor. Crisis prep by 2350.",
    },
}


# ======================================================================== #
# Naval Cap Constants (4.3)
# ======================================================================== #

NAVAL_CAP_USAGE: dict[str, int] = {
    "corvette": 5,
    "frigate": 8,
    "destroyer": 10,
    "cruiser": 20,
    "battleship": 40,
    "titan": 80,
    "juggernaut": 100,
    "colossus": 100,
}

BASE_NAVAL_CAP = 50
ANCHORAGE_NAVAL_CAP = 5
LOGISTICS_OFFICE_BONUS = 3
REPEATABLE_NAVAL_CAP = 20


# ======================================================================== #
# Intelligence & Espionage System (from wiki Intelligence page)
# ======================================================================== #

# Intel categories and what each level reveals
INTEL_CATEGORIES: dict[str, dict[str, list[str]]] = {
    "government": {
        "low": ["authority", "ethics", "capital_location", "ruler"],
        "medium": ["civics", "origin", "owned_relics", "governors"],
        "high": ["empire_size"],
        "full": [],
    },
    "diplomacy": {
        "low": ["casus_belli", "relative_power", "rivalries", "federation_names"],
        "medium": ["opinion_breakdown", "diplomatic_pacts", "galcom_vote_rationale"],
        "high": ["specialist_tier"],
        "full": ["secret_diplomatic_pacts"],
    },
    "economy": {
        "low": ["owned_inhabited_systems", "relative_economic_power"],
        "medium": ["owned_systems", "colony_count", "colony_locations", "colony_planet_class"],
        "high": ["planet_details", "districts", "population", "civilian_orders"],
        "full": ["surveyed_celestial_objects"],
    },
    "technology": {
        "low": ["relative_tech_power", "researched_tech_count"],
        "medium": [],
        "high": [],
        "full": [],
    },
    "military": {
        "low": ["casus_belli", "relative_fleet_power", "starbase_locations", "invasion_plans"],
        "medium": ["ship_details"],
        "high": ["military_fleet_locations"],
        "full": ["military_fleet_orders", "cloaked_fleets"],
    },
}

# Intel cap from diplomatic pacts
INTEL_CAP_FROM_PACTS: dict[str, int] = {
    "first_contact": 10,
    "commercial_pact": 20,
    "guarantee_independence": 20,
    "non_aggression_pact": 20,
    "galactic_community": 30,
    "migration_treaty": 30,
    "research_agreement": 30,
    "overlord_as_subject": 30,
    "subject_as_overlord": 40,
    "defensive_pact": 40,
    "federation_associate": 40,
    "hegemony_federation": 40,
    "martial_alliance": 50,
    "research_cooperative": 50,
    "trade_league": 50,
    "galactic_union": 60,
    "galactic_imperium_member": 65,
    "embassy_bonus": 20,  # added to any existing pact cap
}

# Spy network configuration
SPY_NETWORK_CONFIG: dict = {
    "base_max_infiltration": 50,
    "base_growth_per_day": 1,
    "growth_per_empire_size_400": 1,
    "decay_rate_per_month": 1,  # when envoy removed or over max
    "infiltration_formula": "5 + 5 * current_level",  # points needed per level
}


@dataclass
class EspionageOperation:
    """An espionage operation the AI can recommend."""
    name: str
    category: str          # subterfuge, manipulation, sabotage, provocation
    intel_category: str    # government, diplomacy, economy, technology, military
    min_infiltration: int  # minimum spy network level
    influence_cost: int
    energy_upkeep: int
    infiltration_cost: int  # spy network points consumed
    difficulty: int
    effect: str
    requires_dlc: str = ""
    blocked_by: str = ""    # e.g. "gestalt_consciousness", "enigmatic_engineering"


ESPIONAGE_OPERATIONS: list[EspionageOperation] = [
    # --- Subterfuge ---
    EspionageOperation(
        name="Gather Information",
        category="subterfuge", intel_category="subterfuge",
        min_infiltration=10, influence_cost=20, energy_upkeep=4,
        infiltration_cost=5, difficulty=4,
        effect="+5 max infiltration for 10 years (stacks to +20). Random intel report.",
    ),
    EspionageOperation(
        name="Prepare Sleeper Cells",
        category="subterfuge", intel_category="government",
        min_infiltration=30, influence_cost=45, energy_upkeep=6,
        infiltration_cost=0, difficulty=6,
        effect="+1 operation skill, no spy network decay for 15 years.",
        requires_dlc="Nemesis",
    ),
    EspionageOperation(
        name="Acquire Asset",
        category="subterfuge", intel_category="government",
        min_infiltration=30, influence_cost=45, energy_upkeep=6,
        infiltration_cost=15, difficulty=5,
        effect="Gain a random asset (+4 skill bonus, +5 max infiltration).",
        requires_dlc="Nemesis",
    ),
    EspionageOperation(
        name="Steal Technology",
        category="subterfuge", intel_category="technology",
        min_infiltration=40, influence_cost=80, energy_upkeep=8,
        infiltration_cost=20, difficulty=8,
        effect="+30% research progress in a random technology.",
        blocked_by="enigmatic_engineering",
        requires_dlc="Nemesis",
    ),
    # --- Manipulation ---
    EspionageOperation(
        name="Spark Diplomatic Incident",
        category="manipulation", intel_category="diplomacy",
        min_infiltration=25, influence_cost=30, energy_upkeep=5,
        infiltration_cost=10, difficulty=5,
        effect="Target suffers a diplomatic event or envoy event.",
        blocked_by="gestalt_consciousness",
        requires_dlc="Nemesis",
    ),
    EspionageOperation(
        name="Extort Favors",
        category="manipulation", intel_category="diplomacy",
        min_infiltration=35, influence_cost=60, energy_upkeep=7,
        infiltration_cost=20, difficulty=6,
        effect="80% chance +1 favor, 20% chance +2 favors from target.",
        requires_dlc="Nemesis",
    ),
    EspionageOperation(
        name="Smear Campaign",
        category="manipulation", intel_category="diplomacy",
        min_infiltration=35, influence_cost=60, energy_upkeep=7,
        infiltration_cost=20, difficulty=7,
        effect="Target federation loses -20 cohesion, or -100 opinion with random empire.",
        requires_dlc="Nemesis",
    ),
    # --- Sabotage ---
    EspionageOperation(
        name="Sabotage Starbase",
        category="sabotage", intel_category="military",
        min_infiltration=45, influence_cost=100, energy_upkeep=9,
        infiltration_cost=30, difficulty=9,
        effect="Destroy a random non-shipyard module or building on target starbase.",
        requires_dlc="Nemesis",
    ),
    # --- Provocation ---
    EspionageOperation(
        name="Arm Privateers",
        category="provocation", intel_category="economy",
        min_infiltration=60, influence_cost=180, energy_upkeep=12,
        infiltration_cost=60, difficulty=10,
        effect="A scaling pirate fleet attacks one of the target's systems.",
        requires_dlc="Nemesis",
    ),
    EspionageOperation(
        name="Crisis Beacon",
        category="provocation", intel_category="technology",
        min_infiltration=80, influence_cost=320, energy_upkeep=16,
        infiltration_cost=80, difficulty=12,
        effect="The nearest crisis fleet attacks the target's closest system.",
        requires_dlc="Nemesis",
    ),
]

# Codebreaking and Encryption sources
CODEBREAKING_SOURCES: dict[str, int] = {
    "tech_encryption_1": 1,     # Encryption tech tier 1
    "tech_encryption_2": 1,     # tier 2
    "tech_encryption_3": 1,     # tier 3
    "subterfuge_tradition_adopt": 1,  # Subterfuge adoption
    "subterfuge_tradition_finish": 1,  # Subterfuge finisher
    "psionic_theory_tech": 1,
    "telepathy_tech": 1,
}

ENCRYPTION_SOURCES: dict[str, int] = {
    "tech_decryption_1": 1,
    "tech_decryption_2": 1,
    "tech_decryption_3": 1,
    "subterfuge_tradition_adopt": 1,
    "subterfuge_tradition_finish": 1,
    "psionic_theory_tech": 1,
    "telepathy_tech": 1,
}

# Espionage-relevant civics
ESPIONAGE_CIVICS: dict[str, dict] = {
    "Criminal Heritage": {
        "spy_network_growth_mult": 0.20,
        "espionage_focus": True,
    },
    "Shadow Council": {
        "election_manipulation": True,
        "spy_network_growth_mult": 0.10,
    },
}

# Espionage-relevant traditions (Subterfuge tree)
SUBTERFUGE_TRADITIONS: dict[str, str] = {
    "adopt": "espionage_operation_cost_mult: -25%, intel_decryption_add: +1",
    "Shadow Recruits": "spy_network_growth_mult: +50%",
    "Operational Security": "operation_difficulty: -2",
    "Double Agents": "max_infiltration_add: +10",
    "Non-Disclosure Agreement": "enemy_operation_difficulty: +1",
    "Cell Structure": "spy_network_decay_mult: -50%",
    "finish": "successful_operations_refund_half_infiltration, ascension_perk_slot: +1",
}

# Phase-appropriate espionage priorities
ESPIONAGE_PHASE_PRIORITIES: dict[str, dict] = {
    "early": {
        "priority": "low",
        "recommended_action": "assign_envoy_to_spy_network_on_hostile_neighbor",
        "notes": "Build spy networks early for intel. Gather Information is cheap.",
    },
    "mid": {
        "priority": "moderate",
        "recommended_action": "steal_technology_from_tech_leader",
        "notes": "Steal Technology for +30% research. Acquire Assets for future ops.",
    },
    "late": {
        "priority": "high_if_at_war",
        "recommended_action": "sabotage_or_crisis_beacon",
        "notes": "Arm Privateers to harass. Crisis Beacon as ultimate weapon.",
    },
}


def get_espionage_operations(min_infiltration: int = 0) -> list[dict]:
    """Return all operations available at a given infiltration level."""
    return [
        {
            "name": op.name,
            "category": op.category,
            "min_infiltration": op.min_infiltration,
            "influence_cost": op.influence_cost,
            "difficulty": op.difficulty,
            "effect": op.effect,
        }
        for op in ESPIONAGE_OPERATIONS
        if op.min_infiltration <= min_infiltration or min_infiltration == 0
    ]


def get_espionage_phase_priority(year: int) -> dict:
    """Return espionage priorities for the current game phase."""
    phase = _phase_from_year(year)
    return ESPIONAGE_PHASE_PRIORITIES.get(phase.value, ESPIONAGE_PHASE_PRIORITIES["early"])


# ======================================================================== #
# Public API
# ======================================================================== #

def _normalize_key(raw: str, prefix: str) -> str:
    """Convert Clausewitz IDs like ``ethic_fanatic_militarist`` to display
    names like ``Fanatic Militarist`` that match the lookup tables.

    Also handles already-normalized names (passes them through unchanged).
    """
    if raw in ("", None):
        return raw or ""
    # If it already matches a known format (starts uppercase), return as-is
    if raw[0].isupper():
        return raw
    # Strip prefix (e.g. "ethic_", "civic_", "trait_", "origin_")
    name = raw
    if name.startswith(prefix):
        name = name[len(prefix):]
    # Convert underscores to spaces and title-case
    return name.replace("_", " ").title()


def generate_ruleset(
    ethics: list[str],
    civics: list[str],
    traits: list[str],
    origin: str,
    government: str,
) -> dict:
    """Build a composite ruleset dict for one empire.

    Layers are applied in order; higher-priority layers overwrite lower.
    """
    ruleset: dict = {
        "version": GAME_VERSION,
        "base": {},
        "modifiers": {},
        "micro_modifiers": {},
        "overrides": {},
        "government": government,
        "meta_tier": "C",
        "meta_strategy": "standard",
    }

    # Layer 1 – ethics base
    for ethic in ethics:
        key = _normalize_key(ethic, "ethic_")
        if key in ETHICS_BASE:
            ruleset["base"].update(ETHICS_BASE[key])

    # Layer 2 – civic modifiers
    for civic in civics:
        key = _normalize_key(civic, "civic_")
        if key in CIVIC_MODIFIERS:
            ruleset["modifiers"].update(CIVIC_MODIFIERS[key])

    # Layer 3 – trait micro‑modifiers
    for trait in traits:
        key = _normalize_key(trait, "trait_")
        if key in TRAIT_MICRO:
            ruleset["micro_modifiers"].update(TRAIT_MICRO[key])

    # Layer 4 – origin overrides (highest priority)
    origin_key = _normalize_key(origin, "origin_")
    if origin_key in ORIGIN_OVERRIDES:
        overrides = ORIGIN_OVERRIDES[origin_key]
        ruleset["overrides"] = overrides
        # Promote meta info to top level
        if "meta_tier" in overrides:
            ruleset["meta_tier"] = overrides["meta_tier"]
        if "meta_strategy" in overrides:
            ruleset["meta_strategy"] = overrides["meta_strategy"]

    # Resolve conflicts: flatten all layers with correct priority order.
    # Lowest priority first → highest last (each .update() overwrites).
    # Traits (5) < Civics (4) < Ethics (3) < Origin (1)
    resolved: dict = {}
    resolved.update(ruleset["micro_modifiers"])  # traits — lowest
    resolved.update(ruleset["modifiers"])         # civics
    resolved.update(ruleset["base"])              # ethics
    resolved.update(ruleset["overrides"])         # origin — highest
    ruleset["resolved"] = resolved

    return ruleset


def get_phase_priorities(year: int) -> dict:
    """Return economy/military priorities for the current game phase."""
    phase = _phase_from_year(year)
    return {"phase": phase.value, **PHASE_PRIORITIES[phase]}


def get_fleet_template(year: int) -> FleetTemplate:
    """Return the recommended fleet composition for the current game phase."""
    phase = _phase_from_year(year)
    for tmpl in FLEET_TEMPLATES:
        if tmpl.phase == phase:
            return tmpl
    return FLEET_TEMPLATES[-1]


def get_crisis_counter(crisis_type: str) -> dict | None:
    """Return the recommended counter loadout for a specific crisis."""
    return CRISIS_COUNTERS.get(crisis_type)


def get_weapon_meta() -> list[dict]:
    """Return all tested weapon verdicts as dicts."""
    return [
        {
            "name": w.name,
            "slot_config": w.slot_config,
            "verdict": w.verdict,
            "notes": w.notes,
        }
        for w in WEAPON_META
    ]
