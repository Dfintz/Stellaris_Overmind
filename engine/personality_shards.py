"""
Personality Shards — Stellaris 4.3.4 LLM AI Overhaul

Generates per‑empire personality profiles from ethics, civics, traits, origin,
and government type.  Each leader type contributes a "shard" whose weight is
determined by government structure.

The personality profile is included in LLM prompts so the AI adopts a
believable strategic identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ======================================================================== #
# Government → Leader Weighting
# ======================================================================== #

GOVERNMENT_WEIGHTS: dict[str, dict[str, float]] = {
    "Imperial": {
        "ruler": 0.80,
        "admiral": 0.05,
        "governor": 0.05,
        "scientist": 0.05,
        "general": 0.05,
    },
    "Dictatorial": {
        "ruler": 0.70,
        "admiral": 0.10,
        "governor": 0.05,
        "scientist": 0.10,
        "general": 0.05,
    },
    "Democracy": {
        "ruler": 0.20,
        "admiral": 0.20,
        "governor": 0.20,
        "scientist": 0.20,
        "general": 0.20,
    },
    "Oligarchy": {
        "ruler": 0.40,
        "admiral": 0.15,
        "governor": 0.20,
        "scientist": 0.15,
        "general": 0.10,
    },
    "Corporate": {
        "ruler": 0.35,
        "admiral": 0.10,
        "governor": 0.30,
        "scientist": 0.15,
        "general": 0.10,
    },
    "Hive Mind": {
        "ruler": 1.0,
        "admiral": 0.0,
        "governor": 0.0,
        "scientist": 0.0,
        "general": 0.0,
    },
    "Machine Intelligence": {
        "ruler": 1.0,
        "admiral": 0.0,
        "governor": 0.0,
        "scientist": 0.0,
        "general": 0.0,
    },
}

DEFAULT_WEIGHTS: dict[str, float] = {
    "ruler": 0.40,
    "admiral": 0.15,
    "governor": 0.15,
    "scientist": 0.15,
    "general": 0.15,
}


# ======================================================================== #
# Ascension Path Preferences (from META_4.3.4.md)
# ======================================================================== #

ASCENSION_PREFERENCES: dict[str, str] = {
    # origin → preferred ascension
    "Cybernetic Creed": "cybernetic",
    "Under One Rule": "synthetic",
    "Void Dwellers": "virtual",
    "Endbringers": "psionic",
    "Teachers of the Shroud": "psionic",
    "Shroud-Forged": "psionic",
    "Synthetic Fertility": "synthetic",
    "Clone Army": "biological",
    "Necrophage": "biological",
}


# ======================================================================== #
# Helpers
# ======================================================================== #

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


# ======================================================================== #
# Personality Profile
# ======================================================================== #

@dataclass
class PersonalityProfile:
    """Structured personality for an empire, consumed by the decision engine."""

    war_willingness: float = 0.5
    expansion_drive: float = 0.5
    tech_focus: float = 0.5
    unity_focus: float = 0.5
    diplomatic_openness: float = 0.5
    trade_focus: float = 0.3
    economic_style: str = "balanced"
    risk_tolerance: float = 0.5
    ascension_preference: str = "any"
    crisis_preparedness: float = 0.3
    fleet_doctrine: str = "balanced"
    leader_weights: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "war_willingness": round(self.war_willingness, 2),
            "expansion_drive": round(self.expansion_drive, 2),
            "tech_focus": round(self.tech_focus, 2),
            "unity_focus": round(self.unity_focus, 2),
            "diplomatic_openness": round(self.diplomatic_openness, 2),
            "trade_focus": round(self.trade_focus, 2),
            "economic_style": self.economic_style,
            "risk_tolerance": round(self.risk_tolerance, 2),
            "ascension_preference": self.ascension_preference,
            "crisis_preparedness": round(self.crisis_preparedness, 2),
            "fleet_doctrine": self.fleet_doctrine,
            "leader_weights": {
                k: round(v, 2) for k, v in self.leader_weights.items()
            },
        }


def build_personality(
    ethics: list[str],
    civics: list[str],
    traits: list[str],
    origin: str,
    government: str,
) -> dict:
    """Generate a personality profile dict for one empire."""
    p = PersonalityProfile()

    # --- Ethics influence ---
    for ethic in ethics:
        e = ethic.lower().replace("fanatic ", "")
        fanatic = ethic.lower().startswith("fanatic")
        m = 1.5 if fanatic else 1.0

        if e == "militarist":
            p.war_willingness += 0.2 * m
            p.risk_tolerance += 0.1 * m
            p.fleet_doctrine = "aggressive"
        elif e == "pacifist":
            p.war_willingness -= 0.2 * m
            p.diplomatic_openness += 0.1 * m
            p.fleet_doctrine = "defensive"
        elif e == "xenophile":
            p.diplomatic_openness += 0.2 * m
            p.trade_focus += 0.15 * m
        elif e == "xenophobe":
            p.diplomatic_openness -= 0.2 * m
            p.expansion_drive += 0.15 * m
        elif e == "materialist":
            p.tech_focus += 0.15 * m
        elif e == "spiritualist":
            p.unity_focus += 0.15 * m
            p.tech_focus -= 0.05 * m
        elif e == "egalitarian":
            p.economic_style = "consumer_balanced"
            p.trade_focus += 0.1 * m
        elif e == "authoritarian":
            p.economic_style = "alloy_focused"

    # --- Civic nudges ---
    for civic in civics:
        if civic == "Distinguished Admiralty":
            p.war_willingness += 0.1
            p.fleet_doctrine = "aggressive"
        elif civic == "Technocracy":
            p.tech_focus += 0.15
        elif civic in ("Merchant Guilds", "Masterful Crafters", "Worker Cooperative"):
            p.economic_style = "trade_focused"
            p.trade_focus += 0.15
        elif civic == "Inward Perfection":
            p.diplomatic_openness = 0.0
            p.expansion_drive -= 0.1
            p.unity_focus += 0.2
        elif civic == "Citizen Service":
            p.war_willingness += 0.05
            p.fleet_doctrine = "aggressive"
        elif civic == "Slaver Guilds":
            p.tech_focus += 0.1
        elif civic == "Byzantine Bureaucracy":
            p.unity_focus += 0.1
        # --- Genocidal ---
        elif civic in ("Fanatic Purifiers", "Devouring Swarm", "Determined Exterminator"):
            p.war_willingness = 1.0
            p.diplomatic_openness = 0.0
            p.risk_tolerance += 0.3
            p.fleet_doctrine = "aggressive"
        # --- Machine Intelligence ---
        elif civic == "Rogue Servitor":
            p.unity_focus += 0.2
            p.diplomatic_openness += 0.1
        elif civic == "Driven Assimilator":
            p.war_willingness += 0.15
            p.expansion_drive += 0.1
        # --- Corporate ---
        elif civic in ("Corporate Authority", "Free Traders", "Private Prospectors"):
            p.trade_focus += 0.2
            p.economic_style = "trade_focused"
        elif civic == "Criminal Heritage":
            p.diplomatic_openness -= 0.1
            p.risk_tolerance += 0.1
        elif civic == "Gospel of the Masses":
            p.unity_focus += 0.15
            p.trade_focus += 0.1
        # --- Standard civics ---
        elif civic == "Barbaric Despoilers":
            p.war_willingness += 0.15
            p.fleet_doctrine = "aggressive"
        elif civic == "Nationalistic Zeal":
            p.war_willingness += 0.1
            p.expansion_drive += 0.05
        elif civic == "Diplomatic Corps":
            p.diplomatic_openness += 0.15
        elif civic == "Parliamentary System":
            p.diplomatic_openness += 0.05
        elif civic == "Meritocracy":
            p.tech_focus += 0.05
        elif civic == "Agrarian Idyll":
            p.expansion_drive -= 0.05
            p.economic_style = "food_focused"
        elif civic == "Catalytic Processing":
            p.economic_style = "food_to_alloy"
        elif civic in ("Death Cult", "Exalted Priesthood"):
            p.unity_focus += 0.1
        elif civic == "Pleasure Seekers":
            p.trade_focus += 0.05
        elif civic == "Shared Burdens":
            p.economic_style = "consumer_balanced"
        elif civic == "Mining Guilds":
            p.economic_style = "mineral_focused"

    # --- Trait nudges ---
    for trait in traits:
        if trait == "Intelligent":
            p.tech_focus += 0.05
        elif trait in ("Strong", "Very Strong"):
            p.war_willingness += 0.03
        elif trait == "Thrifty":
            p.trade_focus += 0.15
        elif trait == "Rapid Breeders":
            p.expansion_drive += 0.05
        elif trait == "Traditional":
            p.unity_focus += 0.05
        elif trait == "Unbreakable Resolve":
            pass  # stability bonus, no personality shift
        elif trait == "Ingenious":
            p.economic_style = "energy_focused"
        elif trait == "Industrious":
            p.economic_style = "mineral_focused"
        elif trait in ("Natural Engineers", "Natural Physicists", "Natural Sociologists"):
            p.tech_focus += 0.03
        elif trait == "Charismatic":
            p.diplomatic_openness += 0.03
        elif trait == "Repugnant":
            p.diplomatic_openness -= 0.03
        elif trait in ("Adaptive", "Extremely Adaptive"):
            p.expansion_drive += 0.03
        elif trait == "Nomadic":
            p.expansion_drive += 0.03
        elif trait in ("Communal", "Docile"):
            pass  # housing/admin, no personality shift
        elif trait in ("Fertile", "Rapid Replicators", "Mass Produced"):
            p.expansion_drive += 0.03
        elif trait == "Lithoid":
            p.economic_style = "mineral_focused"
        elif trait in ("Quick Learners", "Enduring", "Venerable"):
            p.tech_focus += 0.02

    # --- Origin personality ---
    if origin in ("Endbringers", "Doomsday"):
        p.risk_tolerance += 0.2
        p.crisis_preparedness += 0.2
    elif origin in ("Cybernetic Creed", "Under One Rule"):
        p.tech_focus += 0.1
    elif origin == "Void Dwellers":
        p.expansion_drive += 0.1
        p.unity_focus += 0.1
    elif origin == "Rogue Servitor":
        p.unity_focus += 0.2
        p.diplomatic_openness += 0.1
    elif origin in ("Teachers of the Shroud", "Shroud-Forged"):
        p.unity_focus += 0.15
    elif origin == "Necrophage":
        p.war_willingness += 0.1
        p.expansion_drive += 0.1
    elif origin == "Synthetic Fertility":
        p.tech_focus += 0.1
        p.expansion_drive += 0.05
    elif origin in ("Clone Army", "Overtuned"):
        p.expansion_drive += 0.1
    elif origin == "Shattered Ring":
        p.tech_focus += 0.15
        p.expansion_drive -= 0.1
    elif origin in ("Hegemon", "Common Ground"):
        p.diplomatic_openness += 0.15
    elif origin == "Remnants":
        p.tech_focus += 0.1
    elif origin == "Progenitor Hive":
        p.expansion_drive += 0.15
    elif origin == "Ocean Paradise":
        p.trade_focus += 0.15
        p.expansion_drive -= 0.05
    elif origin == "Imperial Fiefdom":
        p.diplomatic_openness += 0.1
        p.war_willingness += 0.05

    # --- Ascension preference from origin ---
    p.ascension_preference = ASCENSION_PREFERENCES.get(origin, "any")

    # --- Clamp numeric values ---
    for attr in (
        "war_willingness", "expansion_drive", "tech_focus", "unity_focus",
        "diplomatic_openness", "trade_focus", "risk_tolerance", "crisis_preparedness",
    ):
        setattr(p, attr, _clamp(getattr(p, attr)))

    # --- Leader weights from government ---
    p.leader_weights = GOVERNMENT_WEIGHTS.get(government, DEFAULT_WEIGHTS).copy()

    return p.to_dict()
