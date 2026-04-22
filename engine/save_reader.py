"""
Save Reader — Extracts game state from Stellaris autosave files.

Watches the Stellaris save directory for new ``.sav`` files, parses them
with the Clausewitz parser, and converts the raw data into the structured
state snapshot format consumed by the decision engine.

Key responsibilities:
  1. Watch ``save games/`` for new autosaves
  2. Parse the ``.sav`` ZIP → Clausewitz text → Python dict
  3. Extract our empire's data (economy, fleets, diplomacy, planets)
  4. Apply fog-of-war filtering based on intel levels
  5. Detect triggering events (war, contact, economy thresholds)
  6. Output a state snapshot dict matching ``docs/EXPORTER_SPEC.md``

This replaces the need for a Clausewitz state exporter mod entirely.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from engine.clausewitz_parser import parse_save

log = logging.getLogger(__name__)

GAME_VERSION = "4.3.4"


def detect_game_version(meta: dict) -> str:
    """Extract the game version from save file metadata.

    Stellaris saves store version as e.g. ``"Cetus v4.3.4"``.
    Returns just the numeric part (``"4.3.4"``).
    """
    raw = str(meta.get("version", ""))
    # Format: "PatchName vX.Y.Z" or just "X.Y.Z"
    if " v" in raw:
        return raw.split(" v", 1)[1].strip()
    # Try to extract version-like pattern
    import re
    match = re.search(r"\d+\.\d+\.\d+", raw)
    if match:
        return match.group()
    return raw or GAME_VERSION

# Intel level thresholds for fog-of-war filtering
INTEL_LEVELS = {
    0: "none",      # name + attitude only
    10: "low",      # government type, ethics
    30: "medium",   # fleet power estimate, economy class
    60: "high",     # detailed fleet comp, tech level, economy values
    90: "full",     # everything
}


@dataclass
class SaveWatcherConfig:
    """Configuration for the save file watcher."""

    save_dir: Path = Path("")
    poll_interval_s: float = 2.0
    player_name: str = ""  # auto-detected from meta if empty


class SaveReader:
    """Reads Stellaris autosave files and extracts state snapshots."""

    def __init__(self, config: SaveWatcherConfig) -> None:
        self._config = config
        self._last_mtime: float = 0.0
        self._last_save_path: Path | None = None
        self._previous_state: dict | None = None

    def find_latest_save(self) -> Path | None:
        """Find the most recently modified ``.sav`` file in the save directory."""
        save_dir = self._config.save_dir
        if not save_dir.exists():
            return None

        latest: Path | None = None
        latest_mtime: float = 0.0

        # Stellaris saves are in subdirs: save games/<empire_name>/*.sav
        for sav in save_dir.rglob("*.sav"):
            mtime = os.path.getmtime(sav)
            if mtime > latest_mtime:
                latest = sav
                latest_mtime = mtime

        return latest

    def has_new_save(self) -> bool:
        """Check if a new save file has appeared since last read."""
        latest = self.find_latest_save()
        if latest is None:
            return False
        mtime = os.path.getmtime(latest)
        return mtime > self._last_mtime

    def read_state(self) -> dict | None:
        """Read the latest save and return a state snapshot, or None if no new save."""
        latest = self.find_latest_save()
        if latest is None:
            return None

        mtime = os.path.getmtime(latest)
        if mtime <= self._last_mtime:
            return None

        log.info("Parsing save file: %s", latest.name)
        try:
            raw = parse_save(latest)
        except Exception:
            log.exception("Failed to parse save file: %s", latest)
            return None

        self._last_mtime = mtime
        self._last_save_path = latest

        meta = raw.get("meta", {})
        gamestate = raw.get("gamestate", {})

        # Identify the player
        player_name = self._config.player_name
        if not player_name:
            player_name = _detect_player(meta, gamestate)

        # Extract state snapshot
        state = self._extract_state(gamestate, meta, player_name)

        # Detect events by comparing to previous state
        if self._previous_state is not None:
            state["event"] = _detect_events(self._previous_state, state)
        else:
            state["event"] = "GAME_START"

        self._previous_state = state
        log.info(
            "State extracted: year=%s colonies=%d known_empires=%d event=%s",
            state.get("year"), len(state.get("colonies", [])),
            len(state.get("known_empires", [])), state.get("event"),
        )
        return state

    def _extract_state(
        self, gamestate: dict, meta: dict, player_name: str,
    ) -> dict:
        """Convert raw gamestate into our state snapshot format."""
        # Find player country
        player_country, player_id = _find_player_country(gamestate, meta)

        # Extract date
        date = meta.get("date", gamestate.get("date", "2200.01.01"))
        year, month = _parse_date(date)

        # Use meta name as display name (resolved from localization)
        display_name = str(meta.get("name", player_name))

        version = detect_game_version(meta)

        return _extract_state_for_country(
            gamestate, player_country, player_id, display_name, year, month,
            version=version,
        )

    def read_ai_states(
        self,
        country_ids: list[int] | None = None,
        exclude_ids: list[int] | None = None,
        exclude_fallen: bool = True,
    ) -> list[dict] | None:
        """Read the latest save and return state snapshots for AI empires.

        Each AI empire gets its own FoW-filtered state, with empire info
        auto-detected from the save (no config.toml [empire] needed).

        Parameters
        ----------
        country_ids : list[int] | None
            Specific AI country IDs to extract.  If *None*, extracts all.
        exclude_ids : list[int] | None
            Country IDs to skip (e.g. player, primitives).
        exclude_fallen : bool
            If *True*, skip Fallen Empires.
        """
        latest = self.find_latest_save()
        if latest is None:
            return None

        mtime = os.path.getmtime(latest)
        if mtime <= self._last_mtime:
            return None

        log.info("Parsing save file for AI empires: %s", latest.name)
        try:
            raw = parse_save(latest)
        except Exception:
            log.exception("Failed to parse save file: %s", latest)
            return None

        self._last_mtime = mtime
        self._last_save_path = latest

        meta = raw.get("meta", {})
        gamestate = raw.get("gamestate", {})

        version = detect_game_version(meta)
        date = meta.get("date", gamestate.get("date", "2200.01.01"))
        year, month = _parse_date(date)

        # Find all AI countries
        ai_countries = _find_ai_countries(
            gamestate, country_ids, exclude_ids, exclude_fallen,
        )

        states = []
        for cid, country in ai_countries:
            name = _get_country_display_name(country, str(cid))
            state = _extract_state_for_country(
                gamestate, country, str(cid), name, year, month,
                version=version,
            )
            state["country_id"] = cid
            states.append(state)

        log.info("Extracted %d AI empire states (year %d)", len(states), year)
        return states


# ------------------------------------------------------------------ #
# Player detection
# ------------------------------------------------------------------ #

def _detect_player(meta: dict, gamestate: dict) -> str:
    """Detect the player's empire name from save metadata."""
    name = meta.get("name", "")
    if name:
        return str(name)
    # Fall back to first player in gamestate
    players = gamestate.get("player", [])
    if isinstance(players, list) and players:
        first = players[0]
        if isinstance(first, dict):
            return str(first.get("name", "Player"))
    return "Player"


def _find_player_country(
    gamestate: dict, meta: dict,
) -> tuple[dict, str]:
    """Find the player's country dict and country ID.

    Uses the ``player`` block (``[{country: 0}]``) which is the most
    reliable way to identify the player's country.
    Returns ``(country_dict, country_id_str)``.
    """
    countries = gamestate.get("country", {})
    if not isinstance(countries, dict):
        return {}, "0"

    # Primary: use player block to get country ID directly
    players = gamestate.get("player", [])
    if isinstance(players, list):
        for p in players:
            if isinstance(p, dict):
                cid = p.get("country")
                if cid is not None:
                    country = countries.get(str(cid), {})
                    if isinstance(country, dict):
                        return country, str(cid)

    # Fallback: match by meta name
    meta_name = str(meta.get("name", ""))
    if meta_name:
        for cid, country in countries.items():
            if not isinstance(country, dict):
                continue
            name = country.get("name", "")
            if isinstance(name, dict):
                name = name.get("key", "")
            if str(name) == meta_name:
                return country, str(cid)

    # Last resort: first "default" country
    for cid, country in countries.items():
        if isinstance(country, dict) and country.get("type") == "default":
            return country, str(cid)
    return {}, "0"


def _extract_state_for_country(
    gamestate: dict,
    country: dict,
    country_id: str,
    display_name: str,
    year: int,
    month: int,
    version: str = "",
) -> dict:
    """Build a state snapshot for any country (player or AI)."""
    return {
        "version": version or GAME_VERSION,
        "year": year,
        "month": month,
        "empire": _extract_empire_info(country, display_name),
        "economy": _extract_economy(country),
        "fleets": _extract_fleets(gamestate, country),
        "colonies": _extract_colonies(gamestate, country),
        "known_empires": _extract_known_empires(gamestate, country),
        "technology": _extract_technology(country),
        "traditions": _extract_traditions(country),
        "ascension_perks": _extract_ascension_perks(country),
        "policies": _extract_policies(country),
        "edicts": _extract_edicts(country),
        "wars": _extract_wars(gamestate, country_id),
        "starbases": _extract_starbases(gamestate, country),
        "leaders": _extract_leaders(gamestate, country),
        "naval_capacity": _extract_capacity(country),
        "available_actions": [
            "EXPAND", "BUILD_FLEET", "IMPROVE_ECONOMY", "FOCUS_TECH",
            "DIPLOMACY", "PREPARE_WAR", "DEFEND", "CONSOLIDATE",
            "COLONIZE", "BUILD_STARBASE", "ESPIONAGE",
        ],
    }


def _find_ai_countries(
    gamestate: dict,
    include_ids: list[int] | None = None,
    exclude_ids: list[int] | None = None,
    exclude_fallen: bool = True,
) -> list[tuple[int, dict]]:
    """Find all AI-controlled countries in the gamestate.

    Returns a list of ``(country_id, country_dict)`` tuples.
    Skips primitives, enclaves, and (optionally) Fallen Empires.
    """
    countries = gamestate.get("country", {})
    if not isinstance(countries, dict):
        return []

    # Identify player country IDs to exclude
    player_ids: set[int] = set()
    players = gamestate.get("player", [])
    if isinstance(players, list):
        for p in players:
            if isinstance(p, dict) and p.get("country") is not None:
                player_ids.add(int(p["country"]))

    exclude_set = set(exclude_ids or []) | player_ids

    # Country types that are NOT real empires
    skip_types = {"primitive", "enclave", "rebel", "pirate", "caravaneer"}
    if exclude_fallen:
        skip_types.add("fallen_empire")
        skip_types.add("awakened_fallen_empire")

    result = []
    for cid_str, country in countries.items():
        if not isinstance(country, dict):
            continue
        try:
            cid = int(cid_str)
        except (ValueError, TypeError):
            continue

        if cid in exclude_set:
            continue

        if include_ids and cid not in include_ids:
            continue

        country_type = str(country.get("type", "")).lower()
        if country_type in skip_types:
            continue

        # Must be a real empire type
        if country_type not in ("default", "ai_empire", "fallen_empire",
                                 "awakened_fallen_empire", ""):
            continue

        result.append((cid, country))

    return result


def _get_country_display_name(country: dict, fallback: str) -> str:
    """Extract a display name from a country dict.

    Stellaris saves often store names as localization templates like
    ``%ADJECTIVE% Empire``.  When we can't resolve those, fall back to
    the government type + country ID for readability.
    """
    name = country.get("name", "")
    if isinstance(name, dict):
        # Complex name with key + variables
        key = name.get("key", "")
        # Reject unresolved localization templates
        if key and "%" not in key:
            return str(key)
        # Try variables for a resolved value
        variables = name.get("variables", [])
        if isinstance(variables, list):
            for var in variables:
                if isinstance(var, dict):
                    val = var.get("value", "")
                    if isinstance(val, str) and val and "%" not in val:
                        return val
                    if isinstance(val, dict):
                        inner_key = val.get("key", "")
                        if inner_key and "%" not in inner_key:
                            return inner_key
    if isinstance(name, str) and name and "%" not in name:
        return name

    # Fall back to government type + ID
    gov = country.get("government", {})
    gov_type = ""
    if isinstance(gov, dict):
        gov_type = str(gov.get("type", ""))
    if gov_type:
        return f"{gov_type}#{fallback}"
    return f"Empire_{fallback}"


# ------------------------------------------------------------------ #
# Data extractors
# ------------------------------------------------------------------ #

def _parse_date(date_str) -> tuple[int, int]:
    """Parse '2230.06.15' into (2230, 6)."""
    if isinstance(date_str, str):
        parts = date_str.split(".")
        try:
            return int(parts[0]), int(parts[1]) if len(parts) > 1 else 1
        except (ValueError, IndexError):
            pass
    return 2200, 1


def _extract_empire_info(country: dict, player_name: str) -> dict:
    """Extract basic empire identity."""
    ethics_raw = country.get("ethos", {})
    ethics = []
    if isinstance(ethics_raw, dict):
        ethic_list = ethics_raw.get("ethic", [])
        if isinstance(ethic_list, str):
            ethics = [ethic_list]
        elif isinstance(ethic_list, list):
            ethics = [str(e) for e in ethic_list]

    gov = country.get("government", {})
    if not isinstance(gov, dict):
        gov = {}

    # Civics: can be a list directly or a dict with "civic" key
    civics_raw = gov.get("civics", {})
    civics = []
    if isinstance(civics_raw, list):
        civics = [str(c) for c in civics_raw]
    elif isinstance(civics_raw, dict):
        civic_list = civics_raw.get("civic", [])
        if isinstance(civic_list, str):
            civics = [civic_list]
        elif isinstance(civic_list, list):
            civics = [str(c) for c in civic_list]

    # Origin: inside government block
    origin = gov.get("origin", "")

    gov_type = str(gov.get("type", ""))

    return {
        "name": player_name,
        "ethics": ethics,
        "civics": civics,
        "origin": str(origin),
        "government": gov_type,
    }


def _extract_economy(country: dict) -> dict:
    """Extract resource stockpiles and monthly income/expenses."""
    # Resource stockpiles are in modules.standard_economy_module.resources
    res: dict = {}
    modules = country.get("modules", {})
    if isinstance(modules, dict):
        econ_mod = modules.get("standard_economy_module", {})
        if isinstance(econ_mod, dict):
            res = econ_mod.get("resources", {})
    if not isinstance(res, dict):
        res = {}

    def _get_resource(name: str) -> float:
        val = res.get(name, 0)
        if isinstance(val, (int, float)):
            return float(val)
        return 0.0

    economy: dict = {
        "energy": _get_resource("energy"),
        "minerals": _get_resource("minerals"),
        "food": _get_resource("food"),
        "alloys": _get_resource("alloys"),
        "consumer_goods": _get_resource("consumer_goods"),
        "influence": _get_resource("influence"),
        "unity": _get_resource("unity"),
    }

    # Rare/strategic resources
    for rare in ("exotic_gases", "volatile_motes", "rare_crystals",
                 "dark_matter", "zro", "living_metal", "nanites"):
        val = _get_resource(rare)
        if val > 0:
            economy[rare] = val

    # Monthly income/expenses from budget
    # Budget.last_month.income is keyed by SOURCE (country_base, planet_jobs, etc.),
    # each containing a dict of resource→amount. Sum across all sources.
    budget = country.get("budget", {})
    if isinstance(budget, dict):
        last_month = budget.get("last_month", {})
        if isinstance(last_month, dict):
            income_by_source = last_month.get("income", {})
            expenses_by_source = last_month.get("expenses", {})
            if isinstance(income_by_source, dict) and isinstance(expenses_by_source, dict):
                income_totals: dict[str, float] = {}
                expense_totals: dict[str, float] = {}
                for _src, amounts in income_by_source.items():
                    if isinstance(amounts, dict):
                        for rname, rval in amounts.items():
                            if isinstance(rval, (int, float)):
                                income_totals[rname] = income_totals.get(rname, 0) + float(rval)
                for _src, amounts in expenses_by_source.items():
                    if isinstance(amounts, dict):
                        for rname, rval in amounts.items():
                            if isinstance(rval, (int, float)):
                                expense_totals[rname] = expense_totals.get(rname, 0) + float(rval)

                monthly: dict = {}
                for key in ("energy", "minerals", "food", "alloys",
                            "consumer_goods", "influence", "unity"):
                    inc = income_totals.get(key, 0)
                    exp = expense_totals.get(key, 0)
                    monthly[key] = round(inc - exp, 1)
                if monthly:
                    economy["monthly_net"] = monthly

    return economy


def _extract_fleets(gamestate: dict, player_country: dict) -> list[dict]:
    """Extract player's fleet information.

    Fleet ownership is tracked via ``country.fleets_manager.owned_fleets``,
    not via a fleet's ``owner`` field (which may not exist).
    """
    fleets_out: list[dict] = []
    all_fleets = gamestate.get("fleet", {})

    if not isinstance(all_fleets, dict):
        return fleets_out

    # Get owned fleet IDs from the country's fleets_manager
    owned_fleet_ids: set[int] = set()
    fm = player_country.get("fleets_manager", {})
    if isinstance(fm, dict):
        owned = fm.get("owned_fleets", [])
        if isinstance(owned, list):
            for entry in owned:
                if isinstance(entry, dict):
                    fid = entry.get("fleet")
                    if isinstance(fid, int):
                        owned_fleet_ids.add(fid)
                elif isinstance(entry, int):
                    owned_fleet_ids.add(entry)

    for fid_str, fleet in all_fleets.items():
        if not isinstance(fleet, dict):
            continue

        # Check ownership
        try:
            fid_int = int(fid_str)
        except (ValueError, TypeError):
            continue
        if fid_int not in owned_fleet_ids:
            continue

        # Skip civilian and starbase fleets
        if fleet.get("civilian", False):
            continue
        ship_class = fleet.get("ship_class", "")
        if ship_class in ("shipclass_starbase", "shipclass_transport"):
            continue

        name = fleet.get("name", "Fleet")
        if isinstance(name, dict):
            name = name.get("key", "Fleet")

        power = fleet.get("military_power", 0)
        if isinstance(power, (int, float)):
            power = int(power)
        else:
            power = 0

        # Get location
        location = ""
        movement = fleet.get("movement_manager", {})
        if isinstance(movement, dict):
            coord = movement.get("coordinate", {})
            if isinstance(coord, dict):
                location = str(coord.get("origin", ""))

        # Ship count and composition
        ships = fleet.get("ships", {})
        ship_count = 0
        if isinstance(ships, dict):
            ship_count = len(ships)
        elif isinstance(ships, list):
            ship_count = len(ships)

        fleet_entry: dict = {
            "name": str(name),
            "power": power,
            "location_system": location,
            "ship_count": ship_count,
        }

        # Fleet stance
        stance = fleet.get("fleet_stance", "")
        if stance:
            fleet_entry["stance"] = str(stance)

        fleets_out.append(fleet_entry)

    return fleets_out


def _extract_colonies(
    gamestate: dict, player_country: dict,
) -> list[dict]:
    """Extract detailed information about owned planets."""
    colonies: list[dict] = []
    owned_planets = player_country.get("owned_planets", [])
    if not isinstance(owned_planets, (list, tuple)):
        return colonies

    planet_db = gamestate.get("planets", {})
    if isinstance(planet_db, dict):
        planet_db = planet_db.get("planet", planet_db)
    if not isinstance(planet_db, dict):
        return colonies

    for pid in owned_planets:
        planet = planet_db.get(str(pid), {})
        if not isinstance(planet, dict):
            continue

        name = planet.get("name", f"Planet_{pid}")
        if isinstance(name, dict):
            name = name.get("key", f"Planet_{pid}")

        # Districts
        districts_raw = planet.get("districts", [])
        district_count = 0
        if isinstance(districts_raw, list):
            district_count = len(districts_raw)
        elif isinstance(districts_raw, dict):
            district_count = len(districts_raw)

        # Pops (from num_sapient_pops or pop_groups)
        pops = planet.get("num_sapient_pops", 0)
        if not isinstance(pops, (int, float)):
            pops = 0

        # Stability
        stability = planet.get("stability", 0)
        if not isinstance(stability, (int, float)):
            stability = 0

        colony: dict = {
            "name": str(name),
            "planet_class": str(planet.get("planet_class", "")),
            "planet_size": int(planet.get("planet_size", 0))
            if isinstance(planet.get("planet_size"), (int, float))
            else 0,
            "designation": str(
                planet.get("final_designation",
                           planet.get("designation", ""))
            ),
            "pops": int(pops),
            "districts": district_count,
            "stability": round(float(stability), 1),
        }

        # Crime
        crime = planet.get("crime", 0)
        if isinstance(crime, (int, float)) and crime > 0:
            colony["crime"] = round(float(crime), 1)

        # Free housing
        free_housing = planet.get("free_housing", 0)
        if isinstance(free_housing, (int, float)):
            colony["free_housing"] = int(free_housing)

        colonies.append(colony)

    return colonies


def _extract_known_empires(
    gamestate: dict, player_country: dict,
) -> list[dict]:
    """Extract info about known foreign empires, filtered by intel level."""
    known = []
    relations = player_country.get("relations_manager", {})
    if not isinstance(relations, dict):
        relations = {}

    relation_list = relations.get("relation", [])
    if isinstance(relation_list, dict):
        relation_list = [relation_list]

    countries = gamestate.get("country", {})
    if not isinstance(countries, dict):
        return known

    for rel in relation_list:
        if not isinstance(rel, dict):
            continue
        target_id = rel.get("country")
        if target_id is None:
            continue

        other = countries.get(str(target_id), {})
        if not isinstance(other, dict):
            continue
        if other.get("type", "") != "default":
            continue

        # Get intel level
        intel = _get_intel_level(rel)
        intel_label = _intel_to_label(intel)

        name = other.get("name", f"Empire_{target_id}")
        if isinstance(name, dict):
            name = name.get("key", f"Empire_{target_id}")

        attitude = str(rel.get("attitude", "neutral"))

        entry: dict = {
            "name": str(name),
            "attitude": attitude,
            "intel_level": intel_label,
        }

        # Add data based on intel level (fog-of-war filtering)
        if intel >= 10:  # Low
            gov = other.get("government", {})
            if isinstance(gov, dict):
                entry["government"] = str(gov.get("type", ""))

        if intel >= 30:  # Medium
            entry["known_fleet_power"] = _estimate_fleet_power(
                gamestate, str(target_id),
            )

        if intel >= 60:  # High
            entry["economy_class"] = _estimate_economy_class(other)

        known.append(entry)

    return known


# ------------------------------------------------------------------ #
# Intel / Fog-of-war helpers
# ------------------------------------------------------------------ #

def _get_intel_level(relation: dict) -> int:
    """Extract intel level from a relation entry."""
    intel = relation.get("intel", {})
    if isinstance(intel, dict):
        return int(intel.get("intel", 0))
    if isinstance(intel, (int, float)):
        return int(intel)
    return 0


def _intel_to_label(intel: int) -> str:
    """Convert numeric intel to a label."""
    for threshold in sorted(INTEL_LEVELS.keys(), reverse=True):
        if intel >= threshold:
            return INTEL_LEVELS[threshold]
    return "none"


def _estimate_fleet_power(gamestate: dict, country_id: str) -> int | str:
    """Estimate fleet power for a foreign empire (requires medium intel)."""
    total = 0
    all_fleets = gamestate.get("fleet", {})
    if not isinstance(all_fleets, dict):
        return "Unknown"
    for _fid, fleet in all_fleets.items():
        if not isinstance(fleet, dict):
            continue
        if str(fleet.get("owner")) == country_id:
            power = fleet.get("military_power", 0)
            if isinstance(power, (int, float)):
                total += int(power)
    return total if total > 0 else "Unknown"


def _estimate_economy_class(country: dict) -> str:
    """Classify economy strength (requires high intel)."""
    res = country.get("resources", {})
    if not isinstance(res, dict):
        return "Unknown"
    energy = res.get("energy", 0)
    minerals = res.get("minerals", 0)
    if isinstance(energy, (int, float)) and isinstance(minerals, (int, float)):
        total = energy + minerals
        if total > 10000:
            return "Overwhelming"
        if total > 5000:
            return "Superior"
        if total > 2000:
            return "Equivalent"
        if total > 500:
            return "Inferior"
        return "Pathetic"
    return "Unknown"


# ------------------------------------------------------------------ #
# New extractors: tech, traditions, policies, wars
# ------------------------------------------------------------------ #

def _extract_technology(country: dict) -> dict:
    """Extract researched techs and current research queues."""
    tech_status = country.get("tech_status", {})
    if not isinstance(tech_status, dict):
        return {"researched": [], "in_progress": {}}

    # Researched technologies (parallel arrays: technology[], level[])
    researched_raw = tech_status.get("technology", [])
    researched: list[str] = []
    if isinstance(researched_raw, list):
        researched = [str(t) for t in researched_raw]
    elif isinstance(researched_raw, str):
        researched = [researched_raw]

    # Currently researching
    in_progress: dict[str, str] = {}
    for field in ("physics_queue", "society_queue", "engineering_queue"):
        queue = tech_status.get(field, [])
        if isinstance(queue, list) and queue:
            entry = queue[0]
            if isinstance(entry, dict):
                tech = entry.get("technology", "")
                if tech:
                    category = field.replace("_queue", "")
                    in_progress[category] = str(tech)
        elif isinstance(queue, dict):
            tech = queue.get("technology", "")
            if tech:
                category = field.replace("_queue", "")
                in_progress[category] = str(tech)

    return {
        "researched": researched,
        "in_progress": in_progress,
        "count": len(researched),
    }


def _extract_traditions(country: dict) -> list[str]:
    """Extract completed traditions."""
    traditions_raw = country.get("traditions", [])
    if isinstance(traditions_raw, list):
        return [str(t) for t in traditions_raw]
    if isinstance(traditions_raw, str):
        return [traditions_raw]
    return []


def _extract_ascension_perks(country: dict) -> list[str]:
    """Extract taken ascension perks."""
    perks_raw = country.get("ascension_perks", [])
    if isinstance(perks_raw, list):
        return [str(p) for p in perks_raw]
    if isinstance(perks_raw, str):
        return [perks_raw]
    return []


def _extract_policies(country: dict) -> list[dict]:
    """Extract active policies.

    Returns list of ``{"policy": str, "selected": str}``.
    """
    policies_raw = country.get("active_policies", [])
    policies: list[dict] = []
    if isinstance(policies_raw, list):
        for p in policies_raw:
            if isinstance(p, dict):
                policy = str(p.get("policy", ""))
                selected = str(p.get("selected", ""))
                if policy:
                    policies.append({
                        "policy": policy,
                        "selected": selected,
                    })
    return policies


def _extract_edicts(country: dict) -> list[str]:
    """Extract active edicts (just the edict names)."""
    edicts_raw = country.get("edicts", [])
    edicts: list[str] = []
    if isinstance(edicts_raw, list):
        for e in edicts_raw:
            if isinstance(e, dict):
                name = e.get("edict", "")
                if name:
                    edicts.append(str(name))
            elif isinstance(e, str):
                edicts.append(e)
    return edicts


def _extract_wars(
    gamestate: dict, player_country_id: str,
) -> list[dict]:
    """Extract active wars involving the player."""
    wars_block = gamestate.get("war", {})
    if not isinstance(wars_block, dict):
        return []

    player_cid = int(player_country_id) if player_country_id.isdigit() else -1
    active_wars: list[dict] = []

    for _wid, war in wars_block.items():
        if not isinstance(war, dict):
            continue

        attackers = war.get("attackers", [])
        defenders = war.get("defenders", [])
        if not isinstance(attackers, list):
            attackers = [attackers] if isinstance(attackers, dict) else []
        if not isinstance(defenders, list):
            defenders = [defenders] if isinstance(defenders, dict) else []

        # Check if player is involved
        player_side = ""
        for a in attackers:
            if isinstance(a, dict) and a.get("country") == player_cid:
                player_side = "attacker"
                break
        if not player_side:
            for d in defenders:
                if isinstance(d, dict) and d.get("country") == player_cid:
                    player_side = "defender"
                    break

        if not player_side:
            continue  # Not our war

        # War goal
        goal_key = "attacker_war_goal" if player_side == "attacker" else "defender_war_goal"
        war_goal_raw = war.get(goal_key, {})
        war_goal = ""
        if isinstance(war_goal_raw, dict):
            war_goal = str(war_goal_raw.get("type", ""))

        # War exhaustion
        exh_key = f"{player_side}_war_exhaustion"
        exhaustion = war.get(exh_key, 0)
        if not isinstance(exhaustion, (int, float)):
            exhaustion = 0

        active_wars.append({
            "side": player_side,
            "war_goal": war_goal,
            "war_exhaustion": round(float(exhaustion), 2),
            "start_date": str(war.get("start_date", "")),
        })

    return active_wars


def _extract_starbases(
    gamestate: dict, player_country: dict,
) -> list[dict]:
    """Extract player's starbases with modules and buildings.

    Ownership is determined by matching each starbase's ``station``
    fleet ID against the country's ``fleets_manager.owned_fleets``.
    """
    player_fleet_ids: set[int] = set()
    fm = player_country.get("fleets_manager", {})
    if isinstance(fm, dict):
        owned = fm.get("owned_fleets", [])
        if isinstance(owned, list):
            for entry in owned:
                if isinstance(entry, dict):
                    fid = entry.get("fleet")
                    if isinstance(fid, int):
                        player_fleet_ids.add(fid)
                elif isinstance(entry, int):
                    player_fleet_ids.add(entry)

    sbm = gamestate.get("starbase_mgr", {})
    all_starbases = sbm.get("starbases", {})
    if not isinstance(all_starbases, dict):
        return []

    starbases: list[dict] = []
    for _sid, sb in all_starbases.items():
        if not isinstance(sb, dict):
            continue
        station = sb.get("station")
        if not isinstance(station, int) or station not in player_fleet_ids:
            continue

        level = str(sb.get("level", ""))
        # Skip outpost-level starbases (not upgraded)
        if level == "starbase_level_outpost":
            continue

        # Modules
        modules_raw = sb.get("modules", {})
        modules: list[str] = []
        if isinstance(modules_raw, dict):
            modules = [str(v) for v in modules_raw.values() if isinstance(v, str)]
        elif isinstance(modules_raw, list):
            modules = [str(v) for v in modules_raw]

        # Buildings
        buildings_raw = sb.get("buildings", {})
        buildings: list[str] = []
        if isinstance(buildings_raw, dict):
            buildings = [str(v) for v in buildings_raw.values() if isinstance(v, str)]
        elif isinstance(buildings_raw, list):
            buildings = [str(v) for v in buildings_raw]

        # System name from station fleet
        system_name = ""
        fleet = gamestate.get("fleet", {}).get(str(station), {})
        if isinstance(fleet, dict):
            mm = fleet.get("movement_manager", {})
            if isinstance(mm, dict):
                coord = mm.get("coordinate", {})
                if isinstance(coord, dict):
                    sys_id = coord.get("origin")
                    if sys_id is not None:
                        go = gamestate.get("galactic_object", {}).get(str(sys_id), {})
                        if isinstance(go, dict):
                            name = go.get("name", {})
                            if isinstance(name, dict):
                                system_name = str(name.get("key", ""))
                            elif isinstance(name, str):
                                system_name = name

        entry: dict = {
            "system": system_name,
            "level": level.replace("starbase_level_", ""),
        }
        if modules:
            entry["modules"] = modules
        if buildings:
            entry["buildings"] = buildings

        starbases.append(entry)

    return starbases


def _extract_leaders(
    gamestate: dict, player_country: dict,
) -> list[dict]:
    """Extract player's leaders (class, level, traits)."""
    leaders_db = gamestate.get("leaders", {})
    if not isinstance(leaders_db, dict):
        return []

    owned_raw = player_country.get("owned_leaders", [])
    owned_ids: list = []
    if isinstance(owned_raw, list):
        owned_ids = owned_raw
    elif isinstance(owned_raw, (int, str)):
        owned_ids = [owned_raw]

    leaders: list[dict] = []
    for lid in owned_ids:
        leader = leaders_db.get(str(lid), {})
        if not isinstance(leader, dict):
            continue

        cls = str(leader.get("class", ""))
        level = leader.get("level", 0)
        if not isinstance(level, int):
            level = 0

        traits_raw = leader.get("traits", [])
        traits: list[str] = []
        if isinstance(traits_raw, list):
            traits = [str(t) for t in traits_raw]
        elif isinstance(traits_raw, str):
            traits = [traits_raw]

        leaders.append({
            "class": cls,
            "level": level,
            "traits": traits,
        })

    return leaders


def _extract_capacity(country: dict) -> dict:
    """Extract naval capacity and empire size."""
    result: dict = {}
    for key in ("used_naval_capacity", "starbase_capacity", "empire_size"):
        val = country.get(key)
        if isinstance(val, (int, float)):
            result[key] = int(val)
    return result


# ------------------------------------------------------------------ #
# Event detection
# ------------------------------------------------------------------ #

def _detect_events(prev: dict, curr: dict) -> str | None:
    """Compare two state snapshots to detect what changed."""
    prev_empires = {e["name"] for e in prev.get("known_empires", [])}
    curr_empires = {e["name"] for e in curr.get("known_empires", [])}

    # New empire contact
    new_contacts = curr_empires - prev_empires
    if new_contacts:
        return "BORDER_CONTACT_NEW_EMPIRE"

    # War started (new war in our wars list)
    prev_wars = len(prev.get("wars", []))
    curr_wars = len(curr.get("wars", []))
    if curr_wars > prev_wars:
        return "WAR_DECLARED"

    # Also detect via attitude change (legacy)
    for emp in curr.get("known_empires", []):
        name = emp["name"]
        prev_emp = next(
            (e for e in prev.get("known_empires", []) if e["name"] == name),
            None,
        )
        if prev_emp and prev_emp.get("attitude") != "hostile" and emp.get("attitude") == "hostile":
            return "WAR_DECLARED"

    # Colony gained
    prev_colony_names = {c["name"] if isinstance(c, dict) else c
                         for c in prev.get("colonies", [])}
    curr_colony_names = {c["name"] if isinstance(c, dict) else c
                         for c in curr.get("colonies", [])}
    if curr_colony_names - prev_colony_names:
        return "COLONY_ESTABLISHED"

    # Economy crash (any resource dropped below 0)
    prev_eco = prev.get("economy", {})
    curr_eco = curr.get("economy", {})
    for resource in ("energy", "minerals", "food"):
        if curr_eco.get(resource, 0) < 0 and prev_eco.get(resource, 0) >= 0:
            return "ECONOMY_DEFICIT"

    # Fleet power change > 30%
    prev_power = sum(f.get("power", 0) for f in prev.get("fleets", []))
    curr_power = sum(f.get("power", 0) for f in curr.get("fleets", []))
    if prev_power > 0 and curr_power < prev_power * 0.7:
        return "FLEET_LOST"

    # New tech researched
    prev_techs = set(prev.get("technology", {}).get("researched", []))
    curr_techs = set(curr.get("technology", {}).get("researched", []))
    if curr_techs - prev_techs:
        return "TECH_RESEARCHED"

    return "HEARTBEAT"
