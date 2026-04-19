"""Deep inspect of player country to find tech, traditions, wars, etc."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.clausewitz_parser import parse_save


def find_player_country(gamestate: dict, player_name: str) -> tuple[str, dict] | None:
    """Find player country by name."""
    # In Stellaris saves, countries are at the top level with numeric IDs
    # but the parser may flatten them. Let's search systematically.
    
    # Check if there's a "country" key
    countries = gamestate.get("country", {})
    if isinstance(countries, dict):
        for cid, c in countries.items():
            if not isinstance(c, dict):
                continue
            name = c.get("name", "")
            if isinstance(name, dict):
                name = name.get("key", "")
            if player_name.lower() in str(name).lower():
                return (cid, c)
    
    # Try all top-level dicts
    for key, val in gamestate.items():
        if isinstance(val, dict) and "name" in val:
            name = val.get("name", "")
            if isinstance(name, dict):
                name = name.get("key", "")
            if player_name.lower() in str(name).lower():
                return (key, val)
    
    return None


def deep_inspect(d: dict, prefix: str = "", depth: int = 0, max_depth: int = 3) -> None:
    """Show structure deeply."""
    if depth > max_depth:
        return
    indent = "  " * depth
    for key in sorted(d.keys()):
        val = d[key]
        if isinstance(val, dict):
            sub_count = len(val)
            sample_keys = sorted(val.keys())[:8]
            print(f"{indent}{key}: dict({sub_count}) keys={sample_keys}")
            if depth < max_depth and sub_count < 30:
                deep_inspect(val, "", depth + 1, max_depth)
        elif isinstance(val, list):
            print(f"{indent}{key}: list({len(val)})")
            if val and isinstance(val[0], dict) and depth < max_depth:
                print(f"{indent}  [0] = {sorted(val[0].keys())[:10]}")
        elif isinstance(val, str) and len(str(val)) < 100:
            print(f"{indent}{key}: '{val}'")
        elif isinstance(val, (int, float, bool)):
            print(f"{indent}{key}: {val}")
        else:
            print(f"{indent}{key}: {type(val).__name__} ({len(str(val))} chars)")


def main() -> None:
    save_path = Path(
        r"C:\Users\Fintz\OneDrive\Documents\Paradox Interactive\Stellaris"
        r"\save games\techarancoalition_-1265884157\ironman.sav"
    )
    print(f"Parsing {save_path.name}...")
    raw = parse_save(save_path)
    gamestate = raw.get("gamestate", {})
    
    player_name = raw.get("meta", {}).get("name", "")
    print(f"Player name from meta: '{player_name}'")
    
    # The Clausewitz parser seems to flatten numeric keys at the top level
    # Let's check what the structure really looks like
    print(f"\nGamestate has {len(gamestate)} keys")
    
    # Show top-level keys that aren't just numeric IDs
    named_keys = [k for k in gamestate.keys() if not k.isdigit()]
    print(f"\nNamed keys ({len(named_keys)}): {sorted(named_keys)[:50]}")
    
    # Check if country is flat or nested
    country = gamestate.get("country", None)
    if country is not None:
        print(f"\n'country' exists, type={type(country).__name__}")
        if isinstance(country, dict):
            print(f"  has {len(country)} entries")
            for cid in sorted(country.keys())[:3]:
                c = country[cid]
                if isinstance(c, dict):
                    print(f"\n  country[{cid}] keys: {sorted(c.keys())[:20]}...")
                    # Look for tech/tradition keys
                    for search_key in ["tech_status", "technology", "traditions", 
                                       "ascension_perks", "active_policies", "edicts",
                                       "leaders", "fleet_manager", "spy_networks",
                                       "fleet", "war", "starbase", "modules",
                                       "owned_planets", "resources", "budget",
                                       "government", "ethic", "origin", "species_index",
                                       "first_contact", "subjects", "overlord",
                                       "terra_incognita", "sensor_range",
                                       "flags", "modifier", "timed_modifier"]:
                        if search_key in c:
                            val = c[search_key]
                            if isinstance(val, dict):
                                print(f"    ** {search_key}: dict({len(val)}) sample keys: {sorted(val.keys())[:10]}")
                                # Go one deeper for tech_status
                                if search_key == "tech_status" and len(val) < 50:
                                    deep_inspect(val, "", 3, 4)
                            elif isinstance(val, list):
                                print(f"    ** {search_key}: list({len(val)}) sample: {val[:5]}")
                            else:
                                print(f"    ** {search_key}: {type(val).__name__} = {str(val)[:80]}")
                else:
                    print(f"  country[{cid}] = {type(c).__name__}")
    else:
        print("\nNo 'country' key found!")
        # Maybe it's flattened - look for keys that suggest country data
        for key in sorted(gamestate.keys()):
            val = gamestate[key]
            if isinstance(val, dict) and "ethic" in val:
                print(f"  Found country-like at key '{key}'")
                break

    # Check top-level for wars, galcom, etc.
    print("\n=== TOP-LEVEL GAME SYSTEMS ===")
    for key in ["war", "galactic_community", "federation", "situation",
                "truce", "first_contact", "espionage_operation",
                "spy_network", "galactic_object", "starbase_mgr",
                "ship_design", "fleet", "army", "pop",
                "trade_routes", "agreements"]:
        if key in gamestate:
            val = gamestate[key]
            if isinstance(val, dict):
                print(f"  {key}: dict({len(val)}) sample keys: {sorted(val.keys())[:8]}")
            elif isinstance(val, list):
                print(f"  {key}: list({len(val)})")
            else:
                print(f"  {key}: {type(val).__name__}")
    
    # Let's also check what named keys exist at the gamestate root
    print("\n=== ALL NAMED GAMESTATE KEYS ===")
    for key in sorted(named_keys):
        val = gamestate[key]
        tname = type(val).__name__
        if isinstance(val, dict):
            print(f"  {key}: dict({len(val)})")
        elif isinstance(val, list):
            print(f"  {key}: list({len(val)})")
        else:
            print(f"  {key}: {tname} = {str(val)[:60]}")


if __name__ == "__main__":
    main()
