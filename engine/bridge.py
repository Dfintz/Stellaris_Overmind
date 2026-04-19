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
            return data
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
        except (json.JSONDecodeError, OSError):
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
