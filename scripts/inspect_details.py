"""Inspect planet, war, and leader structures from a parsed save."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.clausewitz_parser import parse_save


def deep(d, depth=0, max_depth=2):
    indent = "  " * depth
    if not isinstance(d, dict):
        return
    for k in sorted(d.keys())[:20]:
        v = d[k]
        if isinstance(v, dict):
            print(f"{indent}{k}: dict({len(v)})")
            if depth < max_depth and len(v) < 20:
                deep(v, depth + 1, max_depth)
        elif isinstance(v, list):
            sample = v[:3] if len(v) < 30 else v[:2]
            print(f"{indent}{k}: list({len(v)}) = {sample}")
        else:
            print(f"{indent}{k}: {v}")


def main():
    save_path = Path(
        r"C:\Users\Fintz\OneDrive\Documents\Paradox Interactive\Stellaris"
        r"\save games\techarancoalition_-1265884157\ironman.sav"
    )
    raw = parse_save(save_path)
    gs = raw["gamestate"]
    
    # Player country
    country0 = gs["country"]["0"]
    
    # Planet details
    print("=== PLANET STRUCTURE ===")
    planets_block = gs.get("planets", {})
    print(f"planets top keys: {sorted(planets_block.keys())[:10]}")
    planet_data = planets_block.get("planet", {})
    if not isinstance(planet_data, dict):
        # Try direct
        planet_data = planets_block
    
    # Find player's first planet
    owned = country0.get("owned_planets", [])
    print(f"Player owns planets: {owned}")
    
    if owned:
        pid = str(owned[0])
        planet = planet_data.get(pid) if isinstance(planet_data, dict) else None
        if planet:
            print(f"\n--- Planet {pid} ---")
            deep(planet, max_depth=1)
        else:
            # Planets might be at top level
            planet = gs.get(pid, {})
            if isinstance(planet, dict) and "planet_class" in planet:
                print(f"\n--- Planet {pid} (from top level) ---")
                deep(planet, max_depth=1)
            else:
                print(f"Planet {pid} not found in planets block or top level")
    
    # Wars
    print("\n=== WAR STRUCTURE ===")
    wars = gs.get("war", {})
    print(f"Wars: {len(wars)} entries")
    for wid, war in wars.items():
        if isinstance(war, dict):
            print(f"\n--- War {wid} ---")
            deep(war, max_depth=1)
            break
    
    # Galactic community
    print("\n=== GALACTIC COMMUNITY ===")
    gc = gs.get("galactic_community", {})
    deep(gc, max_depth=2)
    
    # Leaders
    print("\n=== LEADERS (player's) ===")
    leaders_db = gs.get("leaders", {})
    owned_leaders = country0.get("owned_leaders", [])
    print(f"Total leaders: {len(leaders_db)}, Player owns: {owned_leaders}")
    
    if isinstance(owned_leaders, list) and owned_leaders:
        for lid in owned_leaders[:3]:
            leader = leaders_db.get(str(lid), {})
            if isinstance(leader, dict):
                print(f"\n--- Leader {lid} ---")
                deep(leader, max_depth=1)
    
    # Ascension perks
    print("\n=== ASCENSION PERKS ===")
    asc = country0.get("ascension_perks", [])
    print(f"Perks: {asc}")
    
    # Resources (detailed)
    print("\n=== RESOURCES (from budget) ===")
    budget = country0.get("budget", {})
    if isinstance(budget, dict):
        last_month = budget.get("last_month", {})
        if isinstance(last_month, dict):
            print("Last month budget keys:", sorted(last_month.keys())[:10])
            deep(last_month, max_depth=2)
    
    # Check resources directly
    resources = country0.get("resources", {})
    print(f"\nDirect resources: {type(resources).__name__}")
    if isinstance(resources, dict):
        deep(resources, max_depth=1)
    
    # Starbases
    print("\n=== STARBASES ===")
    sbm = gs.get("starbase_mgr", {})
    print(f"starbase_mgr keys: {sorted(sbm.keys())[:5]}")
    starbases = sbm.get("starbases", {})
    if isinstance(starbases, dict):
        print(f"starbases entries: {len(starbases)}")
        for sid, sb in list(starbases.items())[:2]:
            if isinstance(sb, dict):
                print(f"\n--- Starbase {sid} ---")
                deep(sb, max_depth=1)
    
    # Tech details
    print("\n=== TECH STATUS (player) ===")
    ts = country0.get("tech_status", {})
    techs = ts.get("technology", [])
    levels = ts.get("level", [])
    print(f"Researched technologies ({len(techs)}): {techs[:10]}")
    print(f"Levels ({len(levels)}): {levels[:10]}")
    
    # Currently researching
    for queue_key in ("physics_queue", "society_queue", "engineering_queue"):
        q = ts.get(queue_key, [])
        if q and isinstance(q[0], dict):
            print(f"{queue_key}: {q[0]}")


if __name__ == "__main__":
    main()
