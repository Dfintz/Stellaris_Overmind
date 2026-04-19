"""Tests for save_reader — Stellaris 4.3.4."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from engine.save_reader import (
    SaveReader,
    SaveWatcherConfig,
    _detect_events,
    _extract_ascension_perks,
    _extract_capacity,
    _extract_colonies,
    _extract_economy,
    _extract_edicts,
    _extract_leaders,
    _extract_policies,
    _extract_starbases,
    _extract_technology,
    _extract_traditions,
    _extract_wars,
    _find_player_country,
    _intel_to_label,
    _parse_date,
)


class TestParseDate:

    def test_normal_date(self) -> None:
        assert _parse_date("2230.06.15") == (2230, 6)

    def test_short_date(self) -> None:
        assert _parse_date("2200") == (2200, 1)

    def test_invalid_date(self) -> None:
        assert _parse_date("not_a_date") == (2200, 1)

    def test_non_string(self) -> None:
        assert _parse_date(2230) == (2200, 1)


class TestIntelLabels:

    def test_none_level(self) -> None:
        assert _intel_to_label(0) == "none"

    def test_low_level(self) -> None:
        assert _intel_to_label(15) == "low"

    def test_medium_level(self) -> None:
        assert _intel_to_label(45) == "medium"

    def test_high_level(self) -> None:
        assert _intel_to_label(75) == "high"

    def test_full_level(self) -> None:
        assert _intel_to_label(95) == "full"


class TestExtractEconomy:

    def test_extracts_resources(self) -> None:
        country = {
            "modules": {
                "standard_economy_module": {
                    "resources": {
                        "energy": 500.0,
                        "minerals": 1200,
                        "food": 80,
                        "alloys": 120,
                        "consumer_goods": 45,
                        "influence": 3.5,
                        "unity": 60,
                    }
                }
            }
        }
        eco = _extract_economy(country)
        assert eco["energy"] == 500.0
        assert eco["minerals"] == 1200.0
        assert eco["unity"] == 60.0

    def test_missing_resources_default_zero(self) -> None:
        eco = _extract_economy({})
        assert eco["energy"] == 0.0
        assert eco["alloys"] == 0.0


class TestDetectEvents:

    def test_new_empire_contact(self) -> None:
        prev = {"known_empires": [{"name": "Empire A"}], "colonies": [], "economy": {}, "fleets": []}
        curr = {"known_empires": [{"name": "Empire A"}, {"name": "Empire B"}], "colonies": [], "economy": {}, "fleets": []}
        assert _detect_events(prev, curr) == "BORDER_CONTACT_NEW_EMPIRE"

    def test_war_declared(self) -> None:
        prev = {"known_empires": [{"name": "E", "attitude": "wary"}], "colonies": [], "economy": {}, "fleets": []}
        curr = {"known_empires": [{"name": "E", "attitude": "hostile"}], "colonies": [], "economy": {}, "fleets": []}
        assert _detect_events(prev, curr) == "WAR_DECLARED"

    def test_colony_established(self) -> None:
        prev = {"known_empires": [], "colonies": [{"name": "Earth"}], "economy": {}, "fleets": []}
        curr = {"known_empires": [], "colonies": [{"name": "Earth"}, {"name": "Mars"}], "economy": {}, "fleets": []}
        assert _detect_events(prev, curr) == "COLONY_ESTABLISHED"

    def test_colony_established_legacy_strings(self) -> None:
        prev = {"known_empires": [], "colonies": ["Earth"], "economy": {}, "fleets": []}
        curr = {"known_empires": [], "colonies": ["Earth", "Mars"], "economy": {}, "fleets": []}
        assert _detect_events(prev, curr) == "COLONY_ESTABLISHED"

    def test_economy_deficit(self) -> None:
        prev = {"known_empires": [], "colonies": [], "economy": {"energy": 50}, "fleets": []}
        curr = {"known_empires": [], "colonies": [], "economy": {"energy": -10}, "fleets": []}
        assert _detect_events(prev, curr) == "ECONOMY_DEFICIT"

    def test_fleet_lost(self) -> None:
        prev = {"known_empires": [], "colonies": [], "economy": {}, "fleets": [{"power": 10000}]}
        curr = {"known_empires": [], "colonies": [], "economy": {}, "fleets": [{"power": 5000}]}
        assert _detect_events(prev, curr) == "FLEET_LOST"

    def test_heartbeat_when_nothing_changed(self) -> None:
        state = {"known_empires": [], "colonies": ["Earth"], "economy": {"energy": 100}, "fleets": [{"power": 5000}]}
        assert _detect_events(state, state) == "HEARTBEAT"


class TestSaveReader:

    def test_find_latest_save(self, tmp_path: Path) -> None:
        save_dir = tmp_path / "saves"
        save_dir.mkdir()
        empire_dir = save_dir / "test_empire"
        empire_dir.mkdir()

        # Create fake .sav files with different mtimes
        sav1 = empire_dir / "autosave_2230.sav"
        with zipfile.ZipFile(sav1, "w") as zf:
            zf.writestr("meta", 'date = "2230.01.01"')
            zf.writestr("gamestate", "date = 2230.01.01")

        import time
        time.sleep(0.05)  # ensure different mtime

        sav2 = empire_dir / "autosave_2235.sav"
        with zipfile.ZipFile(sav2, "w") as zf:
            zf.writestr("meta", 'date = "2235.01.01"')
            zf.writestr("gamestate", "date = 2235.01.01")

        reader = SaveReader(SaveWatcherConfig(save_dir=save_dir))
        latest = reader.find_latest_save()
        assert latest is not None
        assert "2235" in latest.name

    def test_no_saves_returns_none(self, tmp_path: Path) -> None:
        reader = SaveReader(SaveWatcherConfig(save_dir=tmp_path))
        assert reader.find_latest_save() is None


class TestFindPlayerCountry:

    def test_finds_by_player_block(self) -> None:
        gamestate = {
            "player": [{"name": "Fintz", "country": 0}],
            "country": {
                "0": {"type": "default", "name": {"key": "TestEmpire"}},
                "1": {"type": "default", "name": {"key": "AIEmpire"}},
            },
        }
        country, cid = _find_player_country(gamestate, {})
        assert cid == "0"
        assert country["name"]["key"] == "TestEmpire"

    def test_fallback_to_first_default(self) -> None:
        gamestate = {
            "player": [],
            "country": {
                "0": {"type": "default", "name": "Empire A"},
            },
        }
        country, cid = _find_player_country(gamestate, {})
        assert cid == "0"

    def test_empty_gamestate(self) -> None:
        country, cid = _find_player_country({}, {})
        assert country == {}
        assert cid == "0"


class TestExtractTechnology:

    def test_extracts_researched_techs(self) -> None:
        country = {
            "tech_status": {
                "technology": ["tech_corvettes", "tech_starbase_1", "tech_lasers_1"],
                "level": [1, 1, 1],
            }
        }
        tech = _extract_technology(country)
        assert tech["count"] == 3
        assert "tech_corvettes" in tech["researched"]
        assert "tech_lasers_1" in tech["researched"]

    def test_extracts_current_research(self) -> None:
        country = {
            "tech_status": {
                "technology": [],
                "physics_queue": [{"technology": "tech_shields_1", "progress": 50}],
                "society_queue": [{"technology": "tech_genome_mapping", "progress": 10}],
                "engineering_queue": [{"technology": "tech_torpedoes_1", "progress": 30}],
            }
        }
        tech = _extract_technology(country)
        assert tech["in_progress"]["physics"] == "tech_shields_1"
        assert tech["in_progress"]["society"] == "tech_genome_mapping"
        assert tech["in_progress"]["engineering"] == "tech_torpedoes_1"

    def test_empty_tech_status(self) -> None:
        tech = _extract_technology({})
        assert tech["researched"] == []
        assert tech["in_progress"] == {}
        assert tech["count"] == 0


class TestExtractTraditions:

    def test_extracts_tradition_list(self) -> None:
        country = {"traditions": ["tr_prosperity_adopt", "tr_prosperity_public_works"]}
        assert _extract_traditions(country) == ["tr_prosperity_adopt", "tr_prosperity_public_works"]

    def test_single_tradition(self) -> None:
        country = {"traditions": "tr_expansion_adopt"}
        assert _extract_traditions(country) == ["tr_expansion_adopt"]

    def test_empty(self) -> None:
        assert _extract_traditions({}) == []


class TestExtractAscensionPerks:

    def test_extracts_perks(self) -> None:
        country = {"ascension_perks": ["ap_technological_ascendancy", "ap_one_vision"]}
        assert _extract_ascension_perks(country) == ["ap_technological_ascendancy", "ap_one_vision"]

    def test_empty(self) -> None:
        assert _extract_ascension_perks({}) == []


class TestExtractPolicies:

    def test_extracts_active_policies(self) -> None:
        country = {
            "active_policies": [
                {"policy": "diplomatic_stance", "selected": "diplo_stance_expansionist"},
                {"policy": "war_philosophy", "selected": "unrestricted_wars"},
                {"policy": "trade_policy", "selected": "trade_policy_wealth_creation"},
            ]
        }
        policies = _extract_policies(country)
        assert len(policies) == 3
        assert policies[0] == {"policy": "diplomatic_stance", "selected": "diplo_stance_expansionist"}
        assert policies[1] == {"policy": "war_philosophy", "selected": "unrestricted_wars"}

    def test_skips_invalid_entries(self) -> None:
        country = {"active_policies": ["invalid", {"policy": "x", "selected": "y"}, None]}
        policies = _extract_policies(country)
        assert len(policies) == 1

    def test_empty(self) -> None:
        assert _extract_policies({}) == []


class TestExtractEdicts:

    def test_extracts_edict_names(self) -> None:
        country = {
            "edicts": [
                {"edict": "recycling_campaign", "perpetual": True},
                {"edict": "fleet_supremacy", "perpetual": True},
            ]
        }
        edicts = _extract_edicts(country)
        assert edicts == ["recycling_campaign", "fleet_supremacy"]

    def test_empty(self) -> None:
        assert _extract_edicts({}) == []


class TestExtractWars:

    def test_extracts_player_war(self) -> None:
        gamestate = {
            "war": {
                "1": {
                    "attackers": [{"country": 0, "call_type": "primary"}],
                    "defenders": [{"country": 5, "call_type": "primary"}],
                    "attacker_war_goal": {"type": "wg_conquest"},
                    "attacker_war_exhaustion": 0.25,
                    "defender_war_exhaustion": 0.5,
                    "start_date": "2220.01.01",
                },
            }
        }
        wars = _extract_wars(gamestate, "0")
        assert len(wars) == 1
        assert wars[0]["side"] == "attacker"
        assert wars[0]["war_goal"] == "wg_conquest"
        assert wars[0]["war_exhaustion"] == 0.25

    def test_player_as_defender(self) -> None:
        gamestate = {
            "war": {
                "1": {
                    "attackers": [{"country": 5}],
                    "defenders": [{"country": 0}],
                    "attacker_war_goal": {"type": "wg_conquest"},
                    "defender_war_goal": {"type": "wg_humiliation"},
                    "attacker_war_exhaustion": 0.1,
                    "defender_war_exhaustion": 0.3,
                    "start_date": "2218.05.18",
                },
            }
        }
        wars = _extract_wars(gamestate, "0")
        assert len(wars) == 1
        assert wars[0]["side"] == "defender"
        assert wars[0]["war_goal"] == "wg_humiliation"
        assert wars[0]["war_exhaustion"] == 0.3

    def test_no_wars(self) -> None:
        assert _extract_wars({"war": {}}, "0") == []
        assert _extract_wars({}, "0") == []

    def test_war_not_involving_player(self) -> None:
        gamestate = {
            "war": {
                "1": {
                    "attackers": [{"country": 3}],
                    "defenders": [{"country": 5}],
                    "attacker_war_goal": {"type": "wg_conquest"},
                    "attacker_war_exhaustion": 0,
                    "defender_war_exhaustion": 0,
                    "start_date": "2220.01.01",
                },
            }
        }
        assert _extract_wars(gamestate, "0") == []


class TestExtractColoniesDetailed:

    def test_extracts_planet_details(self) -> None:
        gamestate = {
            "planets": {
                "planet": {
                    "12": {
                        "name": {"key": "Earth"},
                        "planet_class": "pc_continental",
                        "planet_size": 20,
                        "designation": "col_capital",
                        "final_designation": "col_capital",
                        "num_sapient_pops": 45,
                        "districts": [0, 1, 2],
                        "stability": 72.5,
                        "crime": 5.3,
                        "free_housing": 10,
                    }
                }
            }
        }
        country = {"owned_planets": [12]}
        colonies = _extract_colonies(gamestate, country)
        assert len(colonies) == 1
        c = colonies[0]
        assert c["name"] == "Earth"
        assert c["planet_class"] == "pc_continental"
        assert c["planet_size"] == 20
        assert c["pops"] == 45
        assert c["districts"] == 3
        assert c["stability"] == 72.5
        assert c["crime"] == 5.3
        assert c["free_housing"] == 10

    def test_handles_missing_planet_data(self) -> None:
        gamestate = {"planets": {"planet": {"99": {"name": "Mars"}}}}
        country = {"owned_planets": [99]}
        colonies = _extract_colonies(gamestate, country)
        assert len(colonies) == 1
        assert colonies[0]["name"] == "Mars"
        assert colonies[0]["pops"] == 0

    def test_empty(self) -> None:
        assert _extract_colonies({}, {}) == []


class TestExtractEconomyEnriched:

    def test_includes_rare_resources(self) -> None:
        country = {
            "modules": {
                "standard_economy_module": {
                    "resources": {
                        "energy": 500,
                        "minerals": 1200,
                        "exotic_gases": 50,
                        "volatile_motes": 30,
                        "rare_crystals": 0,
                        "food": 100,
                        "alloys": 200,
                        "consumer_goods": 50,
                        "influence": 3,
                        "unity": 60,
                    }
                }
            }
        }
        eco = _extract_economy(country)
        assert eco["exotic_gases"] == 50.0
        assert eco["volatile_motes"] == 30.0
        assert "rare_crystals" not in eco  # 0 is excluded

    def test_includes_monthly_net(self) -> None:
        country = {
            "modules": {
                "standard_economy_module": {
                    "resources": {"energy": 500, "minerals": 0, "food": 0, "alloys": 0,
                                  "consumer_goods": 0, "influence": 0, "unity": 0},
                }
            },
            "budget": {
                "last_month": {
                    "income": {
                        "country_base": {"energy": 20, "minerals": 20},
                        "planet_jobs": {"energy": 80, "minerals": 60},
                    },
                    "expenses": {
                        "upkeep": {"energy": 60, "minerals": 50},
                    },
                }
            },
        }
        eco = _extract_economy(country)
        assert eco["monthly_net"]["energy"] == 40.0
        assert eco["monthly_net"]["minerals"] == 30.0


class TestDetectEventsNew:

    def test_war_detected_from_wars_field(self) -> None:
        prev = {"known_empires": [], "colonies": [], "economy": {}, "fleets": [], "wars": []}
        curr = {"known_empires": [], "colonies": [], "economy": {}, "fleets": [],
                "wars": [{"side": "attacker", "war_goal": "wg_conquest"}]}
        assert _detect_events(prev, curr) == "WAR_DECLARED"

    def test_tech_researched_event(self) -> None:
        prev = {"known_empires": [], "colonies": [], "economy": {}, "fleets": [],
                "technology": {"researched": ["tech_a"]}}
        curr = {"known_empires": [], "colonies": [], "economy": {}, "fleets": [],
                "technology": {"researched": ["tech_a", "tech_b"]}}
        assert _detect_events(prev, curr) == "TECH_RESEARCHED"

    def test_nonexistent_dir_returns_none(self) -> None:
        reader = SaveReader(SaveWatcherConfig(save_dir=Path("/nonexistent")))
        assert reader.find_latest_save() is None


class TestExtractStarbases:

    def test_extracts_upgraded_starbases(self) -> None:
        gamestate = {
            "fleet": {
                "100": {
                    "movement_manager": {
                        "coordinate": {"origin": 5},
                    },
                },
            },
            "galactic_object": {
                "5": {"name": {"key": "Sol"}},
            },
            "starbase_mgr": {
                "starbases": {
                    "0": {
                        "station": 100,
                        "level": "starbase_level_starport",
                        "type": "sshipyard",
                        "modules": {0: "shipyard", 1: "anchorage"},
                        "buildings": {0: "crew_quarters"},
                    },
                }
            },
        }
        country = {
            "fleets_manager": {
                "owned_fleets": [{"fleet": 100}],
            },
        }
        starbases = _extract_starbases(gamestate, country)
        assert len(starbases) == 1
        assert starbases[0]["system"] == "Sol"
        assert starbases[0]["level"] == "starport"
        assert "shipyard" in starbases[0]["modules"]
        assert "crew_quarters" in starbases[0]["buildings"]

    def test_skips_outposts(self) -> None:
        gamestate = {
            "fleet": {"100": {}},
            "starbase_mgr": {
                "starbases": {
                    "0": {
                        "station": 100,
                        "level": "starbase_level_outpost",
                    },
                }
            },
        }
        country = {
            "fleets_manager": {
                "owned_fleets": [{"fleet": 100}],
            },
        }
        assert _extract_starbases(gamestate, country) == []

    def test_skips_foreign_starbases(self) -> None:
        gamestate = {
            "starbase_mgr": {
                "starbases": {
                    "0": {"station": 999, "level": "starbase_level_starport"},
                }
            },
        }
        country = {
            "fleets_manager": {
                "owned_fleets": [{"fleet": 100}],
            },
        }
        assert _extract_starbases(gamestate, country) == []

    def test_empty(self) -> None:
        assert _extract_starbases({}, {}) == []


class TestExtractLeaders:

    def test_extracts_leader_info(self) -> None:
        gamestate = {
            "leaders": {
                "10": {
                    "class": "scientist",
                    "level": 5,
                    "traits": ["leader_trait_expertise_physics", "leader_trait_spark_of_genius"],
                },
                "20": {
                    "class": "commander",
                    "level": 3,
                    "traits": ["leader_trait_aggressive"],
                },
            }
        }
        country = {"owned_leaders": [10, 20]}
        leaders = _extract_leaders(gamestate, country)
        assert len(leaders) == 2
        assert leaders[0]["class"] == "scientist"
        assert leaders[0]["level"] == 5
        assert len(leaders[0]["traits"]) == 2
        assert leaders[1]["class"] == "commander"

    def test_empty(self) -> None:
        assert _extract_leaders({}, {}) == []


class TestExtractCapacity:

    def test_extracts_capacity_data(self) -> None:
        country = {
            "used_naval_capacity": 55,
            "starbase_capacity": 4,
            "empire_size": 101,
        }
        cap = _extract_capacity(country)
        assert cap["used_naval_capacity"] == 55
        assert cap["starbase_capacity"] == 4
        assert cap["empire_size"] == 101

    def test_empty(self) -> None:
        assert _extract_capacity({}) == {}
