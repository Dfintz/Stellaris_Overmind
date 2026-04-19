"""Inspect starbase + galactic community + leader structures for P1."""
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

# === STARBASES ===
print("=== STARBASES ===")
# Country-level starbase refs
for key in ("starbases", "owned_starbases", "starbase_capacity", "num_upgraded_starbase"):
    val = c0.get(key)
    if val is not None:
        print(f"  country.{key}: {type(val).__name__} = {val}")

# Starbase manager
sbm = gs.get("starbase_mgr", {})
sbs = sbm.get("starbases", {})
print(f"\nstarbase_mgr.starbases: {len(sbs)} entries")

# Find player starbases - need to check which belong to player
# Starbases have a 'station' field pointing to a fleet, and fleets are owned
player_sbs = []
for sid, sb in sbs.items():
    if not isinstance(sb, dict):
        continue
    # Check station -> fleet -> owner via fleets_manager
    station = sb.get("station")
    if station is not None:
        fleet = gs.get("fleet", {}).get(str(station), {})
        if isinstance(fleet, dict):
            # Check if this fleet is in our owned_fleets
            pass
    # Alternative: check owner directly
    owner = sb.get("owner")
    if owner is not None:
        if owner == 0:
            player_sbs.append((sid, sb))
    else:
        # Try to find owner from the system
        pass

print(f"Starbases with owner=0: {len(player_sbs)}")

# Show first 3 player starbases
for sid, sb in player_sbs[:3]:
    print(f"\n  Starbase {sid}:")
    for k in sorted(sb.keys()):
        v = sb[k]
        if isinstance(v, (str, int, float, bool)):
            print(f"    {k}: {v}")
        elif isinstance(v, dict):
            items = dict(list(v.items())[:5])
            print(f"    {k}: dict({len(v)}) = {items}")
        elif isinstance(v, list):
            print(f"    {k}: list({len(v)}) = {v[:3]}")

# If no owner field, check via galactic objects
if not player_sbs:
    print("\nNo owner field found. Checking galactic_objects for starbase links...")
    go = gs.get("galactic_object", {})
    for gid, obj in list(go.items())[:3]:
        if isinstance(obj, dict):
            print(f"  galactic_object {gid}: keys={sorted(obj.keys())[:10]}")

# Check if any starbase has an owner field at all
sample_sb = None
for sid, sb in list(sbs.items())[:5]:
    if isinstance(sb, dict):
        sample_sb = sb
        break
if sample_sb:
    print(f"\nSample starbase keys: {sorted(sample_sb.keys())}")

# === GALACTIC COMMUNITY ===
print("\n\n=== GALACTIC COMMUNITY ===")
gc = gs.get("galactic_community", {})
if isinstance(gc, dict):
    for k in sorted(gc.keys()):
        v = gc[k]
        if isinstance(v, dict):
            print(f"  {k}: dict({len(v)}) keys={sorted(v.keys())[:10]}")
        elif isinstance(v, list):
            print(f"  {k}: list({len(v)}) = {v[:5]}")
        else:
            print(f"  {k}: {v}")

# Check if country has galcom-related data
for key in ("galactic_community", "galcom_member", "galcom_council", 
            "galactic_community_member", "is_galactic_community_member"):
    val = c0.get(key)
    if val is not None:
        print(f"  country.{key}: {val}")

# Look in country flags for galcom hints
flags = c0.get("flags", {})
if isinstance(flags, dict):
    gc_flags = [f for f in flags.keys() if "galactic" in f.lower() or "council" in f.lower() or "custodian" in f.lower()]
    if gc_flags:
        print(f"  country flags (galcom): {gc_flags}")

# === LEADERS ===
print("\n\n=== LEADERS ===")
leaders_db = gs.get("leaders", {})
owned_leaders = c0.get("owned_leaders", [])
print(f"Total leaders: {len(leaders_db)}, Player owns: {len(owned_leaders) if isinstance(owned_leaders, list) else owned_leaders}")

if isinstance(owned_leaders, list):
    for lid in owned_leaders[:5]:
        leader = leaders_db.get(str(lid), {})
        if isinstance(leader, dict):
            name = leader.get("name", "?")
            if isinstance(name, dict):
                fn = name.get("full_names", {})
                if isinstance(fn, dict):
                    name = fn.get("name", name)
            cls = leader.get("class", "?")
            level = leader.get("level", 0)
            traits = leader.get("traits", [])
            print(f"  Leader {lid}: class={cls} level={level} traits={traits}")

# === NAVYCAP & EMPIRE SIZE ===
print("\n\n=== CAPACITY DATA ===")
for key in ("used_naval_capacity", "naval_capacity", "empire_size",
            "starbase_capacity", "admin_cap"):
    val = c0.get(key)
    if val is not None:
        print(f"  {key}: {val}")

# === FEDERATION ===
print("\n\n=== FEDERATION ===")
fed_data = c0.get("federation", {})
print(f"  country.federation: {fed_data}")
fed_top = gs.get("federation", {})
print(f"  gamestate.federation: {len(fed_top)} entries")
if isinstance(fed_top, dict):
    for fid, fed in list(fed_top.items())[:2]:
        if isinstance(fed, dict):
            print(f"    federation {fid}: keys={sorted(fed.keys())[:10]}")
