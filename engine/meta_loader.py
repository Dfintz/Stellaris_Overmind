"""
Meta Loader — Version-aware meta knowledge loading.

Loads curated meta rules from ``docs/meta/`` for the detected game version.
Falls back to the nearest available version if an exact match isn't found.

Meta files are structured JSON covering:
  - Weapon verdicts (what's strong/weak this patch)
  - Fleet composition templates per phase
  - Economy priorities per phase
  - Origin tier list
  - Civic synergies
  - Forbidden patterns (things the LLM must never recommend)

How to add a new version:
  1. Copy ``docs/meta/4.3.4.json`` to ``docs/meta/X.Y.Z.json``
  2. Update weapon verdicts, fleet templates, economy rules from patch notes
  3. Test in a real game — don't invent meta from patch notes alone
  4. The engine auto-detects the version from the save file and loads the right meta
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_META_DIR = Path(__file__).resolve().parent.parent / "docs" / "meta"
_CACHE: dict[str, dict] = {}


def load_meta(version: str) -> dict:
    """Load meta rules for a specific game version.

    Falls back to nearest available version if exact match not found.
    Results are cached in memory.
    """
    if version in _CACHE:
        return _CACHE[version]

    meta = _try_load(version)
    if meta is None:
        # Try major.minor match (e.g. 4.3.4 → 4.3)
        parts = version.split(".")
        if len(parts) >= 2:
            fallback = f"{parts[0]}.{parts[1]}"
            meta = _try_load_prefix(fallback)

    if meta is None:
        # Fall back to latest available
        meta = _load_latest()

    if meta is None:
        log.warning("No meta files found in %s — using empty meta", _META_DIR)
        meta = _empty_meta(version)

    _CACHE[version] = meta
    log.info("Loaded meta for version %s (source: %s)", version, meta.get("_source", "empty"))
    return meta


def available_versions() -> list[str]:
    """Return list of available meta versions."""
    if not _META_DIR.exists():
        return []
    return sorted(
        p.stem for p in _META_DIR.glob("*.json")
        if not p.stem.startswith("_")
    )


def _try_load(version: str) -> dict | None:
    path = _META_DIR / f"{version}.json"
    if path.exists():
        return _read_meta(path)
    return None


def _try_load_prefix(prefix: str) -> dict | None:
    """Load the highest version matching a prefix (e.g. '4.3' matches '4.3.4')."""
    if not _META_DIR.exists():
        return None
    matches = sorted(
        p for p in _META_DIR.glob(f"{prefix}*.json")
        if not p.stem.startswith("_")
    )
    if matches:
        return _read_meta(matches[-1])
    return None


def _load_latest() -> dict | None:
    if not _META_DIR.exists():
        return None
    files = sorted(
        p for p in _META_DIR.glob("*.json")
        if not p.stem.startswith("_")
    )
    if files:
        return _read_meta(files[-1])
    return None


def _read_meta(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta = json.loads(raw)
    meta["_source"] = path.name
    return meta


def _empty_meta(version: str) -> dict:
    return {
        "version": version,
        "weapon_verdicts": {},
        "fleet_templates": {},
        "economy_rules": {},
        "forbidden_weapons": [],
        "forbidden_fleet_patterns": [],
        "origin_tiers": {},
        "meta_rules_domestic": "",
        "meta_rules_military": "",
        "_source": "empty",
    }
