"""Inspect a Stellaris save file to discover available data structures."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.clausewitz_parser import parse_save


def show_keys(d: dict, prefix: str = "", depth: int = 0, max_depth: int = 2) -> None:
    """Print keys recursively up to max_depth."""
    if depth > max_depth:
        return
    for key in sorted(d.keys()):
        val = d[key]
        indent = "  " * depth
        if isinstance(val, dict):
            print(f"{indent}{prefix}{key}: dict({len(val)} keys)")
            if depth < max_depth:
                show_keys(val, "", depth + 1, max_depth)
        elif isinstance(val, list):
            print(f"{indent}{prefix}{key}: list({len(val)} items)")
            if val and isinstance(val[0], dict) and depth < max_depth:
                print(f"{indent}  [0] keys: {sorted(val[0].keys())[:15]}")
        else:
            print(f"{indent}{prefix}{key}: {type(val).__name__} = {str(val)[:80]}")


def main() -> None:
    save_path = Path(
        r"C:\Users\Fintz\OneDrive\Documents\Paradox Interactive\Stellaris"
        r"\save games\techarancoalition_-1265884157\ironman.sav"
    )
    print(f"Parsing {save_path.name} ({save_path.stat().st_size / 1024 / 1024:.1f} MB)...")
    raw = parse_save(save_path)

    print("\n=== TOP-LEVEL KEYS ===")
    for section in ("meta", "gamestate"):
        data = raw.get(section, {})
        print(f"\n--- {section} ({len(data)} keys) ---")
        show_keys(data, max_depth=1)

    # Now dig into player country
    gamestate = raw.get("gamestate", {})
    countries = gamestate.get("country", {})
    print(f"\n=== COUNTRIES: {len(countries)} total ===")

    # Find player country (first one usually)
    for cid, country in countries.items():
        if not isinstance(country, dict):
            continue
        name = country.get("name", "")
        if isinstance(name, dict):
            name = name.get("key", "")
        # Check first few countries
        if int(cid) > 3:
            break
        print(f"\n--- Country {cid}: {name} ---")
        show_keys(country, max_depth=1)
        
        # Specifically look for tech, traditions, etc.
        for key in ("tech_status", "traditions", "ascension_perks",
                     "owned_planets", "war", "active_policies",
                     "edicts", "leaders", "starbases", "fleet_manager",
                     "spy_networks", "species", "first_contact",
                     "federation", "galactic_object", "situations",
                     "relics", "technology"):
            if key in country:
                val = country[key]
                if isinstance(val, dict):
                    print(f"  >> {key}: dict keys = {sorted(val.keys())[:20]}")
                elif isinstance(val, list):
                    print(f"  >> {key}: list({len(val)}) first = {val[:3]}")
                else:
                    print(f"  >> {key}: {type(val).__name__} = {str(val)[:100]}")

    # Check top-level gamestate for wars, galcom
    for key in ("war", "galactic_community", "federation",
                "galactic_object", "situation", "truce"):
        if key in gamestate:
            val = gamestate[key]
            if isinstance(val, dict):
                print(f"\ngamestate.{key}: dict({len(val)} keys), sample keys: {sorted(val.keys())[:10]}")
            elif isinstance(val, list):
                print(f"\ngamestate.{key}: list({len(val)})")
            else:
                print(f"\ngamestate.{key}: {type(val).__name__}")

    # Look at planets structure
    planets = gamestate.get("planets", {})
    if isinstance(planets, dict):
        planet_data = planets.get("planet", {})
        if isinstance(planet_data, dict):
            print(f"\n=== PLANETS: {len(planet_data)} total ===")
            # Show first owned planet in detail
            for pid, planet in planet_data.items():
                if not isinstance(planet, dict):
                    continue
                owner = planet.get("owner")
                if owner is not None and str(owner) == "0":
                    print(f"\n--- Player Planet {pid} ---")
                    show_keys(planet, max_depth=1)
                    break


if __name__ == "__main__":
    main()
