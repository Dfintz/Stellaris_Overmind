"""Find how starbases link to countries."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.clausewitz_parser import parse_save

raw = parse_save(Path(
    r"C:\Users\Fintz\OneDrive\Documents\Paradox Interactive\Stellaris"
    r"\save games\techarancoalition_-1265884157\ironman.sav"
))
gs = raw["gamestate"]
c0 = gs["country"]["0"]

# Build set of player fleet IDs
player_fleet_ids = set()
fm = c0.get("fleets_manager", {})
if isinstance(fm, dict):
    owned = fm.get("owned_fleets", [])
    if isinstance(owned, list):
        for entry in owned:
            if isinstance(entry, dict):
                fid = entry.get("fleet")
                if isinstance(fid, int):
                    player_fleet_ids.add(fid)

print(f"Player has {len(player_fleet_ids)} fleet IDs")

# Now find starbases whose station is in our fleet set
sbm = gs.get("starbase_mgr", {})
sbs = sbm.get("starbases", {})
player_starbases = []

for sid, sb in sbs.items():
    if not isinstance(sb, dict):
        continue
    station = sb.get("station")
    if isinstance(station, int) and station in player_fleet_ids:
        player_starbases.append((sid, sb))
    elif isinstance(station, list):
        # Station could be a list of fleet IDs?
        for s in station:
            if isinstance(s, int) and s in player_fleet_ids:
                player_starbases.append((sid, sb))
                break

print(f"Player starbases: {len(player_starbases)}")
print(f"Starbase capacity: {c0.get('starbase_capacity')}")
print(f"Upgraded starbases: {c0.get('num_upgraded_starbase')}")

for sid, sb in player_starbases[:5]:
    level = sb.get("level", "?")
    modules = sb.get("modules", {})
    buildings = sb.get("buildings", {})
    sb_type = sb.get("type", "?")
    constr_type = sb.get("construction_type", "?")
    
    # Get system name from station fleet
    station_id = sb.get("station")
    system_name = "?"
    if station_id is not None:
        fleet = gs.get("fleet", {}).get(str(station_id), {})
        if isinstance(fleet, dict):
            # Fleet's movement_manager has coordinate.origin (system ID)
            mm = fleet.get("movement_manager", {})
            if isinstance(mm, dict):
                coord = mm.get("coordinate", {})
                if isinstance(coord, dict):
                    sys_id = coord.get("origin")
                    if sys_id is not None:
                        go = gs.get("galactic_object", {}).get(str(sys_id), {})
                        if isinstance(go, dict):
                            name = go.get("name", {})
                            if isinstance(name, dict):
                                system_name = name.get("key", "?")
                            else:
                                system_name = str(name)

    mod_list = []
    if isinstance(modules, dict):
        mod_list = [str(v) for v in modules.values() if isinstance(v, str)]
    elif isinstance(modules, list):
        mod_list = [str(v) for v in modules]
    
    bldg_list = []
    if isinstance(buildings, dict):
        bldg_list = [str(v) for v in buildings.values() if isinstance(v, str)]
    elif isinstance(buildings, list):
        bldg_list = [str(v) for v in buildings]

    print(f"\n  Starbase {sid} ({system_name}):")
    print(f"    level: {level}")
    print(f"    type: {sb_type} / construction: {constr_type}")
    print(f"    modules: {mod_list}")
    print(f"    buildings: {bldg_list}")
