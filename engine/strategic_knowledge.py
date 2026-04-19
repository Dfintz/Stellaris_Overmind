"""
Strategic Knowledge — Stellaris 4.3.4 game systems reference.

This module provides structured strategic knowledge about game systems
that the LLM needs to make informed decisions.  Unlike ruleset_generator.py
(which models the empire's configuration), this module models the game's
mechanics that apply to ALL empires.

Covers: Traditions, Ascension Perks, Megastructures, Policies, Edicts,
        Designations, War Goals, Federation Types, Galactic Community.

The data here is used by the decision engine to enrich LLM prompts with
context-appropriate strategic guidance.
"""

from __future__ import annotations

from dataclasses import dataclass
from engine.ruleset_generator import GamePhase, _phase_from_year


# ======================================================================== #
# Tradition Trees
# ======================================================================== #

TRADITION_TREES: dict[str, dict] = {
    "Adaptability": {
        "focus": "planet_efficiency",
        "adopt": "-10% pop housing usage",
        "finish": "designation bonuses enhanced",
        "key_traditions": ["Adaptive Ecology (+1 max districts)", "Appropriation (-50% resettle cost, +25% auto-resettle)"],
        "gestalt_variant": "Versatility",
        "blocked_by": [],
        "meta_priority": "mid",
    },
    "Harmony": {
        "focus": "stability_unity",
        "adopt": "-10% pop upkeep",
        "finish": "+25% planetary ascension effect",
        "key_traditions": ["Utopian Dream (+3 stability)", "Harmonious Directives (+50 edict fund)"],
        "gestalt_variant": "Synchronicity",
        "blocked_by": [],
        "meta_priority": "early_to_mid",
    },
    "Commerce": {
        "focus": "trade_value",
        "adopt": "-20% trader upkeep",
        "finish": "+10% monthly trade, unlocks Trade League federation",
        "key_traditions": ["Trickle Up Economics (+15% trade from living standards)", "Insider Trading (-10% market fee)"],
        "gestalt_variant": "Logistics",
        "blocked_by": [],
        "meta_priority": "early_for_trade_builds",
    },
    "Diplomacy": {
        "focus": "federations_envoys",
        "adopt": "-50% diplomatic influence cost, unlocks Diplomatic Grants edict",
        "finish": "+2 monthly federation XP, +10% diplo weight, +1 official",
        "key_traditions": ["The Federation (+1 envoy, +1 fed cohesion)", "Eminent Diplomats (+5 diplo acceptance)"],
        "blocked_by": ["Inward Perfection", "Devouring Swarm", "Endbringers"],
        "meta_priority": "mid_for_diplomats",
    },
    "Discovery": {
        "focus": "research_exploration",
        "adopt": "+20% anomaly research speed, unlocks Map the Stars edict",
        "finish": "+10% research speed, unlocks Research Cooperative federation",
        "key_traditions": ["Science Division (+1 research alternatives, +1 scientist cap)", "Faith in Science (-20% researcher upkeep)"],
        "blocked_by": [],
        "meta_priority": "early_always",
    },
    "Domination": {
        "focus": "worker_output_empire_management",
        "adopt": "+5% worker output, +5% slave efficiency",
        "finish": "-5% empire size from pops, unlocks Hegemony federation",
        "key_traditions": ["Workplace Motivators (+5% worker output, unlocks Extended Shifts edict)", "Imperious Architecture (housing+jobs from capitals)"],
        "blocked_by": [],
        "meta_priority": "early_for_authoritarian",
    },
    "Expansion": {
        "focus": "territory_colonization",
        "adopt": "+25% colony dev speed, -20% habitat upkeep",
        "finish": "+1 max districts on non-artificial planets",
        "key_traditions": ["A New Life (+10% pop growth/assembly)", "Courier Network (-15% empire size from systems/planets)"],
        "blocked_by": [],
        "meta_priority": "early_for_wide",
    },
    "Prosperity": {
        "focus": "economy_infrastructure",
        "adopt": "+20% mining station output",
        "finish": "+25% resources from orbital stations",
        "key_traditions": ["Standard Construction Templates (-10% cost, +25% build speed)", "The Pursuit of Profit (+5% resources from jobs)"],
        "blocked_by": [],
        "meta_priority": "early_always",
    },
    "Supremacy": {
        "focus": "fleet_military",
        "adopt": "+20 naval capacity, +20% army damage",
        "finish": "unlocks War Doctrine policies, Supremacist diplomatic stance",
        "key_traditions": ["Fleet Logistics Corps (-10% ship upkeep, +20% naval cap)", "Overwhelming Force (+20% bombardment, +10% fire rate)"],
        "blocked_by": [],
        "meta_priority": "mid_for_militarist",
    },
    "Fortification": {
        "focus": "defense_starbases",
        "adopt": "+2 starbase capacity, +50% starbase upgrade speed",
        "finish": "+50% defense platform cap, -20% starbase upkeep, unlocks Eternal Vigilance AP",
        "key_traditions": ["Defensive Zeal (+33% starbase damage/health)", "Never Surrender (-25% war exhaustion)"],
        "blocked_by": [],
        "requires_dlc": "Apocalypse or Overlord",
        "meta_priority": "situational_defensive",
    },
    "Subterfuge": {
        "focus": "espionage_intel",
        "adopt": "+1 codebreaking, x5 cloaking tech chance",
        "finish": "50% infiltration refund on successful ops, +1 cloaking strength",
        "key_traditions": ["Shadow Recruits (+50% infiltration speed)", "Double Agents (+1 envoy, +10 max infiltration)"],
        "blocked_by": [],
        "requires_dlc": "Nemesis",
        "meta_priority": "mid_for_espionage",
    },
    "Aptitude": {
        "focus": "leaders",
        "adopt": "+1 leader trait option",
        "finish": "+1 leader starting traits",
        "key_traditions": ["Specialist Training (+2% specialist job eff per governor level)", "Champions of the Empire (+1 effective leader skill)"],
        "requires_dlc": "Galactic Paragons",
        "meta_priority": "early_to_mid",
    },
    "Statecraft": {
        "focus": "council_agendas",
        "adopt": "+50 edict fund",
        "finish": "-5% empire size",
        "key_traditions": ["Constitutional Focus (+25% agenda speed)", "Shared Benefits (+1 effective councilor skill)"],
        "requires_dlc": "Galactic Paragons",
        "meta_priority": "early_to_mid",
    },
    "Enmity": {
        "focus": "rival_bonuses",
        "adopt": "+3% pop growth per neighboring rival",
        "finish": "+1 envoy, unlocks Antagonistic stance",
        "key_traditions": ["Match (bonuses when rival is stronger)", "Outpace (+15% damage to rivals)"],
        "requires_dlc": "Humanoids",
        "blocked_by": ["Genocidal", "Inward Perfection", "Driven Assimilator"],
        "meta_priority": "situational_aggressive",
    },
    "Politics": {
        "focus": "galactic_community",
        "adopt": "+1 envoy",
        "finish": "+10% diplo weight, unlocks Politics resolutions",
        "key_traditions": ["Gravitas (-25% resolution cost, +2.5% diplo weight per official level)", "Extraordinary Powers (-25% veto/emergency cooldown)"],
        "requires_dlc": "Federations",
        "blocked_by": ["Genocidal"],
        "meta_priority": "mid_for_galcom",
    },
    "Archivism": {
        "focus": "specimens_archaeology",
        "adopt": "-50% exhibit unlocking cost, +5% anomaly discovery chance",
        "finish": "+15% specimens output, up to -45% relic activation cost",
        "key_traditions": ["Xeno-Paleontology (+30% scientist XP, +30% archaeology speed)", "Frontier Archaeology (excavate in unowned systems)"],
        "requires_dlc": "Grand Archive",
        "blocked_by": [],
        "meta_priority": "situational_grand_archive",
    },
    "Domestication": {
        "focus": "space_fauna",
        "adopt": "+20% farmer output, -10% space fauna cloning cost",
        "finish": "+50% space fauna XP, unlocks Voidlure starbase building",
        "key_traditions": ["Containment Protocols (+25% vivarium capacity, +20% capture chance)", "Killer Instinct (+15% space fauna damage, +15% speed)"],
        "requires_dlc": "Grand Archive",
        "blocked_by": [],
        "meta_priority": "situational_fauna_builds",
    },
}

# Phase-appropriate tradition recommendations
TRADITION_PHASE_GUIDANCE: dict[str, list[str]] = {
    "early": ["Discovery", "Expansion", "Prosperity", "Domination"],
    "mid": ["Supremacy", "Subterfuge", "Diplomacy", "Commerce"],
    "late": ["Fortification", "Harmony", "Adaptability"],
}


# ======================================================================== #
# Ascension Perks
# ======================================================================== #

ASCENSION_PERKS: dict[str, dict] = {
    # --- Tier 0 (no prerequisites) ---
    "Technological Ascendancy": {"tier": 0, "effect": "+50% rare tech chance, unlocks Research Focus policies", "meta": "S-tier for tech builds"},
    "Executive Vigor": {"tier": 0, "effect": "+100 edict fund, +15% agenda speed", "meta": "strong early pick"},
    "Interstellar Dominion": {"tier": 0, "effect": "-20% claim/starbase influence cost, -25% empire size from systems", "meta": "strong for expansion"},
    "One Vision": {"tier": 0, "effect": "+10% unity, +50% governing ethics attraction", "meta": "strong for stability"},
    "Mastery of Nature": {"tier": 0, "effect": "-33% blocker cost, Mastery of Nature decision", "meta": "good early if many blockers"},
    "Shared Destiny": {"tier": 0, "effect": "+2 envoys, +1 subjects exempt from divided patronage", "meta": "for overlord builds"},
    "Voidborne": {"tier": 0, "effect": "-20% habitat cost, +2 habitat max districts, +50% habitat jobs", "meta": "essential for Void Dwellers"},
    "Galactic Wonders": {"tier": 0, "effect": "unlocks Ring World, Dyson Sphere, Matter Decompressor", "meta": "S-tier late game"},
    "Eternal Vigilance": {"tier": 0, "effect": "+25% starbase damage/hull, +20% home territory fire rate", "meta": "strong defensive"},
    "Nihilistic Acquisition": {"tier": 0, "effect": "unlocks Raiding bombardment stance", "meta": "for pop-stealing builds"},
    "Enigmatic Engineering": {"tier": 0, "effect": "+2 encryption, blocks enemy Steal Technology ops", "meta": "strong if ahead in tech"},
    "Transcendent Learning": {"tier": 0, "effect": "+2 scientist cap, +25% leader XP, -15% leader upkeep", "meta": "decent early"},
    "Imperial Prerogative": {"tier": 0, "effect": "-25% empire size from planets, +2 official capacity", "meta": "strong for wide, blocked for Corporate"},
    "Consecrated Worlds": {"tier": 0, "effect": "Consecrate World decision (massive planet bonuses)", "meta": "strong for Spiritualist", "requires": "Spiritualist"},
    "Universal Transactions": {"tier": 0, "effect": "+1 official cap, -15% branch office cost, free commercial pacts", "meta": "essential for Megacorp", "requires": "Corporate, not Criminal Heritage"},
    "Lord of War": {"tier": 0, "effect": "+1 enclave capacity, +25% diplo weight from fleet power", "meta": "for mercenary builds", "requires": "Individualist or Tactical Algorithms"},
    "Mechromancy": {"tier": 0, "effect": "+15% L/XL/T weapon damage, resurrect organic guardians", "meta": "for Machine Intelligence", "requires": "Machine Intelligence"},
    "Archaeo-Engineers": {"tier": 0, "effect": "+1 scientist cap, +33% archaeotech damage, +25% specimens output", "meta": "strong with Ancient Relics", "requires": "Archaeostudies tech"},
    "Xeno-Compatibility": {"tier": 0, "effect": "+20% pop growth with 2+ species, +100% refugee attraction", "meta": "pop growth powerhouse", "requires": "Xenophile"},
    "Hydrocentric": {"tier": 0, "effect": "-25% ocean terraforming cost, Expand Planetary Sea, Deluge colossus", "meta": "essential for Aquatic builds", "requires": "Aquatic founder species"},
    "Detox": {"tier": 0, "effect": "can terraform Toxic worlds", "meta": "situational", "requires": "Climate Restoration tech"},
    # --- Tier 1 ---
    "Grasp the Void": {"tier": 1, "effect": "+5 starbase capacity", "meta": "good for wide empires"},
    "World Shaper": {"tier": 1, "effect": "-25% terraforming cost, Gaia terraforming option", "meta": "good for tall"},
    "Galactic Weather Control": {"tier": 1, "effect": "science ships can create cosmic storms", "meta": "situational", "requires": "Advanced Storm Manipulation tech, Cosmic Storms DLC"},
    # --- Tier 2 (ascension paths) ---
    "Synthetic Evolution": {"tier": 2, "effect": "unlocks Synthetics traditions, synthetic ascension", "meta": "S-tier for UOR builds"},
    "The Flesh is Weak": {"tier": 2, "effect": "unlocks Cybernetics traditions, cybernetic ascension", "meta": "S-tier for Cybernetic Creed"},
    "Mind Over Matter": {"tier": 2, "effect": "unlocks Psionics traditions, psionic ascension", "meta": "S-tier for psionic builds"},
    "Biomorphosis": {"tier": 2, "effect": "unlocks Genetics/Cloning/Mutation/Purity traditions", "meta": "S-tier for biological"},
    "Synthetic Age": {"tier": 2, "effect": "unlocks Modularity/Nanotech/Virtuality traditions for machines", "meta": "S-tier for Machine Intelligence", "requires": "Machine founder species"},
    "Interdimensional Processing": {"tier": 2, "effect": "unlocks Psionics traditions for machines", "meta": "unique machine psionic path", "requires": "Machine founder species, Shadows of the Shroud DLC"},
    "Galactic Force Projection": {"tier": 2, "effect": "+1 commander, +20% fleet command limit, +150 naval cap", "meta": "S-tier for military"},
    "Master Builders": {"tier": 2, "effect": "+50% megastructure build speed, +1 megastructure build capacity", "meta": "S-tier with Galactic Wonders"},
    "Arcology Project": {"tier": 2, "effect": "unlocks Ecumenopolis decision", "meta": "strong for tall builds"},
    "Hive Worlds": {"tier": 2, "effect": "Hive World terraforming option (max districts, unique bonuses)", "meta": "essential for Hive Mind tall", "requires": "Hive Mind"},
    "Machine Worlds": {"tier": 2, "effect": "Machine World terraforming option (double resource district output)", "meta": "essential for Machine Intelligence tall", "requires": "Machine Intelligence"},
    # --- Tier 3 ---
    "Defender of the Galaxy": {"tier": 3, "effect": "+50% damage vs crisis, +200 opinion from all empires", "meta": "essential for crisis prep"},
    "Galactic Contender": {"tier": 3, "effect": "+20% diplo weight, +33% damage vs fallen/awakened empires", "meta": "strong mid-late"},
    "Colossus Project": {"tier": 3, "effect": "unlocks Colossus ship, -5% ship upkeep, -15% war exhaustion", "meta": "strong for total war"},
    # --- Tier 3 (crisis paths) ---
    "Galactic Nemesis": {"tier": 3, "effect": "unlocks Menace, Galactic Nemesis crisis progression", "meta": "player crisis path", "requires": "not Xenophile/Pacifist, Nemesis DLC"},
    "Cosmogenesis": {"tier": 3, "effect": "unlocks Advanced Logic, Cosmogenesis crisis progression", "meta": "machine crisis path", "requires": "The Machine Age DLC"},
    "Behemoth Fury": {"tier": 3, "effect": "unlocks Feral Insight, Behemoth Fury crisis progression", "meta": "biological crisis path", "requires": "Biological shipset, BioGenesis DLC"},
    "Galactic Hyperthermia": {"tier": 3, "effect": "unlocks Crystallized Entropy, Galactic Hyperthermia crisis progression", "meta": "infernal crisis path", "requires": "Infernals DLC"},
}


# ======================================================================== #
# Megastructures
# ======================================================================== #

MEGASTRUCTURES: dict[str, dict] = {
    "Dyson Sphere": {
        "type": "multi_stage",
        "stages": 5,
        "total_cost_alloys": 50000,
        "total_time_years": 55,
        "final_output": "+4000 energy",
        "location": "single star system, no binary/trinary, no pulsars/neutrons/black holes",
        "requires": "Galactic Wonders AP + Dyson Sphere tech",
        "meta_priority": "high_late_game",
        "notes": "Colonized planets in system become frozen on completion. Top priority for energy economy.",
    },
    "Matter Decompressor": {
        "type": "multi_stage",
        "stages": 4,
        "total_cost_alloys": 62500,
        "total_time_years": 45,
        "final_output": "+2000 minerals",
        "location": "black hole only",
        "requires": "Galactic Wonders AP + Matter Decompressor tech",
        "meta_priority": "high_late_game",
        "notes": "Must be built around black hole. Essential for mineral-to-alloy conversion scaling.",
    },
    "Science Nexus": {
        "type": "multi_stage",
        "stages": 3,
        "total_cost_alloys": 50000,
        "total_time_years": 35,
        "final_output": "+300 research (all), +15% research speed",
        "requires": "Mega-Engineering tech",
        "meta_priority": "high_if_research_focused",
    },
    "Ring World": {
        "type": "multi_stage",
        "stages": 5,
        "total_cost_alloys": 55000,
        "total_time_years": 58,
        "final_output": "4 habitable segments (100% habitability, 10 districts each)",
        "location": "no black holes, no binary, no existing habitable planets",
        "requires": "Galactic Wonders AP + Ring World tech",
        "meta_priority": "high_for_pop_capacity",
    },
    "Strategic Coordination Center": {
        "type": "multi_stage",
        "stages": 3,
        "total_cost_alloys": 55000,
        "total_time_years": 35,
        "final_output": "+300 naval cap, +6 starbase cap, +12 defense platforms, +15% sublight speed",
        "requires": "Mega-Engineering tech",
        "meta_priority": "high_for_military",
    },
    "Mega Shipyard": {
        "type": "multi_stage",
        "stages": 3,
        "total_cost_alloys": 33000,
        "total_time_years": 20,
        "final_output": "+20 shipyard capacity, +100% empire ship build speed, can build titans/colossi",
        "requires": "Mega-Engineering tech",
        "requires_dlc": "Federations",
        "meta_priority": "high_for_fleet_buildup",
    },
    "Sentry Array": {
        "type": "multi_stage",
        "stages": 4,
        "total_cost_alloys": 45000,
        "total_time_years": 25,
        "final_output": "galaxy-wide sensor range, +40 base intel, +2 codebreaking",
        "requires": "Mega-Engineering tech",
        "meta_priority": "medium_good_for_intel",
    },
    "Gateway": {
        "type": "ftl",
        "cost_alloys": 5000,
        "cost_influence": 75,
        "time_years": 8,
        "effect": "instant travel between all connected gateways",
        "requires": "Gateway Construction tech",
        "meta_priority": "high_mid_to_late",
    },
    "Habitat": {
        "type": "colonizable",
        "cost_alloys": 1500,
        "cost_influence": 200,
        "time_years": 5,
        "effect": "colonizable station orbiting planet/star",
        "requires": "Orbital Habitats tech",
        "meta_priority": "essential_for_void_dwellers",
    },
    "Orbital Ring": {
        "type": "upgrade",
        "tiers": 3,
        "effect": "additional starbase-like station around colonized planet with modules and buildings",
        "requires": "Orbital Rings tech",
        "requires_dlc": "Overlord",
        "meta_priority": "high_for_planetary_output",
    },
    "Mega Art Installation": {
        "type": "multi_stage",
        "stages": 4,
        "total_cost_alloys": 50000,
        "total_time_years": 35,
        "final_output": "+400 unity, +20% amenities, -20% planetary ascension cost",
        "requires": "Mega-Engineering tech",
        "requires_dlc": "MegaCorp",
        "meta_priority": "medium_unity_builds",
    },
    "Interstellar Assembly": {
        "type": "multi_stage",
        "stages": 4,
        "total_cost_alloys": 45000,
        "total_time_years": 25,
        "final_output": "+40% diplomatic weight, +150 opinion, +2 envoys, -10% empire size",
        "requires": "Mega-Engineering tech",
        "requires_dlc": "MegaCorp",
        "meta_priority": "high_for_diplomacy_builds",
    },
    "Hyper Relay": {
        "type": "ftl",
        "cost_alloys": 500,
        "cost_influence": 25,
        "cost_rare_crystals": 100,
        "time_years": 1,
        "effect": "fast travel between connected relay systems, skips sublight traversal",
        "requires": "Hyper Relays tech",
        "requires_dlc": "Overlord",
        "meta_priority": "high_for_fleet_mobility",
    },
    "Deep Space Citadel": {
        "type": "defensive",
        "tiers": 3,
        "effect": "large defensive station with starbase buildings and defense platforms",
        "requires": "Deep Space Citadel tech",
        "requires_dlc": "BioGenesis",
        "meta_priority": "situational_defensive",
    },
    "Arc Furnace": {
        "type": "multi_stage",
        "stages": 4,
        "final_output": "+100% mining station output in system, +2 minerals/+2 alloys per celestial body",
        "location": "molten worlds only",
        "requires": "Arc Furnace tech",
        "requires_dlc": "The Machine Age",
        "meta_priority": "high_for_mineral_scaling",
        "notes": "Arc Welders origin starts with one. Build limit increased by Mega-Engineering.",
    },
    "Quantum Catapult": {
        "type": "multi_stage",
        "stages": 3,
        "total_cost_alloys": 20000,
        "total_time_years": 15,
        "final_output": "catapult fleets across galaxy, +33% fire rate for 120 days on arrival",
        "location": "pulsars and neutron stars only",
        "requires": "Quantum Catapult tech",
        "requires_dlc": "Overlord",
        "meta_priority": "situational_offensive",
    },
    "Aetherophasic Engine": {
        "type": "crisis",
        "stages": 5,
        "effect": "Galactic Nemesis crisis progression megastructure, destroys galaxy on completion",
        "requires": "Galactic Nemesis crisis level 5",
        "requires_dlc": "Nemesis",
        "meta_priority": "crisis_only",
    },
    "Synaptic Lathe": {
        "type": "crisis",
        "effect": "Cosmogenesis crisis megastructure, has pops/stability/districts, produces resources from Neural Chip jobs",
        "requires": "Cosmogenesis AP + Scalable Reservoir Computing tech",
        "requires_dlc": "The Machine Age",
        "meta_priority": "crisis_only",
    },
    "Grand Archive": {
        "type": "single_stage",
        "cost_alloys": 1000,
        "effect": "enables specimen exhibits, +50 vivarium capacity",
        "requires": "Galactic Archivism tech, 2500+ pops",
        "requires_dlc": "Grand Archive",
        "meta_priority": "situational_grand_archive",
    },
    "Behemoth Egg": {
        "type": "crisis",
        "cost_food": 50000,
        "cost_influence": 300,
        "time_years": 10,
        "effect": "hatches into Behemoth class I/II/III biological warship",
        "requires": "Behemoth Fury AP + crisis level 2",
        "requires_dlc": "BioGenesis",
        "meta_priority": "crisis_only",
    },
    "Shroud Seal": {
        "type": "defensive",
        "cost_alloys": 500,
        "cost_zro": 100,
        "time_years": 3,
        "effect": "reduces psionic aura intensity by 10/day in system, -50% psionic weapon fire rate",
        "requires": "Psionic Suppression tech",
        "requires_dlc": "Shadows of the Shroud",
        "meta_priority": "situational_anti_psionic",
    },
    "Galactic Crucible": {
        "type": "crisis",
        "stages": 4,
        "final_output": "+375 naval cap (Hub path) or +350 alloys (Institute path)",
        "requires": "Galactic Hyperthermia AP",
        "requires_dlc": "Infernals",
        "meta_priority": "crisis_only",
    },
}


# ======================================================================== #
# War Goals & Diplomacy
# ======================================================================== #

WAR_GOALS: dict[str, dict] = {
    "Conquer": {"type": "offensive", "effect": "claim enemy systems", "cost": "influence for claims"},
    "Subjugation": {"type": "offensive", "effect": "make target a vassal", "requires": "not Fanatic Xenophobe or Genocidal"},
    "Ideology": {"type": "offensive", "effect": "force ethics shift", "requires": "Liberation Wars policy"},
    "Humiliation": {"type": "offensive", "effect": "-33% rival influence, +100 influence", "cost": "no claims needed"},
    "Colossus": {"type": "total_war", "effect": "total war, use Colossus weapons", "requires": "Colossus Project AP"},
    "Containment": {"type": "defensive", "effect": "status quo, force vassalization of nearby systems"},
    "Animosity": {"type": "offensive", "effect": "humiliate rival empire", "requires": "Enmity traditions"},
    "Purification": {"type": "total_war", "effect": "total war — purge all pops", "requires": "Fanatic Purifiers"},
    "Absorption": {"type": "total_war", "effect": "total war — devour all pops", "requires": "Devouring Swarm"},
    "Extermination": {"type": "total_war", "effect": "total war — exterminate organics", "requires": "Determined Exterminator"},
    "Assimilation": {"type": "total_war", "effect": "total war — assimilate into cyborgs", "requires": "Driven Assimilator"},
    "Expel Corporations": {"type": "offensive", "effect": "close enemy branch offices", "requires": "target is Megacorp"},
    "End Threat": {"type": "offensive", "effect": "total war against crisis empire", "requires": "Galactic Community resolution"},
    "Independence": {"type": "defensive", "effect": "break free from overlord", "requires": "subject empire"},
}


# ======================================================================== #
# Policies — strategic decisions the AI must actively manage
# ======================================================================== #

POLICIES: dict[str, dict] = {
    "diplomatic_stance": {
        "options": {
            "diplo_stance_belligerent": {"effect": "+10% fire rate, +25% rivalry gain, -50% trust growth", "meta": "war-focused empires"},
            "diplo_stance_cooperative": {"effect": "+25% trust growth, +1 envoy, -50% rivalry gain", "meta": "federation builders"},
            "diplo_stance_expansionist": {"effect": "-20% starbase influence cost, -10% claim cost", "meta": "early game default"},
            "diplo_stance_isolationist": {"effect": "+10% admin cap, -50% diplomatic weight", "meta": "tall builds"},
            "diplo_stance_mercantile": {"effect": "+10% trade value, +1 envoy", "meta": "trade empires"},
            "diplo_stance_supremacist": {"effect": "+20% naval cap, -33% trust cap", "meta": "late-game military"},
        },
        "meta_note": "Expansionist early, switch to Supremacist or Cooperative mid-game",
    },
    "war_philosophy": {
        "options": {
            "unrestricted_wars": {"effect": "can declare wars of conquest", "requires": "not Pacifist"},
            "liberation_wars": {"effect": "wars force ethics shift, no conquest", "requires": "not Fanatic Militarist"},
            "no_wars": {"effect": "cannot declare offensive wars", "requires": "Pacifist only"},
        },
        "meta_note": "Unrestricted for conquest empires, Liberation for ideology play",
    },
    "orbital_bombardment": {
        "options": {
            "orbital_bombardment_selective": {"effect": "slow, no collateral, -25% army damage", "meta": "default"},
            "orbital_bombardment_indiscriminate": {"effect": "normal speed, collateral damage", "meta": "fast wars"},
            "orbital_bombardment_armageddon": {"effect": "fastest, max devastation, can destroy pops", "requires": "Genocidal or total war"},
        },
        "meta_note": "Indiscriminate is the best balance of speed vs. preservation",
    },
    "economic_policy": {
        "options": {
            "civilian_economy": {"effect": "+15% CG output, -15% alloy output", "meta": "peaceful build-up"},
            "mixed_economy": {"effect": "no bonuses, balanced", "meta": "default"},
            "militarized_economy": {"effect": "+15% alloy output, -15% CG output, +5% naval cap", "meta": "pre-war/war economy"},
        },
        "meta_note": "Militarized when building fleet or at war, Civilian for stability",
    },
    "trade_policy": {
        "options": {
            "trade_policy_wealth_creation": {"effect": "1 TV = 1 energy", "meta": "default"},
            "trade_policy_consumer_benefits": {"effect": "1 TV = 0.5 energy + 0.25 CG", "meta": "reduces CG needs"},
            "trade_policy_marketplace_of_ideas": {"effect": "1 TV = 0.5 energy + 0.15 unity", "meta": "unity rush builds"},
        },
        "meta_note": "Marketplace of Ideas is meta for unity; Consumer Benefits for CG-hungry empires",
    },
    "first_contact_protocol": {
        "options": {
            "first_contact_proactive": {"effect": "+25% first contact speed, slight diplo penalty", "meta": "early exploration"},
            "first_contact_cautious": {"effect": "default behavior"},
            "first_contact_aggressive": {"effect": "+50% first contact speed, major diplo penalty", "requires": "Militarist or Xenophobe"},
        },
        "meta_note": "Proactive early, switch later. Speed matters for galactic community.",
    },
    "subjugation_war_terms": {
        "options": {
            "benevolent_terms": {"effect": "vassal has more freedom, happier", "meta": "for loyal subjects"},
            "balanced_terms": {"effect": "default terms"},
            "harsh_terms": {"effect": "more extraction, less freedom, unhappy subject", "meta": "resource extraction"},
        },
        "meta_note": "Balanced is safe; Harsh for exploitative overlords",
    },
    "pre_sapients": {
        "options": {
            "pre_sapients_protect": {"effect": "cannot displace, +unity from observation"},
            "pre_sapients_allow": {"effect": "default"},
            "pre_sapients_purge": {"effect": "can purge pre-sapients", "requires": "Xenophobe"},
        },
        "meta_note": "Rarely matters; Allow is default",
    },
    "refugees": {
        "options": {
            "refugees_allowed": {"effect": "all refugees can settle", "meta": "pop growth boost"},
            "refugees_not_allowed": {"effect": "no refugees"},
        },
        "meta_note": "Allow for pop growth, disable if near housing limits",
    },
    "pop_growth_control": {
        "options": {
            "pop_growth_allowed": {"effect": "normal pop growth"},
            "pop_growth_restricted": {"effect": "-75% pop growth, less CG upkeep"},
        },
        "meta_note": "Only restrict if deliberately capping planet size",
    },
}


def get_policy_guidance(
    year: int, ethics: list[str] | None = None,
) -> dict:
    """Return policy recommendations for the current game phase."""
    phase = _phase_from_year(year)
    recommendations: dict[str, str] = {}

    is_militarist = any("militarist" in e for e in (ethics or []))
    is_pacifist = any("pacifist" in e for e in (ethics or []))

    if phase == GamePhase.EARLY:
        recommendations["diplomatic_stance"] = "diplo_stance_expansionist"
        recommendations["trade_policy"] = "trade_policy_marketplace_of_ideas"
        recommendations["economic_policy"] = "mixed_economy"
        recommendations["first_contact_protocol"] = "first_contact_proactive"
    elif phase == GamePhase.MID:
        recommendations["diplomatic_stance"] = (
            "diplo_stance_supremacist" if is_militarist
            else "diplo_stance_cooperative"
        )
        recommendations["trade_policy"] = "trade_policy_marketplace_of_ideas"
        recommendations["economic_policy"] = "militarized_economy"
    else:  # LATE
        recommendations["diplomatic_stance"] = "diplo_stance_supremacist"
        recommendations["economic_policy"] = "militarized_economy"

    if not is_pacifist:
        recommendations["war_philosophy"] = "unrestricted_wars"
    recommendations["orbital_bombardment"] = "orbital_bombardment_indiscriminate"

    return {
        "phase": phase.value,
        "recommended": recommendations,
    }

FEDERATION_TYPES: dict[str, dict] = {
    "Galactic Union": {"focus": "general", "unlock": "Domination traditions", "intel_cap": 60},
    "Trade League": {"focus": "trade", "unlock": "Commerce traditions", "intel_cap": 50, "bonus": "members share trade value"},
    "Martial Alliance": {"focus": "military", "unlock": "Fortification traditions", "intel_cap": 50, "bonus": "joint fleet"},
    "Research Cooperative": {"focus": "research", "unlock": "Discovery traditions", "intel_cap": 50, "bonus": "shared research"},
    "Hegemony": {"focus": "dominance", "unlock": "Domination traditions", "intel_cap": 40, "bonus": "leader controls federation"},
    "Holy Covenant": {"focus": "spiritualist", "unlock": "Harmony traditions", "intel_cap": 50},
}


# ======================================================================== #
# Planetary Designations
# ======================================================================== #

DESIGNATIONS: dict[str, str] = {
    "Generator World": "+energy job efficiency",
    "Mining World": "+mineral job efficiency",
    "Agri-World": "+food job efficiency",
    "Industrial World": "+alloy/CG job efficiency",
    "Tech-World": "+research job efficiency",
    "Unification Center": "+unity job efficiency",
    "Fortress World": "+soldier jobs, +stability, +FTL inhibitor",
    "Trade Station": "+trade from trader jobs",
    "Penal Colony": "+crime reduction, +stability on other planets",
    "Resort World": "+amenities for empire, no jobs",
    "Thrall-World": "+slave output, worker only",
    "Refinery World": "+strategic resource job efficiency",
    "Rural World": "+food from farmer jobs",
    "Bureaucratic Center": "+admin cap from bureaucrats",
    "Foundry World": "+alloy job efficiency only",
    "Factory World": "+CG job efficiency only",
}


# ======================================================================== #
# Edicts — togglable empire bonuses (meta-relevant ones)
# ======================================================================== #

EDICTS: dict[str, dict] = {
    # Unity Fund edicts (togglable, cost unity upkeep)
    "map_the_stars": {
        "effect": "+25% survey speed, +15% anomaly discovery",
        "cost": "unity upkeep",
        "when": "early game, active exploration",
        "meta": "essential early",
    },
    "recycling_campaign": {
        "effect": "+5% minerals output",
        "cost": "unity upkeep",
        "when": "always good if you can afford the unity",
        "meta": "filler edict",
    },
    "capacity_subsidies": {
        "effect": "-10% starbase upkeep",
        "cost": "unity upkeep",
        "when": "when starbase cap is strained",
        "meta": "niche",
    },
    "fleet_supremacy": {
        "effect": "+20% naval capacity",
        "cost": "unity upkeep",
        "when": "pre-war buildup, permanent for military empires",
        "meta": "essential for war",
    },
    "diplomatic_grants": {
        "effect": "+2 envoys",
        "cost": "unity upkeep",
        "when": "federation/diplomacy focus",
        "meta": "good for federation builders",
    },
    "research_subsidies": {
        "effect": "+10% research speed",
        "cost": "unity upkeep",
        "when": "tech rush builds",
        "meta": "high priority for tech focus",
    },
    "extended_shifts": {
        "effect": "+10% minerals, +10% energy, -5% happiness",
        "cost": "unity upkeep",
        "when": "economy crunch, watch stability",
        "meta": "strong but risky",
    },
    "forge_subsidies": {
        "effect": "+10% alloy output",
        "cost": "unity upkeep",
        "when": "pre-war alloy buildup",
        "meta": "essential pre-war",
    },
    "veneration_of_saints": {
        "effect": "+20% unity",
        "cost": "unity upkeep",
        "when": "spiritualist empires",
        "requires": "Spiritualist",
        "meta": "strong for unity rush",
    },
    "hearts_and_minds": {
        "effect": "+10% governing ethics attraction",
        "cost": "unity upkeep",
        "when": "faction management",
        "meta": "niche",
    },
    # Campaign edicts (temporary, influence cost)
    "production_targets": {
        "effect": "+10% minerals, +10% food for 10 years",
        "cost": "influence",
        "when": "economy boost needed",
        "meta": "good for early expansion",
    },
    "land_of_opportunity": {
        "effect": "+25% pop growth for 10 years",
        "cost": "influence",
        "when": "new colonies, pop growth push",
        "meta": "essential early if pop-growing",
    },
    "war_games": {
        "effect": "+15% ship fire rate for 10 years",
        "cost": "influence",
        "when": "before a major war",
        "meta": "strong pre-war",
    },
}


# ======================================================================== #
# Technology Priorities — phase-based guidance for the LLM
# ======================================================================== #

TECH_PRIORITIES: dict[str, dict] = {
    "early": {
        "phase": "early",
        "physics": [
            "tech_shields_1", "tech_combat_computers_1", "tech_lasers_2",
            "tech_sensors_2", "tech_fusion_power",
        ],
        "society": [
            "tech_genome_mapping", "tech_space_trading", "tech_planetary_unification",
            "tech_colonial_centralization", "tech_alien_life_studies",
        ],
        "engineering": [
            "tech_alloys_1", "tech_starbase_2", "tech_destroyers",
            "tech_ship_armor_2", "tech_corvette_hull_1",
        ],
        "meta_notes": [
            "Rush alloy tech (tech_alloys_1) — foundries are critical",
            "Destroyers before cruisers — early fleet comp",
            "Skip food tech if not bio empire",
            "Colonial centralization early for building slots",
        ],
    },
    "mid": {
        "phase": "mid",
        "physics": [
            "tech_shields_3", "tech_lasers_4", "tech_plasma_1",
            "tech_combat_computers_2", "tech_battleships",
        ],
        "society": [
            "tech_galactic_administration", "tech_psionic_theory",
            "tech_gene_tailoring", "tech_ascension_theory",
        ],
        "engineering": [
            "tech_cruisers", "tech_alloys_2", "tech_mega_engineering",
            "tech_autocannons_2", "tech_torpedoes_2",
        ],
        "meta_notes": [
            "Battleships are the mid-game goal",
            "Mega Engineering enables megastructures — critical path",
            "Plasma + Autocannon is meta weapon combo",
            "Ascension theory unlocks ascension perks",
        ],
    },
    "late": {
        "phase": "late",
        "physics": [
            "tech_shields_5", "tech_zero_point_power",
            "tech_tachyon_lance", "tech_matter_decompressor",
        ],
        "society": [
            "tech_synthetic_workers", "tech_synthetic_leaders",
            "tech_telepathy", "tech_psi_jump_drive_1",
        ],
        "engineering": [
            "tech_titans", "tech_juggernaut", "tech_colossus",
            "tech_giga_cannon", "tech_mega_shipyard",
        ],
        "meta_notes": [
            "Titans are meta-defining for AoE beams",
            "Repeatables: focus shields > armor > weapons",
            "Colossus enables Total War CB — game-changing",
            "Juggernaut is a mobile shipyard for sustained wars",
        ],
    },
}


# ======================================================================== #
# Galactic Community — resolutions and council mechanics
# ======================================================================== #

GALACTIC_COMMUNITY: dict[str, dict] = {
    "council": {
        "description": "Top 3 empires by diplo weight sit on council",
        "custodian": "Council member can become Custodian during crisis",
        "imperium": "Custodian can become Galactic Emperor (permanent)",
        "meta": "Being on council gives +diplo weight, influence. Custodian is very strong.",
    },
    "resolution_categories": {
        "Greater Good": {
            "focus": "pacifist/egalitarian",
            "key_resolutions": ["Universal Prosperity Mandate (-CG upkeep)", "Five Year Plans (+worker output)"],
        },
        "Mutual Defense": {
            "focus": "military cooperation",
            "key_resolutions": ["Enemies Abound (+naval cap for all)", "Council Emergency Powers"],
        },
        "Commerce": {
            "focus": "trade/economic",
            "key_resolutions": ["Galactic Commerce (+trade value)", "Market Fee Reduction"],
        },
        "Supremacy": {
            "focus": "militarist",
            "key_resolutions": ["Right of Conquest (legalize wars)", "Fleet Standardization (+fire rate)"],
        },
        "Ecology": {
            "focus": "environmentalist",
            "key_resolutions": ["Protected Worlds", "Industrial Emission Standards"],
        },
        "Galactic Reform": {
            "focus": "politics",
            "key_resolutions": ["Expand Council", "Custodian Declaration", "Galactic Imperium"],
        },
    },
    "meta_notes": [
        "Get on council ASAP — diplo weight matters",
        "Custodian during crisis gives massive fleet cap bonus",
        "Vote against resolutions that hurt your playstyle",
        "Supremacy category is best for militarist empires",
        "Commerce + Greater Good combo is strong for tall play",
    ],
}


# ======================================================================== #
# Starbase Strategy — module and building priorities
# ======================================================================== #

STARBASE_STRATEGY: dict[str, dict] = {
    "early_game": {
        "priority": "shipyard + anchorage",
        "modules": ["shipyard", "anchorage"],
        "buildings": ["crew_quarters"],
        "notes": "1-2 shipyard starbases, rest anchorage for naval cap",
    },
    "mid_game": {
        "priority": "bastion chokepoints + trade hubs",
        "modules": ["gun_battery", "missile_battery", "hangar_bay", "trade_hub"],
        "buildings": ["communications_jammer", "defense_grid", "nebula_refinery"],
        "notes": "Fortify chokepoints, trade hubs in safe core systems",
    },
    "late_game": {
        "priority": "mega shipyard + deep space stations",
        "modules": ["shipyard", "anchorage"],
        "buildings": ["fleet_academy", "titan_yards", "colossus_yards"],
        "notes": "Convert to full shipyard/anchorage, bastions become obsolete",
    },
}


# ======================================================================== #
# Subject / Vassal Types
# ======================================================================== #

SUBJECT_TYPES: dict[str, dict] = {
    "vassal": {"focus": "general", "effect": "pays portion of income, follows overlord in wars"},
    "tributary": {"focus": "economy", "effect": "pays 25% energy+minerals, independent in wars"},
    "subsidiary": {"focus": "megacorp", "effect": "pays 25% energy+minerals, +10% trade value to overlord"},
    "scholarium": {"focus": "research", "effect": "pays research to overlord, gets fleet protection", "dlc": "Overlord"},
    "bulwark": {"focus": "military", "effect": "provides fleet support, gets economic aid", "dlc": "Overlord"},
    "prospectorium": {"focus": "resources", "effect": "pays resources to overlord, gets tech", "dlc": "Overlord"},
}


# ======================================================================== #
# Ship Design Components — defense and utility meta
# ======================================================================== #

SHIP_COMPONENTS: dict[str, dict] = {
    "armor": {
        "types": {
            "durasteel": {"tier": 1, "hp": 25, "meta": "early game default"},
            "ceramo_metal": {"tier": 2, "hp": 50, "meta": "mid-game standard"},
            "plasteel": {"tier": 3, "hp": 75, "meta": "solid choice"},
            "duranium": {"tier": 4, "hp": 100, "meta": "late-game standard"},
            "neutronium": {"tier": 5, "hp": 140, "meta": "best repeatable scaling"},
            "dragonscale": {"tier": 5, "hp": 160, "meta": "rare tech, best armor", "source": "dragon kill"},
        },
        "meta": "Armor beats kinetic weapons. Stack armor vs kinetic-heavy enemies.",
    },
    "shields": {
        "types": {
            "deflectors": {"tier": 1, "hp": 25},
            "improved_deflectors": {"tier": 2, "hp": 50},
            "hyper_shields": {"tier": 3, "hp": 100},
            "advanced_shields": {"tier": 4, "hp": 200},
            "dark_matter_deflectors": {"tier": 5, "hp": 325, "source": "fallen empire"},
            "psionic_shields": {"tier": 5, "hp": 350, "source": "Shroud event"},
        },
        "meta": "Shields beat energy weapons. Shields regen, armor doesn't.",
    },
    "combat_computers": {
        "types": {
            "swarm": {"behavior": "aggressive", "meta": "corvettes/destroyers — close range"},
            "picket": {"behavior": "defensive", "meta": "point defense destroyers"},
            "line": {"behavior": "balanced", "meta": "cruisers/battleships default"},
            "artillery": {"behavior": "long_range", "meta": "battleship artillery — stay at max range"},
        },
        "meta": "Artillery computer on battleships is meta. Swarm on corvettes.",
    },
    "utility": {
        "aux_fire_control": {"effect": "+5% accuracy", "meta": "always good on battleships"},
        "afterburners": {"effect": "+10% sublight speed, +10% evasion", "meta": "corvettes/destroyers"},
        "regenerative_hull": {"effect": "hull regen in combat", "meta": "niche, good for sustained fights"},
        "shield_capacitor": {"effect": "+10% shield HP", "meta": "if stacking shields"},
        "enigmatic_encoder": {"effect": "+20% evasion", "source": "enigmatic fortress", "meta": "very rare, very strong"},
    },
    "auras": {
        "shield_dampener": {"effect": "-20% enemy shields", "meta": "if running energy weapons"},
        "subspace_snare": {"effect": "prevents emergency FTL", "meta": "always good on titans"},
        "inspiring_presence": {"effect": "+10% fire rate for all", "meta": "best titan aura overall"},
        "quantum_destabilizer": {"effect": "-20% enemy fire rate", "meta": "strong defensive aura"},
    },
}

SHIP_DESIGN_META: dict[str, str] = {
    "corvette": "Swarm computer, afterburners, autocannon+plasma or torpedo+autocannon",
    "destroyer": "Picket (PD) or gunship. PD: point defense + flak. Gunship: small weapons",
    "cruiser": "Line computer, hangar section for strike craft OR carrier with fighters",
    "battleship": "Artillery computer, giga cannon + neutron launchers OR tachyon lance + kinetic artillery",
    "titan": "Artillery computer, perdition beam, inspiring presence aura, tank build",
    "juggernaut": "Mobile shipyard, keep behind front lines, repair + rebuild",
    "colossus": "Neutron sweep (kill pops, keep planet) is meta. Global Pacifier for pacifists",
}


# ======================================================================== #
# Fallen & Awakened Empires
# ======================================================================== #

FALLEN_EMPIRE_TYPES: dict[str, dict] = {
    "Holy Guardians": {
        "ethic": "Spiritualist",
        "trigger": "colonize or terraform a Holy World",
        "fleet_power": "~150k-350k",
        "behavior": "Passive until triggered. Declares war if Holy Worlds colonized.",
        "loot": "Psionic tech, Enigmatic tech, Dark Matter",
        "awakened_bonus": "+fleet cap, +fire rate, war on all non-spiritualists",
        "counter": "Do NOT colonize Holy Worlds until ready. Build 200k+ fleet before provoking.",
    },
    "Enigmatic Observers": {
        "ethic": "Xenophile",
        "trigger": "purging pops, genocide",
        "fleet_power": "~150k-350k",
        "behavior": "Gifts tech and resources to weaker empires. Attacks genocidals.",
        "loot": "Enigmatic tech (encoders/decoders), Dark Matter",
        "awakened_bonus": "Protective, vassalizes neighbors",
        "counter": "Stay friendly. Accept gifts. Only fight if awakened and threatening.",
    },
    "Keepers of Knowledge": {
        "ethic": "Materialist",
        "trigger": "researching dangerous tech (AI, Jump Drive, Psi)",
        "fleet_power": "~150k-350k",
        "behavior": "Demands you stop dangerous research. May attack.",
        "loot": "Advanced tech, Dark Matter, Synthetics",
        "awakened_bonus": "Forces tech sharing, vassalizes",
        "counter": "Dangerous tech IS worth it. Delay until you can match them.",
    },
    "Militant Isolationists": {
        "ethic": "Xenophobe",
        "trigger": "border friction, expanding near them",
        "fleet_power": "~150k-350k",
        "behavior": "Demands you close borders. Most aggressive fallen empire.",
        "loot": "Dark Matter tech, advanced weapons",
        "awakened_bonus": "Purges everything, total war",
        "counter": "Expand away from them early. Prepare a massive fleet before contact.",
    },
    "Ancient Caretakers": {
        "ethic": "Machine Intelligence (special)",
        "trigger": "varies — can malfunction",
        "fleet_power": "~150k-350k",
        "behavior": "Dormant. Can awaken as either benevolent or hostile.",
        "loot": "Machine tech, synthetics",
        "awakened_bonus": "Variable based on malfunction outcome",
        "counter": "Unpredictable. Always prepare contingency fleet.",
    },
}

FALLEN_EMPIRE_META: list[str] = [
    "Never fight fallen empires before 2300 — their fleets will crush you.",
    "Dark Matter tech from fallen empires is among the best in the game.",
    "War in Heaven: pick a side or form Non-Aligned League for +diplo weight.",
    "Awakened empires lose fleet power over time — stall if needed.",
    "Enigmatic fortress/encoders are best-in-game evasion components.",
]


# ======================================================================== #
# Relics — powerful empire-wide artifacts
# ======================================================================== #

RELICS: dict[str, dict] = {
    "Galatron": {
        "passive": "+3 influence/month, +10% diplo weight",
        "triumph": "+20% happiness for 10 years",
        "source": "Caravaneers reliquary (0.5% chance)",
        "meta": "Best relic — massive influence income. War target if others have it.",
    },
    "Prethoryn Brood-Queen": {
        "passive": "+1 organic pop assembly",
        "triumph": "Spawn Prethoryn armies",
        "source": "Defeat Prethoryn crisis",
        "meta": "Free pop growth — very strong for bio empires.",
    },
    "Contingency Core": {
        "passive": "+20% research speed",
        "triumph": "+100% research speed for 10 years",
        "source": "Defeat Contingency crisis",
        "meta": "Strongest research boost in the game.",
    },
    "Unbidden Warlock": {
        "passive": "+20% energy, +20% shield HP",
        "triumph": "+50% energy for 10 years",
        "source": "Defeat Unbidden crisis",
        "meta": "Strong energy economy boost.",
    },
    "Scales of the Worm": {
        "passive": "+15% physics research, +10% society",
        "triumph": "Transform random pops into Tomb World preference",
        "source": "Horizon Signal event chain",
        "meta": "Solid research boost. Event chain is rare.",
    },
    "Head of Zarqlan": {
        "passive": "+100 unity/month, +1 edict capacity",
        "triumph": "All planets get +10 stability for 10 years",
        "source": "Archaeological site (Spiritualist or First League)",
        "meta": "Excellent unity income and stability.",
    },
    "Surveyor": {
        "passive": "+10% anomaly discovery, +1 sensor range",
        "triumph": "Reveal all hyperlanes in galaxy",
        "source": "Ancient Relics archaeological site",
        "meta": "Early game is where this shines. Reveal helps planning.",
    },
    "Vultaum Reality Perforator": {
        "passive": "+10% research speed",
        "triumph": "+30% research speed for 10 years",
        "source": "First League / Precursor chain",
        "meta": "Reliable research boost from precursors.",
    },
    "Blade of the Huntress": {
        "passive": "+10% army damage, +10% fire rate",
        "triumph": "+25% fire rate for 10 years",
        "source": "Archaeological site",
        "meta": "Strong combat relic for war-focused empires.",
    },
    "Omnicodex": {
        "passive": "+3 max leader level, +10% leader XP",
        "triumph": "Add random trait to all leaders",
        "source": "First League precursor chain",
        "meta": "Great for leader-focused builds.",
    },
}


# ======================================================================== #
# Leader Traits — strategically relevant traits
# ======================================================================== #

LEADER_TRAITS: dict[str, dict] = {
    # --- Scientist ---
    "Spark of Genius": {"class": "scientist", "effect": "+10% research speed", "meta": "best scientist trait"},
    "Meticulous": {"class": "scientist", "effect": "+10% anomaly discovery", "meta": "early game"},
    "Expertise (any)": {"class": "scientist", "effect": "+15% research in field", "meta": "match to research queue"},
    "Archaeologist": {"class": "scientist", "effect": "+25% archaeology speed", "meta": "early game relics"},
    "Maniacal": {"class": "scientist", "effect": "+5% research speed", "meta": "solid"},
    # --- Commander ---
    "Aggressive": {"class": "commander", "effect": "+10% fire rate, -10% disengagement", "meta": "best for offense"},
    "Cautious": {"class": "commander", "effect": "-20% damage taken, +10% disengagement", "meta": "best for defense"},
    "Fleet Organizer": {"class": "commander", "effect": "+10% naval cap from this fleet", "meta": "always good"},
    "Trickster": {"class": "commander", "effect": "+25% disengagement, +15% sublight speed", "meta": "save ships"},
    "Unyielding": {"class": "commander", "effect": "+20% hull points, -10% speed", "meta": "tank fleets"},
    "Scout": {"class": "commander", "effect": "+1 sensor range, +15% sublight speed", "meta": "exploration admiral"},
    # --- Official ---
    "Politician": {"class": "official", "effect": "+15% unity", "meta": "unity economy"},
    "Eye for Talent": {"class": "official", "effect": "+1 leader level cap", "meta": "great for council"},
    "Industrialist": {"class": "official", "effect": "+5% minerals, +5% energy", "meta": "economy governor"},
    "Intellectual": {"class": "official", "effect": "+10% research speed (planet)", "meta": "tech world governor"},
    "Righteous": {"class": "official", "effect": "-15% crime, +5% unity", "meta": "stability"},
    "Army Veteran": {"class": "official", "effect": "+10% army damage, +5% defense army HP", "meta": "niche"},
    # --- Negative (all classes) ---
    "Substance Abuser": {"class": "any", "effect": "-10% to main output", "meta": "dismiss if possible"},
    "Corrupt": {"class": "official", "effect": "+10% empire size", "meta": "replace ASAP"},
    "Lethargic": {"class": "any", "effect": "-25% XP gain", "meta": "avoid"},
}


# ======================================================================== #
# Planet Buildings — key buildings and their strategic role
# ======================================================================== #

PLANET_BUILDINGS: dict[str, dict] = {
    # --- Capital chain ---
    "Planetary Administration": {"tier": 1, "effect": "+2 complex jobs, +5 amenities", "unlocks": "more building slots"},
    "Planetary Capital": {"tier": 2, "effect": "+5 complex jobs, +8 amenities", "requires": "10+ pops, Colonial Centralization tech"},
    "System Capital-Complex": {"tier": 3, "effect": "+8 complex jobs, +10 amenities", "requires": "40+ pops, Galactic Administration tech"},
    # --- Research ---
    "Research Lab": {"tier": 1, "effect": "2 researcher jobs", "meta": "core building on every planet"},
    "Supercomputer": {"tier": 2, "effect": "3 researcher jobs + 5% planet research", "meta": "upgrade when available"},
    # --- Alloy ---
    "Alloy Foundry": {"tier": 1, "effect": "2 metallurgist jobs", "meta": "priority on industrial worlds"},
    "Alloy Mega-Forge": {"tier": 2, "effect": "3 metallurgist jobs + 5% planet alloys", "meta": "upgrade priority"},
    # --- Consumer Goods ---
    "Civilian Industries": {"tier": 1, "effect": "2 artisan jobs", "meta": "needed for CG balance"},
    "Civilian Repli-Complex": {"tier": 2, "effect": "3 artisan jobs + 5% planet CG", "meta": "upgrade on factory worlds"},
    # --- Unity ---
    "Temple/Monument": {"tier": 1, "effect": "2 priest/culture worker jobs", "meta": "1 per planet minimum"},
    "Grand Archive HQ": {"tier": 2, "effect": "archivist jobs + planet bonuses", "meta": "strong for unity"},
    # --- Strategic ---
    "Stronghold": {"tier": 1, "effect": "2 soldier jobs, +5 defense armies", "meta": "fortress worlds only"},
    "Fortress": {"tier": 2, "effect": "3 soldier jobs, FTL inhibitor", "meta": "chokepoint planets"},
    "Robot Assembly Plant": {"tier": 1, "effect": "+1 pop assembly", "meta": "build everywhere for growth"},
    "Clone Vats": {"tier": 1, "effect": "+1 organic pop assembly", "meta": "bio empires — build everywhere"},
    "Gene Clinic": {"tier": 1, "effect": "2 medical workers, +pop growth", "meta": "early game growth boost"},
    "Holo-Theatre": {"tier": 1, "effect": "2 entertainer jobs, +amenities", "meta": "amenity management"},
    "Commercial Zone": {"tier": 1, "effect": "2 clerk/trader jobs, +trade value", "meta": "trade empires only"},
    "Precinct House": {"tier": 1, "effect": "2 enforcer jobs, -crime", "meta": "only if crime > 20"},
    "Planetary Shield Generator": {"tier": 2, "effect": "+5 planetary defense, +shield", "meta": "border worlds"},
}

DISTRICT_TYPES: dict[str, dict] = {
    "City": {"effect": "+5 housing, +1 clerk job", "meta": "build for housing, not jobs"},
    "Generator": {"effect": "2 technician jobs", "meta": "Generator Worlds"},
    "Mining": {"effect": "2 miner jobs", "meta": "Mining Worlds"},
    "Agriculture": {"effect": "2 farmer jobs", "meta": "only what you need for food"},
    "Industrial": {"effect": "2 metallurgist OR artisan jobs", "meta": "priority on all planets"},
    "Leisure": {"effect": "2 entertainer jobs, +amenities", "meta": "replaces city for amenities"},
    "Trade": {"effect": "clerk jobs, +trade value", "meta": "trade empires, replaces city"},
    "Nexus": {"effect": "3 complex drone jobs (Machine/Hive)", "meta": "gestalt housing equivalent"},
}

PLANET_BUILD_META: list[str] = [
    "Industrial districts are king — alloys/CG from day one.",
    "1 research lab per planet minimum, upgrade ASAP.",
    "Robot Assembly Plant on EVERY planet for free pop growth.",
    "Gene Clinic is only worth it early game; replace mid-game.",
    "Fortress worlds on chokepoints — 3 strongholds + planetary shield.",
    "Don't overbuild food/mining districts — efficiency matters more than raw output.",
    "Capital buildings are free jobs — always upgrade when pop threshold met.",
]


# ======================================================================== #
# Situations — dynamic event-driven mechanics
# ======================================================================== #

SITUATIONS: dict[str, dict] = {
    "food_shortage": {
        "trigger": "food deficit for extended time",
        "effect": "pops start declining, stability drops",
        "fix": "IMPROVE_ECONOMY: build agriculture districts or buy food on market",
        "severity": "high",
    },
    "energy_shortage": {
        "trigger": "energy deficit",
        "effect": "buildings/districts deactivate, fleet upkeep unpaid",
        "fix": "IMPROVE_ECONOMY: build generator districts, sell surplus minerals",
        "severity": "critical",
    },
    "crime_wave": {
        "trigger": "crime > 50 on a planet",
        "effect": "reduced stability, criminal jobs appear, negative events",
        "fix": "CONSOLIDATE: build precinct house, assign enforcer governor",
        "severity": "medium",
    },
    "low_stability": {
        "trigger": "stability < 25",
        "effect": "reduced resource output, revolt risk",
        "fix": "CONSOLIDATE: increase amenities, reduce crime, manage factions",
        "severity": "high",
    },
    "unemployment": {
        "trigger": "unemployed pops on planet",
        "effect": "crime increase, happiness decrease",
        "fix": "IMPROVE_ECONOMY: build districts/buildings for jobs, or resettle",
        "severity": "medium",
    },
    "piracy": {
        "trigger": "trade routes unpatrolled",
        "effect": "trade value lost along routes",
        "fix": "BUILD_STARBASE: add hangar bays on trade route starbases, patrol fleets",
        "severity": "low",
    },
    "labor_deficit": {
        "trigger": "open jobs > available workers",
        "effect": "reduced output from unfilled jobs",
        "fix": "COLONIZE or grow pops; prioritize robot assembly",
        "severity": "medium",
    },
    "housing_shortage": {
        "trigger": "free housing <= 0",
        "effect": "pop growth slows, emigration push",
        "fix": "IMPROVE_ECONOMY: build city districts or housing buildings",
        "severity": "medium",
    },
}


# ======================================================================== #
# Public API
# ======================================================================== #

def get_tradition_guidance(year: int, ethics: list[str] | None = None) -> dict:
    """Return tradition tree recommendations for the current game phase."""
    phase = _phase_from_year(year)
    recommended = TRADITION_PHASE_GUIDANCE.get(phase.value, [])

    return {
        "phase": phase.value,
        "recommended_trees": recommended,
        "notes": {name: TRADITION_TREES[name].get("meta_priority", "") for name in recommended if name in TRADITION_TREES},
    }


def get_ascension_perk_guidance(tier: int = 0) -> list[dict]:
    """Return ascension perks available at a given tier."""
    return [
        {"name": name, **data}
        for name, data in ASCENSION_PERKS.items()
        if data["tier"] <= tier
    ]


def get_megastructure_guidance(year: int) -> list[dict]:
    """Return megastructure recommendations for the current game phase."""
    phase = _phase_from_year(year)
    results = []
    for name, data in MEGASTRUCTURES.items():
        priority = data.get("meta_priority", "")
        if phase == GamePhase.LATE or "high" in priority or "essential" in priority:
            results.append({"name": name, **data})
    return results


def get_designation_for_focus(focus: str) -> str | None:
    """Return the best planet designation for a given economic focus."""
    mapping = {
        "energy": "Generator World",
        "minerals": "Mining World",
        "food": "Agri-World",
        "alloys": "Industrial World",
        "research": "Tech-World",
        "unity": "Unification Center",
        "trade": "Trade Station",
        "defense": "Fortress World",
    }
    return mapping.get(focus.lower())


def get_edict_guidance(year: int) -> list[dict]:
    """Return edict recommendations for the current game phase."""
    phase = _phase_from_year(year)
    results = []
    for name, data in EDICTS.items():
        meta = data.get("meta", "")
        when = data.get("when", "")
        if phase == GamePhase.EARLY and "early" in meta.lower():
            results.append({"name": name, **data})
        elif phase == GamePhase.MID and ("war" in meta.lower() or "strong" in meta.lower()):
            results.append({"name": name, **data})
        elif phase == GamePhase.LATE:
            results.append({"name": name, **data})
        elif "essential" in meta.lower():
            results.append({"name": name, **data})
    return results


def get_tech_priorities(year: int) -> dict:
    """Return technology priorities for the current game phase."""
    phase = _phase_from_year(year)
    return TECH_PRIORITIES.get(phase.value, TECH_PRIORITIES["early"])


def get_starbase_guidance(year: int) -> dict:
    """Return starbase strategy for the current game phase."""
    phase = _phase_from_year(year)
    phase_map = {
        GamePhase.EARLY: "early_game",
        GamePhase.MID: "mid_game",
        GamePhase.LATE: "late_game",
    }
    return STARBASE_STRATEGY.get(phase_map.get(phase, "early_game"), {})
