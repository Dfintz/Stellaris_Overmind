"""Tests for recorder — Stellaris 4.3.4."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.recorder import GameRecorder


@pytest.fixture
def recorder(tmp_path: Path) -> GameRecorder:
    return GameRecorder(game_id="test_game", replay_dir=tmp_path)


class TestRecording:

    def test_record_creates_file(self, recorder: GameRecorder, tmp_path: Path) -> None:
        recorder.record_decision(
            state={"year": 2210, "month": 1},
            decision={"action": "EXPAND", "target": "Sol"},
        )
        path = tmp_path / "test_game.jsonl"
        assert path.exists()

    def test_record_count(self, recorder: GameRecorder) -> None:
        assert recorder.record_count == 0
        recorder.record_decision(
            state={"year": 2210}, decision={"action": "EXPAND"},
        )
        assert recorder.record_count == 1

    def test_jsonl_format(self, recorder: GameRecorder, tmp_path: Path) -> None:
        recorder.record_decision(
            state={"year": 2210}, decision={"action": "EXPAND"},
        )
        recorder.record_decision(
            state={"year": 2215}, decision={"action": "BUILD_FLEET"},
        )
        lines = (tmp_path / "test_game.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2
        rec1 = json.loads(lines[0])
        assert rec1["decision"]["action"] == "EXPAND"
        rec2 = json.loads(lines[1])
        assert rec2["decision"]["action"] == "BUILD_FLEET"

    def test_turn_increments(self, recorder: GameRecorder) -> None:
        recorder.record_decision(state={"year": 2210}, decision={"action": "A"})
        recorder.record_decision(state={"year": 2215}, decision={"action": "B"})
        records = recorder.get_records()
        assert records[0].turn == 1
        assert records[1].turn == 2


class TestOutcomes:

    def test_update_outcomes_fills_state_after(self, recorder: GameRecorder) -> None:
        recorder.record_decision(
            state={"year": 2210, "month": 1}, decision={"action": "EXPAND"},
        )
        # 13 months later
        updated = recorder.update_outcomes({"year": 2211, "month": 2}, lookback_months=12)
        assert updated == 1
        assert recorder.get_records()[0].state_after is not None

    def test_update_too_early_no_fill(self, recorder: GameRecorder) -> None:
        recorder.record_decision(
            state={"year": 2210, "month": 6}, decision={"action": "EXPAND"},
        )
        # Only 6 months later
        updated = recorder.update_outcomes({"year": 2211, "month": 1}, lookback_months=12)
        assert updated == 0
        assert recorder.get_records()[0].state_after is None

    def test_finalize_fills_all(self, recorder: GameRecorder) -> None:
        recorder.record_decision(state={"year": 2210}, decision={"action": "A"})
        recorder.record_decision(state={"year": 2215}, decision={"action": "B"})
        recorder.finalize({"year": 2400, "final": True})
        for rec in recorder.get_records():
            assert rec.state_after is not None
            assert rec.state_after["final"] is True
