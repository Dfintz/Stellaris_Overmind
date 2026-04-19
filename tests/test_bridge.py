"""Tests for bridge — Stellaris 4.3.4."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.bridge import BridgeConfig, BridgeReader, BridgeWriter, UnifiedBridge


@pytest.fixture
def bridge_dir(tmp_path: Path) -> Path:
    d = tmp_path / "ai_bridge"
    d.mkdir()
    return d


@pytest.fixture
def bridge_config(bridge_dir: Path) -> BridgeConfig:
    return BridgeConfig(bridge_dir=bridge_dir, save_dir=Path(""))


class TestBridgeWriter:

    def test_write_directive(self, bridge_config: BridgeConfig) -> None:
        writer = BridgeWriter(bridge_config)
        writer.write_directive({"action": "EXPAND", "target": "Sol"})
        path = bridge_config.bridge_dir / "directive.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["action"] == "EXPAND"

    def test_write_is_atomic(self, bridge_config: BridgeConfig) -> None:
        """No .tmp file should remain after write."""
        writer = BridgeWriter(bridge_config)
        writer.write_directive({"action": "DEFEND"})
        tmp = bridge_config.bridge_dir / "directive.tmp"
        assert not tmp.exists()

    def test_clear_directive(self, bridge_config: BridgeConfig) -> None:
        writer = BridgeWriter(bridge_config)
        writer.write_directive({"action": "EXPAND"})
        writer.clear_directive()
        assert not (bridge_config.bridge_dir / "directive.json").exists()

    def test_clear_nonexistent_ok(self, bridge_config: BridgeConfig) -> None:
        writer = BridgeWriter(bridge_config)
        writer.clear_directive()  # should not raise


class TestBridgeReader:

    def test_no_snapshot_returns_none(self, bridge_config: BridgeConfig) -> None:
        reader = BridgeReader(bridge_config)
        assert reader.read_snapshot() is None

    def test_read_snapshot(self, bridge_config: BridgeConfig) -> None:
        snap_path = bridge_config.bridge_dir / "state_snapshot.json"
        snap_path.write_text(json.dumps({"year": 2230, "month": 6}))
        reader = BridgeReader(bridge_config)
        data = reader.read_snapshot()
        assert data is not None
        assert data["year"] == 2230

    def test_no_double_read(self, bridge_config: BridgeConfig) -> None:
        snap_path = bridge_config.bridge_dir / "state_snapshot.json"
        snap_path.write_text(json.dumps({"year": 2230}))
        reader = BridgeReader(bridge_config)
        assert reader.read_snapshot() is not None
        assert reader.read_snapshot() is None  # same file, not re-read

    def test_read_ack(self, bridge_config: BridgeConfig) -> None:
        ack_path = bridge_config.bridge_dir / "ack.json"
        ack_path.write_text(json.dumps({"status": "ok"}))
        reader = BridgeReader(bridge_config)
        ack = reader.read_ack()
        assert ack is not None
        assert ack["status"] == "ok"

    def test_corrupt_json_returns_none(self, bridge_config: BridgeConfig) -> None:
        snap_path = bridge_config.bridge_dir / "state_snapshot.json"
        snap_path.write_text("{invalid json")
        reader = BridgeReader(bridge_config)
        assert reader.read_snapshot() is None


class TestUnifiedBridge:

    def test_json_mode_when_no_save_dir(self, bridge_config: BridgeConfig) -> None:
        config = BridgeConfig(save_dir=Path("/nonexistent_path_xyz"), bridge_dir=bridge_config.bridge_dir)
        bridge = UnifiedBridge(config)
        assert bridge.mode == "json"

    def test_autosave_mode_when_save_dir_exists(self, tmp_path: Path) -> None:
        save_dir = tmp_path / "save games"
        save_dir.mkdir()
        config = BridgeConfig(save_dir=save_dir, bridge_dir=tmp_path / "bridge")
        bridge = UnifiedBridge(config)
        assert bridge.mode == "autosave"
