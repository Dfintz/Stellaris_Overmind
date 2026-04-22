"""
Recorder — Captures (state, decision, outcome) tuples during live play.

Every tick that produces a decision is recorded.  After the game advances,
the recorder retroactively scores each decision by comparing the state at
decision time with the state N months later.

Output: one ``.jsonl`` file per game session in ``training/replay_buffer/``.
Each line is a complete training record:

    {
        "game_id": "game_001",
        "turn": 42,
        "year": 2230,
        "state_before": { ... },
        "decision": { "action": "BUILD_FLEET", "target": "Sol", "reason": "..." },
        "state_after": { ... },        // filled retroactively
        "outcome_scores": { ... },     // filled by OutcomeScorer
        "meta_alignment": 0.85,        // how well the decision matched meta rules
        "validated": true
    }
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

REPLAY_DIR = Path("training/replay_buffer")


@dataclass
class DecisionRecord:
    """A single recorded decision with its context and eventual outcome."""

    game_id: str
    turn: int
    year: int
    month: int
    state_before: dict
    decision: dict
    event: str | None = None
    state_after: dict | None = None
    outcome_scores: dict | None = None
    meta_alignment: float | None = None
    validated: bool = True
    llm_latency_ms: float = 0.0
    provider: str = ""
    timestamp_unix: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class GameRecorder:
    """Records decisions during a live game for later training."""

    def __init__(self, game_id: str | None = None, replay_dir: Path = REPLAY_DIR) -> None:
        raw_id = game_id or f"game_{uuid.uuid4().hex[:8]}"
        # Sanitize game_id to prevent path traversal
        self._game_id = Path(raw_id).name.replace("..", "_")
        self._replay_dir = replay_dir
        self._records: list[DecisionRecord] = []
        self._pending: list[DecisionRecord] = []  # waiting for state_after
        self._turn = 0
        self._file_path = self._replay_dir / f"{self._game_id}.jsonl"

        self._replay_dir.mkdir(parents=True, exist_ok=True)
        log.info("Recorder started: game_id=%s file=%s", self._game_id, self._file_path)

    @property
    def game_id(self) -> str:
        return self._game_id

    @property
    def record_count(self) -> int:
        return len(self._records)

    def record_decision(
        self,
        state: dict,
        decision: dict,
        event: str | None = None,
        validated: bool = True,
        llm_latency_ms: float = 0.0,
        provider: str = "",
    ) -> None:
        """Record a decision made at the current game state."""
        self._turn += 1
        rec = DecisionRecord(
            game_id=self._game_id,
            turn=self._turn,
            year=state.get("year", 0),
            month=state.get("month", 0),
            state_before=state,
            decision=decision,
            event=event,
            validated=validated,
            llm_latency_ms=llm_latency_ms,
            provider=provider,
        )
        self._records.append(rec)
        self._pending.append(rec)

        # Append to JSONL file immediately (crash-safe)
        self._append_record(rec)

        log.debug(
            "Recorded turn %d: %s → %s",
            self._turn, decision.get("action"), decision.get("target"),
        )

    def update_outcomes(self, current_state: dict, lookback_months: int = 12) -> int:
        """Retroactively fill state_after for decisions old enough.

        Called periodically with the latest game state.  Decisions that are
        at least ``lookback_months`` game-months old get their ``state_after``
        filled.  Returns the number of records updated.
        """
        current_year = current_state.get("year", 0)
        current_month = current_state.get("month", 0)
        current_total = current_year * 12 + current_month

        updated = 0
        still_pending = []
        for rec in self._pending:
            rec_total = rec.year * 12 + rec.month
            if current_total - rec_total >= lookback_months:
                rec.state_after = current_state
                updated += 1
            else:
                still_pending.append(rec)

        self._pending = still_pending

        if updated:
            log.info("Updated outcomes for %d records", updated)
            # Rewrite the full file with updated records
            self._rewrite_file()

        return updated

    def finalize(self, final_state: dict) -> None:
        """Mark all remaining pending records with the final game state."""
        for rec in self._pending:
            rec.state_after = final_state
        self._pending.clear()
        self._rewrite_file()
        log.info("Finalized %d total records for game %s", len(self._records), self._game_id)

    def get_records(self) -> list[DecisionRecord]:
        return list(self._records)

    # ------------------------------------------------------------------ #
    # File I/O
    # ------------------------------------------------------------------ #

    def _append_record(self, rec: DecisionRecord) -> None:
        """Append a single record to the JSONL file."""
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict(), separators=(",", ":")) + "\n")

    def _rewrite_file(self) -> None:
        """Rewrite the entire JSONL file (used after retroactive updates)."""
        tmp = self._file_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for rec in self._records:
                f.write(json.dumps(rec.to_dict(), separators=(",", ":")) + "\n")
        tmp.replace(self._file_path)
