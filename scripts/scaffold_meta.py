"""
Scaffold a new meta file for a Stellaris patch version.

Usage:
    python scripts/scaffold_meta.py 4.4.0
    python scripts/scaffold_meta.py 4.4.0 --from 4.3.4
    python scripts/scaffold_meta.py --detect   # detect from latest save file

Creates ``docs/meta/X.Y.Z.json`` with the structure pre-filled from
the base version.  You then update the weapon verdicts, fleet templates,
economy rules, etc. based on the patch notes and community testing.

Recommended workflow:
  1. Read the patch notes: stellaris.paradoxwikis.com/Patch_X.Y
  2. Check community builds: stellaris-build.com
  3. Watch combat testing videos (Aktion, etc.)
  4. Run ``python scripts/scaffold_meta.py X.Y.Z``
  5. Edit ``docs/meta/X.Y.Z.json`` with the new meta
  6. Test in a real game before committing
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
META_DIR = PROJECT_ROOT / "docs" / "meta"


def detect_version_from_save() -> str | None:
    """Try to detect game version from the latest save file."""
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from engine.config import load_config
        from engine.clausewitz_parser import parse_save
        from engine.save_reader import detect_game_version

        cfg = load_config()
        save_dir = Path(cfg.bridge.save_dir)
        if not save_dir.exists():
            print(f"Save directory not found: {save_dir}")
            return None

        # Find latest .sav file
        saves = sorted(save_dir.rglob("*.sav"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not saves:
            print("No save files found")
            return None

        raw = parse_save(saves[0])
        version = detect_game_version(raw.get("meta", {}))
        print(f"Detected version: {version} (from {saves[0].name})")
        return version
    except Exception as exc:
        print(f"Could not detect version: {exc}")
        return None


def scaffold(version: str, base_version: str | None = None) -> None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    target = META_DIR / f"{version}.json"

    if target.exists():
        print(f"Meta file already exists: {target}")
        print("Edit it directly or delete it first.")
        return

    # Find base to copy from
    if base_version:
        base_path = META_DIR / f"{base_version}.json"
    else:
        # Use latest available
        existing = sorted(META_DIR.glob("*.json"))
        base_path = existing[-1] if existing else None

    if base_path and base_path.exists():
        data = json.loads(base_path.read_text(encoding="utf-8"))
        data["version"] = version
        data["patch_name"] = f"TODO — check stellaris.paradoxwikis.com/Patch_{version.rsplit('.', 1)[0]}"
        data["sources"] = [
            f"stellaris.paradoxwikis.com/Patch_{version.rsplit('.', 1)[0]}",
            "stellaris-build.com",
            "TODO — add community testing sources",
        ]
        data["key_changes_from_previous"] = [
            "TODO — read patch notes and list key changes",
        ]
        data.pop("_source", None)
        print(f"Scaffolded from {base_path.name}")
    else:
        # Create minimal template
        data = {
            "version": version,
            "patch_name": "TODO",
            "sources": [
                f"stellaris.paradoxwikis.com/Patch_{version.rsplit('.', 1)[0]}",
                "stellaris-build.com",
            ],
            "weapon_verdicts": {
                "TODO": {"verdict": "TODO", "notes": "Test in game before filling"},
            },
            "forbidden_weapons": [],
            "forbidden_fleet_patterns": [],
            "fleet_templates": {
                "early": {"composition": {}, "notes": "TODO"},
                "mid": {"composition": {}, "notes": "TODO"},
                "late": {"composition": {}, "notes": "TODO"},
            },
            "economy_rules": {
                "early": {"focus": "TODO", "notes": "TODO"},
                "mid": {"focus": "TODO", "notes": "TODO"},
                "late": {"focus": "TODO", "notes": "TODO"},
            },
            "combat_rules": {},
            "crisis_counters": {},
            "origin_tiers": {"S": [], "A": [], "B": [], "C": [], "F": []},
            "ascension_meta": {},
            "key_changes_from_previous": ["TODO"],
            "meta_rules_domestic": "TODO",
            "meta_rules_military": "TODO",
        }
        print("Created from blank template")

    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nCreated: {target}")
    print(f"\nNext steps:")
    print(f"  1. Read patch notes: stellaris.paradoxwikis.com/Patch_{version.rsplit('.', 1)[0]}")
    print(f"  2. Check builds: stellaris-build.com")
    print(f"  3. Edit {target}")
    print(f"  4. Test in a real {version} game")
    print(f"  5. Update engine/ruleset_generator.py GAME_VERSION if needed")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold a new Stellaris meta file for a patch version",
    )
    parser.add_argument(
        "version", nargs="?", default=None,
        help="Target version (e.g. 4.4.0). Use --detect to auto-detect.",
    )
    parser.add_argument(
        "--from", dest="base", default=None,
        help="Base version to copy from (default: latest available)",
    )
    parser.add_argument(
        "--detect", action="store_true",
        help="Detect version from latest save file",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available meta versions",
    )
    args = parser.parse_args()

    if args.list:
        versions = sorted(p.stem for p in META_DIR.glob("*.json"))
        if versions:
            print("Available meta versions:")
            for v in versions:
                print(f"  {v}")
        else:
            print("No meta files found")
        return

    version = args.version
    if args.detect:
        version = detect_version_from_save()
        if not version:
            sys.exit(1)

    if not version:
        parser.error("Provide a version or use --detect")

    scaffold(version, args.base)


if __name__ == "__main__":
    main()
