"""Shared pytest fixtures for Stellaris Overmind tests."""

from __future__ import annotations

import pytest


# ======================================================================== #
# Empire Fixtures
# ======================================================================== #

@pytest.fixture
def une_empire() -> dict:
    """United Nations of Earth — standard democratic empire."""
    return {
        "ethics": ["Egalitarian", "Xenophile", "Militarist"],
        "civics": ["Beacon of Liberty", "Meritocracy"],
        "traits": ["Intelligent", "Thrifty"],
        "origin": "Prosperous Unification",
        "government": "Democracy",
    }


@pytest.fixture
def void_dwellers_empire() -> dict:
    """Void Dwellers — habitat-only colonization."""
    return {
        "ethics": ["Fanatic Materialist", "Xenophobe"],
        "civics": ["Technocracy", "Citizen Service"],
        "traits": ["Intelligent", "Natural Engineers"],
        "origin": "Void Dwellers",
        "government": "Oligarchy",
    }


@pytest.fixture
def cybernetic_creed_empire() -> dict:
    """Cybernetic Creed — worker stacking meta build."""
    return {
        "ethics": ["Fanatic Authoritarian", "Spiritualist"],
        "civics": ["Corvée System", "Planet Forgers"],
        "traits": ["Ingenious", "Industrious"],
        "origin": "Cybernetic Creed",
        "government": "Imperial",
    }


@pytest.fixture
def uor_empire() -> dict:
    """Under One Rule — synthetic ascension snowball."""
    return {
        "ethics": ["Xenophobe", "Pacifist", "Materialist"],
        "civics": ["Byzantine Bureaucracy", "Technocracy"],
        "traits": ["Intelligent", "Traditional", "Rapid Breeders"],
        "origin": "Under One Rule",
        "government": "Dictatorial",
    }


@pytest.fixture
def endbringer_empire() -> dict:
    """Endbringers — psionic crisis rush."""
    return {
        "ethics": ["Fanatic Militarist", "Egalitarian"],
        "civics": ["Idealistic Foundation", "Distinguished Admiralty"],
        "traits": ["Unbreakable Resolve", "Familial"],
        "origin": "Endbringers",
        "government": "Democracy",
    }


@pytest.fixture
def necrophage_empire() -> dict:
    """Necrophage — pop snowball."""
    return {
        "ethics": ["Fanatic Xenophobe", "Materialist"],
        "civics": ["Technocracy", "Slaver Guilds"],
        "traits": ["Intelligent", "Strong"],
        "origin": "Necrophage",
        "government": "Oligarchy",
    }


@pytest.fixture
def hive_mind_empire() -> dict:
    """Hive Mind — unified gestalt."""
    return {
        "ethics": ["Gestalt Consciousness"],
        "civics": [],
        "traits": ["Rapid Breeders"],
        "origin": "Hive Mind",
        "government": "Hive Mind",
    }


@pytest.fixture
def machine_empire() -> dict:
    """Machine Intelligence — logic modules."""
    return {
        "ethics": ["Gestalt Consciousness"],
        "civics": [],
        "traits": ["Rapid Replicators", "Mass Produced"],
        "origin": "Machine Intelligence",
        "government": "Machine Intelligence",
    }


# ======================================================================== #
# State Fixtures
# ======================================================================== #

@pytest.fixture
def early_game_state() -> dict:
    """Minimal early-game state snapshot (year 2210)."""
    return {
        "version": "4.3.4",
        "year": 2210,
        "month": 3,
        "colonies": ["Earth", "Mars"],
        "known_empires": [
            {"name": "Tzynn Empire", "attitude": "Hostile", "intel_level": "Low"},
        ],
        "economy": {
            "energy": 100,
            "minerals": 200,
            "food": 80,
            "alloys": 30,
            "consumer_goods": 20,
            "influence": 3,
            "unity": 15,
        },
        "fleets": [
            {
                "name": "1st Fleet",
                "power": 1500,
                "location_system": "Sol",
                "composition": {"corvettes": 10},
            },
        ],
    }


@pytest.fixture
def mid_game_state() -> dict:
    """Mid-game state snapshot (year 2280)."""
    return {
        "version": "4.3.4",
        "year": 2280,
        "month": 6,
        "colonies": ["Earth", "Mars", "Alpha Centauri III", "Deneb IV", "Sirius Prime"],
        "known_empires": [
            {"name": "Tzynn Empire", "attitude": "Hostile", "intel_level": "Medium"},
            {"name": "Iferyx Fleets", "attitude": "Cordial", "intel_level": "High"},
        ],
        "economy": {
            "energy": 350,
            "minerals": 500,
            "food": 150,
            "alloys": 120,
            "consumer_goods": 60,
            "influence": 4,
            "unity": 80,
        },
        "fleets": [
            {
                "name": "1st Fleet",
                "power": 8000,
                "location_system": "Sol",
                "composition": {"corvettes": 15, "destroyers": 5, "cruisers": 3},
            },
        ],
    }


@pytest.fixture
def late_game_state() -> dict:
    """Late-game state snapshot (year 2380)."""
    return {
        "version": "4.3.4",
        "year": 2380,
        "month": 1,
        "colonies": [
            "Earth", "Mars", "Alpha Centauri III", "Deneb IV",
            "Sirius Prime", "Vega II", "Arcturus III", "Polaris IV",
        ],
        "known_empires": [
            {"name": "Tzynn Empire", "attitude": "Hostile", "intel_level": "High"},
            {"name": "Iferyx Fleets", "attitude": "Friendly", "intel_level": "Full"},
            {"name": "Prikkiki-Ti", "attitude": "Hostile", "intel_level": "Medium"},
        ],
        "economy": {
            "energy": 800,
            "minerals": 1200,
            "food": 300,
            "alloys": 350,
            "consumer_goods": 150,
            "influence": 5,
            "unity": 200,
        },
        "fleets": [
            {
                "name": "Grand Fleet",
                "power": 45000,
                "location_system": "Sol",
                "composition": {"battleships": 10, "cruisers": 8, "destroyers": 6, "titans": 1},
            },
        ],
    }
