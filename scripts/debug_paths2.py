"""Debug fleet ownership and budget income structure."""
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

# Find fleet ownership
print("=== FLEET OWNERSHIP ===")
# Check fleets_manager
fm = c0.get("fleets_manager", {})
print(f"fleets_manager: type={type(fm).__name__}")
if isinstance(fm, dict):
    print(f"  keys: {sorted(fm.keys())[:10]}")
    owned = fm.get("owned_fleets", [])
    print(f"  owned_fleets: {owned[:10]}")

# Check owned_fleets directly
owned_fleets = c0.get("owned_fleets", [])
print(f"owned_fleets (direct): type={type(owned_fleets).__name__}")
if isinstance(owned_fleets, list):
    print(f"  first 5: {owned_fleets[:5]}")

# Check fleet_manager
flm = c0.get("fleet_manager", {})
if isinstance(flm, dict):
    print(f"fleet_manager: {sorted(flm.keys())[:10]}")

# Check what keys a fleet actually has
print("\n=== FLEET STRUCTURE ===")
all_fleets = gs.get("fleet", {})
# Check first fleet that has data
for fid in sorted(all_fleets.keys())[:5]:
    f = all_fleets[fid]
    if isinstance(f, dict) and len(f) > 3:
        print(f"\nFleet {fid}:")
        for k in sorted(f.keys())[:20]:
            v = f[k]
            if isinstance(v, (str, int, float, bool)):
                print(f"  {k}: {v}")
            elif isinstance(v, list):
                print(f"  {k}: list({len(v)})")
            elif isinstance(v, dict):
                print(f"  {k}: dict({len(v)})")
        break

# Budget income structure
print("\n=== BUDGET INCOME STRUCTURE ===")
budget = c0.get("budget", {})
lm = budget.get("last_month", {})
if isinstance(lm, dict):
    income = lm.get("income", {})
    if isinstance(income, dict):
        # Look at first income source to see structure
        for source_key, source_val in list(income.items())[:3]:
            print(f"\nincome['{source_key}']: type={type(source_val).__name__}")
            if isinstance(source_val, dict):
                print(f"  keys: {sorted(source_val.keys())[:10]}")
                for rk, rv in list(source_val.items())[:5]:
                    print(f"    {rk}: {rv}")
            elif isinstance(source_val, (int, float)):
                print(f"  value: {source_val}")
    
    # Balance should be the net
    balance = lm.get("balance", {})
    print(f"\nbalance: type={type(balance).__name__}")
    if isinstance(balance, dict):
        print(f"  keys: {sorted(balance.keys())[:15]}")
        for k in ("energy", "minerals", "food", "alloys", "consumer_goods", "unity"):
            print(f"    {k}: {balance.get(k)}")

# Economy module resources
print("\n=== ECONOMY MODULE RESOURCES ===")
modules = c0.get("modules", {})
econ = modules.get("standard_economy_module", {}) if isinstance(modules, dict) else {}
if isinstance(econ, dict):
    res = econ.get("resources", {})
    if isinstance(res, dict):
        for k in ("energy", "minerals", "food", "alloys", "consumer_goods", 
                   "influence", "unity", "exotic_gases", "volatile_motes", 
                   "rare_crystals", "dark_matter", "zro", "living_metal"):
            v = res.get(k)
            if v is not None:
                print(f"  {k}: {v}")
