"""End-to-end test: read a real Stellaris save through the full pipeline."""
from __future__ import annotations
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.save_reader import SaveReader, SaveWatcherConfig


def main() -> None:
    save_dir = Path(
        r"C:\Users\Fintz\OneDrive\Documents\Paradox Interactive\Stellaris\save games"
    )
    reader = SaveReader(SaveWatcherConfig(save_dir=save_dir))
    
    # Force read (reset mtime)
    reader._last_mtime = 0.0
    state = reader.read_state()
    
    if state is None:
        print("ERROR: No state returned!")
        return
    
    print("=== STATE SNAPSHOT ===")
    print(f"Version: {state['version']}")
    print(f"Year: {state['year']}.{state['month']:02d}")
    print(f"Empire: {state['empire']['name']}")
    print(f"  Ethics: {state['empire']['ethics']}")
    print(f"  Civics: {state['empire']['civics']}")
    print(f"  Origin: {state['empire']['origin']}")
    print(f"  Government: {state['empire']['government']}")
    
    eco = state['economy']
    print(f"\nEconomy:")
    for k, v in eco.items():
        if k == "monthly_net":
            print(f"  Monthly net: {v}")
        elif isinstance(v, float):
            print(f"  {k}: {v:.0f}")
        else:
            print(f"  {k}: {v}")
    
    print(f"\nFleets: {len(state['fleets'])} total")
    for f in state['fleets'][:3]:
        print(f"  {f['name']}: power={f['power']}, ships={f.get('ship_count', '?')}")
    
    print(f"\nColonies: {len(state['colonies'])}")
    for c in state['colonies'][:5]:
        print(f"  {c['name']}: {c['planet_class']} size={c['planet_size']} "
              f"pops={c['pops']} stability={c['stability']} "
              f"designation={c['designation']}")
    
    print(f"\nKnown empires: {len(state['known_empires'])}")
    for e in state['known_empires'][:3]:
        print(f"  {e['name']}: {e['attitude']} (intel={e['intel_level']})")
    
    tech = state['technology']
    print(f"\nTechnology: {tech['count']} researched")
    print(f"  Sample: {tech['researched'][:5]}")
    print(f"  Researching: {tech['in_progress']}")
    
    print(f"\nTraditions ({len(state['traditions'])}): {state['traditions']}")
    print(f"Ascension Perks: {state['ascension_perks']}")
    
    print(f"\nPolicies ({len(state['policies'])}):")
    for p in state['policies'][:5]:
        print(f"  {p['policy']}: {p['selected']}")
    
    print(f"\nEdicts: {state['edicts']}")
    print(f"Wars: {state['wars']}")
    print(f"Event: {state['event']}")
    print(f"Actions: {state['available_actions']}")
    
    print(f"\nStarbases ({len(state.get('starbases', []))}):")
    for sb in state.get("starbases", []):
        print(f"  {sb.get('system', '?')}: {sb.get('level', '?')} modules={sb.get('modules', [])}")
    
    print(f"\nLeaders ({len(state.get('leaders', []))}):")
    for ld in state.get("leaders", [])[:5]:
        print(f"  {ld['class']} level={ld['level']} traits={ld.get('traits', [])}")
    
    print(f"\nNaval Capacity: {state.get('naval_capacity', {})}")
    
    print(f"\n=== JSON SIZE: {len(json.dumps(state))} chars ===")


if __name__ == "__main__":
    main()
