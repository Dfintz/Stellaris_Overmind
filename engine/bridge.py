"""
Bridge — Communication between Stellaris and the Python engine.

Two modes of operation:

**Mode A — Autosave Reader (recommended):**
  The Python engine watches the Stellaris autosave directory for new ``.sav``
  files, parses them directly with ``save_reader.py``, and extracts game state.
  No Clausewitz exporter mod needed.

**Mode B — JSON File Bridge (legacy):**
  A Clausewitz mod writes ``state_snapshot.json`` to a shared directory.
  The Python engine polls for changes.

**Directive output (both modes):**
  The engine writes ``directive.json`` to the mod's ``ai_bridge/`` directory.
  A simple Clausewitz mod reads this and executes the action.

Flow (Mode A):
  1. Stellaris autosaves → ``save games/<empire>/*.sav``
  2. SaveBridge detects new save, parses it
  3. Engine processes → writes ``directive.json`` to mod bridge dir
  4. Clausewitz mod reads directive on next tick, executes action

Flow (Mode B — legacy):
  1. Clausewitz mod writes ``state_snapshot.json``
  2. BridgeReader detects change
  3. Engine processes → writes ``directive.json``
  4. Mod reads directive on next tick
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Fields that should never appear in known_empires at low/no intel
_FOW_SUSPECT_FIELDS = {"economy", "economy_class", "tech_count", "known_fleet_power",
                       "military_power", "fleet_power", "resources"}


def _sanitize_snapshot_fow(data: dict) -> dict:
    """Strip fields from a legacy JSON snapshot that could violate fog-of-war.

    The autosave path (SaveBridge) has proper intel-level filtering, but
    the legacy JSON bridge trusts the Clausewitz exporter entirely.
    This adds defense-in-depth by warning on suspicious fields.
    """
    empires = data.get("known_empires", [])
    if not isinstance(empires, list):
        return data

    for empire in empires:
        if not isinstance(empire, dict):
            continue
        intel = empire.get("intel_level", "none")
        if intel in ("none", "low"):
            # At low/no intel, strip fields that require higher intel
            stripped = [k for k in empire if k in _FOW_SUSPECT_FIELDS]
            for k in stripped:
                del empire[k]
            if stripped:
                log.warning(
                    "FoW sanitize: stripped %s from empire '%s' (intel=%s)",
                    stripped, empire.get("name", "?"), intel,
                )
    return data


# ======================================================================== #
# Config
# ======================================================================== #

@dataclass
class BridgeConfig:
    """Paths and timing for the bridge."""

    # Autosave mode (Mode A)
    save_dir: Path = Path("")             # e.g. .../Paradox Interactive/Stellaris/save games
    player_name: str = ""                 # auto-detected if empty

    # Directive output (both modes)
    bridge_dir: Path = Path("mod/ai_bridge")
    directive_file: str = "directive.json"
    ack_file: str = "ack.json"

    # Legacy JSON bridge (Mode B)
    snapshot_file: str = "state_snapshot.json"

    # Timing
    poll_interval_s: float = 2.0

    @property
    def mode(self) -> str:
        """Return 'autosave' if save_dir is configured, else 'json'."""
        if self.save_dir and self.save_dir.exists():
            return "autosave"
        return "json"


# ======================================================================== #
# Mode A — Autosave Bridge (recommended)
# ======================================================================== #

class SaveBridge:
    """Watches autosave directory and parses ``.sav`` files directly.

    This eliminates the need for a Clausewitz state exporter mod.
    """

    def __init__(self, config: BridgeConfig) -> None:
        self._config = config
        # Lazy import to avoid circular deps
        from engine.save_reader import SaveReader, SaveWatcherConfig

        self._reader = SaveReader(SaveWatcherConfig(
            save_dir=config.save_dir,
            poll_interval_s=config.poll_interval_s,
            player_name=config.player_name,
        ))

    def has_new_snapshot(self) -> bool:
        return self._reader.has_new_save()

    def read_snapshot(self) -> dict | None:
        return self._reader.read_state()


# ======================================================================== #
# Mode B — Legacy JSON File Bridge
# ======================================================================== #

class BridgeReader:
    """Watches for JSON state snapshots written by a Clausewitz mod."""

    def __init__(self, config: BridgeConfig) -> None:
        self._config = config
        self._snapshot_path = config.bridge_dir / config.snapshot_file
        self._last_mtime: float = 0.0

    def has_new_snapshot(self) -> bool:
        if not self._snapshot_path.exists():
            return False
        mtime = os.path.getmtime(self._snapshot_path)
        return mtime > self._last_mtime

    def read_snapshot(self) -> dict | None:
        if not self.has_new_snapshot():
            return None
        try:
            raw = self._snapshot_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self._last_mtime = os.path.getmtime(self._snapshot_path)
            log.info(
                "Read JSON snapshot: year=%s month=%s event=%s",
                data.get("year"), data.get("month"), data.get("event"),
            )
            return _sanitize_snapshot_fow(data)
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Failed to read snapshot: %s", exc)
            return None

    def read_ack(self) -> dict | None:
        ack_path = self._config.bridge_dir / self._config.ack_file
        if not ack_path.exists():
            return None
        try:
            raw = ack_path.read_text(encoding="utf-8")
            return json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            log.debug("Failed to read ack file: %s", exc)
            return None


# ======================================================================== #
# Unified Reader — picks the right mode automatically
# ======================================================================== #

class UnifiedBridge:
    """Automatically selects autosave or JSON mode based on config."""

    def __init__(self, config: BridgeConfig) -> None:
        self._config = config
        self._mode = config.mode

        if self._mode == "autosave":
            self._reader = SaveBridge(config)
            log.info("Bridge mode: AUTOSAVE (watching %s)", config.save_dir)
        else:
            self._reader = BridgeReader(config)
            log.info("Bridge mode: JSON (watching %s)", config.bridge_dir / config.snapshot_file)

    @property
    def mode(self) -> str:
        return self._mode

    def has_new_snapshot(self) -> bool:
        return self._reader.has_new_snapshot()

    def read_snapshot(self) -> dict | None:
        return self._reader.read_snapshot()

    def read_ack(self) -> dict | None:
        if isinstance(self._reader, BridgeReader):
            return self._reader.read_ack()
        return None  # autosave mode doesn't have ack files


# ======================================================================== #
# Directive Writer (shared by both modes)
# ======================================================================== #

class BridgeWriter:
    """Writes directives for the Clausewitz mod to consume."""

    def __init__(self, config: BridgeConfig) -> None:
        self._config = config
        self._directive_path = config.bridge_dir / config.directive_file

    def write_directive(self, directive: dict) -> None:
        self._config.bridge_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self._directive_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(directive, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(self._directive_path)
        log.info(
            "Wrote directive: action=%s target=%s",
            directive.get("action"), directive.get("target"),
        )

    def clear_directive(self) -> None:
        """Remove the directive file after the mod acknowledges execution."""
        if self._directive_path.exists():
            self._directive_path.unlink()

    def write_console_commands(self, directive: dict, stellaris_dir: Path | None = None) -> None:
        """Write ``ai_commands.txt`` with console effects for this directive.

        Generates both the mod flag commands AND direct Clausewitz effects
        that execute real actions (build ships, research tech, build buildings,
        adopt traditions, etc.) so the player sees immediate results.
        """
        action_codes = {
            "EXPAND": 1, "BUILD_FLEET": 2, "IMPROVE_ECONOMY": 3,
            "FOCUS_TECH": 4, "DIPLOMACY": 5, "PREPARE_WAR": 6,
            "DEFEND": 7, "CONSOLIDATE": 8, "COLONIZE": 9,
            "BUILD_STARBASE": 10, "ESPIONAGE": 11,
        }
        action = directive.get("action", "CONSOLIDATE")
        code = action_codes.get(action, 8)

        commands = [
            f"# Overmind directive: {action}",
            f"# Reason: {directive.get('reason', 'N/A')[:80]}",
            "",
            "# --- Mod flags (personality + modifier) ---",
            f"effect set_variable = {{ which = overmind_action value = {code} }}",
            "effect set_country_flag = overmind_directive_ready",
        ]

        # --- Direct effects per action ---
        commands.append("")
        commands.append(f"# --- Direct effects: {action} ---")

        if action == "BUILD_FLEET":
            commands.extend([
                "# Build corvettes at all shipyards",
                "effect every_owned_planet = {",
                "    limit = { has_starport_size >= starbase_level_starport }",
                "    planet_event = { id = overmind.100 }",
                "}",
                "# Queue ship construction via resource boost",
                "effect add_resource = { alloys = 200 }",
                "effect country_event = { id = overmind.100 }",
            ])

        elif action == "IMPROVE_ECONOMY":
            commands.extend([
                "# Build mining/generator districts on planets with free slots",
                "effect every_owned_planet = {",
                "    limit = { free_district_slots > 0 num_districts = { type = district_mining value < 10 } }",
                "    add_district = district_mining",
                "}",
                "effect every_owned_planet = {",
                "    limit = { free_district_slots > 0 num_districts = { type = district_generator value < 10 } }",
                "    add_district = district_generator",
                "}",
                "# Build alloy foundry on capital if possible",
                "effect capital_scope = {",
                "    if = {",
                "        limit = { free_building_slots > 0 }",
                "        add_building = building_foundry_1",
                "    }",
                "}",
            ])

        elif action == "FOCUS_TECH":
            commands.extend([
                "# Build research districts/labs",
                "effect every_owned_planet = {",
                "    limit = { free_district_slots > 0 }",
                "    add_district = district_generator",
                "}",
                "effect capital_scope = {",
                "    if = {",
                "        limit = { free_building_slots > 0 }",
                "        add_building = building_research_lab_1",
                "    }",
                "}",
                "# Boost research output",
                "effect add_modifier = { modifier = overmind_research_focus days = 180 }",
            ])

        elif action == "EXPAND":
            commands.extend([
                "# Boost influence for expansion",
                "effect add_resource = { influence = 50 }",
                "effect add_modifier = { modifier = overmind_expansion_focus days = 180 }",
            ])

        elif action == "COLONIZE":
            commands.extend([
                "# Boost colony development",
                "effect add_resource = { food = 200 }",
                "effect add_modifier = { modifier = overmind_colonize_focus days = 180 }",
            ])

        elif action == "PREPARE_WAR":
            commands.extend([
                "# War economy: boost alloys",
                "effect add_resource = { alloys = 300 }",
                "effect add_modifier = { modifier = overmind_war_preparation days = 360 }",
            ])

        elif action == "DEFEND":
            commands.extend([
                "# Reinforce starbases",
                "effect add_modifier = { modifier = overmind_defense_focus days = 180 }",
            ])

        elif action == "CONSOLIDATE":
            commands.extend([
                "# Stabilize economy",
                "effect add_resource = { energy = 100 minerals = 100 }",
                "effect add_modifier = { modifier = overmind_consolidation days = 180 }",
            ])

        elif action == "BUILD_STARBASE":
            commands.extend([
                "# Starbase upgrade resources",
                "effect add_resource = { alloys = 150 influence = 25 }",
                "effect add_modifier = { modifier = overmind_starbase_focus days = 180 }",
            ])

        elif action == "DIPLOMACY":
            commands.extend([
                "# Diplomatic weight boost",
                "effect add_modifier = { modifier = overmind_diplomacy_focus days = 180 }",
            ])

        elif action == "ESPIONAGE":
            commands.extend([
                "# Espionage boost",
                "effect add_modifier = { modifier = overmind_espionage_focus days = 180 }",
            ])

        # Write to Stellaris user data dir (where `run` looks for files)
        if stellaris_dir and stellaris_dir.exists():
            cmd_path = stellaris_dir / "ai_commands.txt"
        else:
            cmd_path = self._config.bridge_dir / "ai_commands.txt"

        cmd_path.write_text("\n".join(commands), encoding="utf-8")
        log.info("Wrote console commands: %s → %s (code %d)", action, cmd_path, code)

    def write_suggestion(self, directive: dict, stellaris_dir: Path | None = None) -> None:
        """Write a human-readable suggestion file for player mode.

        Instead of executing actions, this shows the player what the
        LLM recommends they should do next.
        """
        _SUGGESTION_TIPS = {
            "EXPAND": [
                "Build a starbase outpost in a nearby unclaimed system",
                "Prioritize chokepoint systems for defense",
                "Claim systems with rare resources first",
            ],
            "BUILD_FLEET": [
                "Queue corvettes/destroyers at your shipyard",
                "Use autocannon + plasma loadout (4.3 meta)",
                "Fill your naval cap before upgrading ship designs",
            ],
            "IMPROVE_ECONOMY": [
                "Build mining districts on mineral-rich planets",
                "Build alloy foundries (alloys > consumer goods early)",
                "Specialize planets with designations",
            ],
            "FOCUS_TECH": [
                "Build research labs on your capital",
                "Set Academic Privilege living standard",
                "Prioritize alloy/mineral tech for early economy",
            ],
            "DIPLOMACY": [
                "Send an envoy to improve relations with neighbors",
                "Consider a research agreement or commercial pact",
                "Set diplomatic stance to Cooperative",
            ],
            "PREPARE_WAR": [
                "Move fleets to the border with your target",
                "Stock up on alloys (aim for 1000+)",
                "Set economic policy to Militarist",
                "Claim target systems before declaring war",
            ],
            "DEFEND": [
                "Consolidate fleets at chokepoint starbases",
                "Upgrade starbases with gun batteries + hangars",
                "Build defense platforms at key starbases",
            ],
            "CONSOLIDATE": [
                "Fix any energy/food deficits first",
                "Build amenity buildings on low-stability planets",
                "Pause expansion until economy stabilizes",
            ],
            "COLONIZE": [
                "Build a colony ship and send to the best available world",
                "Prioritize size 20+ planets with good habitability",
                "Void Dwellers: build habitats instead",
            ],
            "BUILD_STARBASE": [
                "Upgrade a starbase at a chokepoint to starhold/fortress",
                "Add anchorages for naval cap, or trade hubs for energy",
                "Build shipyard modules for fleet production",
            ],
            "ESPIONAGE": [
                "Build a spy network in a rival empire",
                "Assign a high-level operative as spymaster",
                "Gather intel before declaring war",
            ],
        }

        action = directive.get("action", "CONSOLIDATE")
        reason = directive.get("reason", "")
        timestamp = directive.get("timestamp", "")
        tips = _SUGGESTION_TIPS.get(action, ["Follow the LLM's recommendation"])

        lines = [
            "╔══════════════════════════════════════════════════════════╗",
            f"║  OVERMIND SUGGESTS: {action:<38}║",
            "╠══════════════════════════════════════════════════════════╣",
            f"║  Year: {timestamp:<50}║",
            "║                                                          ║",
            f"║  Reason: {reason[:48]:<48}  ║",
        ]
        if len(reason) > 48:
            lines.append(f"║          {reason[48:96]:<48}  ║")

        lines.append("║                                                          ║")
        lines.append("║  What to do:                                              ║")
        for tip in tips:
            lines.append(f"║   • {tip:<53}║")
        lines.extend([
            "║                                                          ║",
            "╚══════════════════════════════════════════════════════════╝",
        ])

        suggestion_text = "\n".join(lines)

        # Print to stdout for immediate visibility
        print("\n" + suggestion_text + "\n")

        # Also save to file
        if stellaris_dir and stellaris_dir.exists():
            path = stellaris_dir / "overmind_suggestion.txt"
        else:
            path = self._config.bridge_dir / "overmind_suggestion.txt"

        path.write_text(suggestion_text, encoding="utf-8")
        log.info("Suggestion: %s — %s", action, reason[:80])

    def write_directive_for(self, country_id: int, directive: dict) -> None:
        """Write a directive for a specific AI empire.

        Creates ``directive_<country_id>.json`` in the bridge directory.
        The mod reads each per-empire directive and scopes execution to
        the matching country.
        """
        self._config.bridge_dir.mkdir(parents=True, exist_ok=True)
        path = self._config.bridge_dir / f"directive_{country_id}.json"
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(directive, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(path)
        log.debug(
            "Wrote directive for country %d: action=%s",
            country_id, directive.get("action"),
        )
