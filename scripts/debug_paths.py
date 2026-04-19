"""Debug resource, fleet, civic extraction paths."""
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

# Resources
print("=== RESOURCES ===")
res = c0.get("resources", {})
print(f"type: {type(res).__name__}")
if isinstance(res, dict):
    print(f"keys: {sorted(res.keys())[:15]}")
    for k in ("energy", "minerals", "food", "alloys", "consumer_goods"):
        print(f"  {k}: {res.get(k)}")
elif isinstance(res, list):
    print(f"list of {len(res)} items, first: {res[:3]}")

# Budget / income
print("\n=== BUDGET ===")
budget = c0.get("budget", {})
if isinstance(budget, dict):
    print(f"keys: {sorted(budget.keys())}")
    lm = budget.get("last_month", {})
    if isinstance(lm, dict):
        print(f"last_month keys: {sorted(lm.keys())}")
        inc = lm.get("income", {})
        print(f"income type: {type(inc).__name__}")
        if isinstance(inc, dict):
            print(f"income keys: {sorted(inc.keys())[:10]}")
            for k in ("energy", "minerals", "alloys"):
                print(f"  {k}: {inc.get(k)}")
        elif isinstance(inc, list):
            print(f"income is list({len(inc)}), first: {inc[:3]}")

# Modules / economy module
print("\n=== MODULES ===")
modules = c0.get("modules", {})
if isinstance(modules, dict):
    econ = modules.get("standard_economy_module", {})
    if isinstance(econ, dict):
        res2 = econ.get("resources", {})
        print(f"economy_module.resources: {type(res2).__name__}")
        if isinstance(res2, dict):
            print(f"  keys: {sorted(res2.keys())[:10]}")

# Fleets
print("\n=== FLEETS ===")
fleets = gs.get("fleet", {})
print(f"Total fleet entries: {len(fleets)}")
player_fleets = 0
for fid, f in fleets.items():
    if not isinstance(f, dict):
        continue
    owner = f.get("owner")
    if owner == 0:
        name = f.get("name", "?")
        if isinstance(name, dict):
            name = name.get("key", "?")
        power = f.get("military_power", 0)
        civ = f.get("civilian", False)
        print(f"  Fleet {fid}: name={name} power={power} civilian={civ}")
        player_fleets += 1
        if player_fleets >= 5:
            break
if player_fleets == 0:
    # Show first few to see owner format
    count = 0
    for fid, f in fleets.items():
        if not isinstance(f, dict):
            continue
        owner = f.get("owner")
        print(f"  fleet {fid}: owner={owner!r} type={type(owner).__name__}")
        count += 1
        if count >= 5:
            break

# Government/Origin/Civics
print("\n=== GOVERNMENT ===")
gov = c0.get("government", {})
if isinstance(gov, dict):
    print(f"keys: {sorted(gov.keys())}")
    print(f"origin: {gov.get('origin')}")
    civics = gov.get("civics", {})
    print(f"civics: {civics}")
    if isinstance(civics, dict):
        print(f"  civic entries: {civics.get('civic', [])}")
# Also check top-level origin
print(f"top-level origin: {c0.get('origin', 'NOT FOUND')}")
