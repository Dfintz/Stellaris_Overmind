"""
Training Data Curator — Converts scored replay data into fine-tuning datasets.

Two output formats:

1. **SFT (Supervised Fine-Tuning):**
   High-scoring decisions become (prompt, completion) pairs.
   Only decisions with composite score ≥ threshold are included.

   Output: ``training/sft_data/sft_YYYYMMDD.jsonl``

2. **DPO (Direct Preference Optimization):**
   Pairs of (good_decision, bad_decision) for the same game state.
   Requires at least 2 decisions for the same state context.

   Output: ``training/dpo_pairs/dpo_YYYYMMDD.jsonl``

Usage:
    python -m training.curate --replay-dir training/replay_buffer --min-score 0.3
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from engine.decision_engine import build_prompt
from engine.scorer import score_outcome

log = logging.getLogger(__name__)


@dataclass
class SFTExample:
    """A single supervised fine-tuning example."""

    prompt: str
    completion: str
    composite_score: float
    game_id: str
    turn: int

    def to_dict(self) -> dict:
        return {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a Stellaris 4.3.4 strategic AI advisor. "
                        "Choose exactly ONE action and cite ruleset elements."
                    ),
                },
                {"role": "user", "content": self.prompt},
                {"role": "assistant", "content": self.completion},
            ],
            "metadata": {
                "composite_score": self.composite_score,
                "game_id": self.game_id,
                "turn": self.turn,
            },
        }


@dataclass
class DPOPair:
    """A preference pair for DPO training."""

    prompt: str
    chosen: str       # the better response
    rejected: str     # the worse response
    chosen_score: float
    rejected_score: float

    def to_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "chosen": self.chosen,
            "rejected": self.rejected,
            "chosen_score": self.chosen_score,
            "rejected_score": self.rejected_score,
        }


class TrainingCurator:
    """Processes replay buffer into training datasets."""

    def __init__(
        self,
        replay_dir: Path = Path("training/replay_buffer"),
        output_dir: Path = Path("training"),
        sft_threshold: float = 0.3,
        dpo_margin: float = 0.2,
    ) -> None:
        self._replay_dir = replay_dir
        self._sft_dir = output_dir / "sft_data"
        self._dpo_dir = output_dir / "dpo_pairs"
        self._sft_threshold = sft_threshold
        self._dpo_margin = dpo_margin

    def curate_all(self, ruleset: dict, personality: dict) -> dict:
        """Process all replay files and generate training data.

        Returns a summary dict with counts.
        """
        self._sft_dir.mkdir(parents=True, exist_ok=True)
        self._dpo_dir.mkdir(parents=True, exist_ok=True)

        all_records = self._load_all_replays()
        log.info("Loaded %d records from replay buffer", len(all_records))

        # Score all records that have both before/after states
        scored = self._score_records(all_records, ruleset)
        log.info("Scored %d records", len(scored))

        # Generate SFT data
        sft_examples = self._generate_sft(scored, ruleset, personality)
        sft_path = self._sft_dir / f"sft_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        self._write_jsonl(sft_path, [e.to_dict() for e in sft_examples])

        # Generate DPO pairs
        dpo_pairs = self._generate_dpo(scored, ruleset, personality)
        dpo_path = self._dpo_dir / f"dpo_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        self._write_jsonl(dpo_path, [p.to_dict() for p in dpo_pairs])

        summary = {
            "total_records": len(all_records),
            "scored_records": len(scored),
            "sft_examples": len(sft_examples),
            "dpo_pairs": len(dpo_pairs),
            "sft_path": str(sft_path),
            "dpo_path": str(dpo_path),
        }
        log.info("Curation complete: %s", summary)
        return summary

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _load_all_replays(self) -> list[dict]:
        """Load all JSONL records from the replay directory."""
        records = []
        for path in sorted(self._replay_dir.glob("*.jsonl")):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        return records

    def _score_records(self, records: list[dict], ruleset: dict) -> list[dict]:
        """Score records that have both state_before and state_after."""
        scored = []
        for rec in records:
            before = rec.get("state_before")
            after = rec.get("state_after")
            decision = rec.get("decision")
            if not (before and after and decision):
                continue

            scores = score_outcome(before, after, decision, ruleset)
            rec["outcome_scores"] = scores.to_dict()
            rec["meta_alignment"] = scores.meta_alignment
            rec["composite_score"] = scores.composite
            scored.append(rec)

        return scored

    def _generate_sft(
        self, scored: list[dict], ruleset: dict, personality: dict,
    ) -> list[SFTExample]:
        """Generate SFT examples from high-scoring decisions."""
        examples = []
        for rec in scored:
            if rec["composite_score"] < self._sft_threshold:
                continue

            decision = rec["decision"]
            state = rec["state_before"]
            event = rec.get("event")

            prompt = build_prompt(ruleset, personality, state, event)
            completion = (
                f"ACTION: {decision.get('action', 'CONSOLIDATE')}\n"
                f"TARGET: {decision.get('target', 'NONE')}\n"
                f"REASON: {decision.get('reason', 'N/A')}"
            )

            examples.append(SFTExample(
                prompt=prompt,
                completion=completion,
                composite_score=rec["composite_score"],
                game_id=rec.get("game_id", "?"),
                turn=rec.get("turn", 0),
            ))

        # Sort by score descending — best decisions first
        examples.sort(key=lambda e: e.composite_score, reverse=True)
        log.info(
            "Generated %d SFT examples (threshold=%.2f)",
            len(examples), self._sft_threshold,
        )
        return examples

    def _generate_dpo(
        self, scored: list[dict], ruleset: dict, personality: dict,
    ) -> list[DPOPair]:
        """Generate DPO preference pairs from scored decisions.

        Pairs are formed by matching decisions from similar game phases
        and comparing their scores.  The higher-scoring decision is 'chosen',
        the lower-scoring one is 'rejected'.
        """
        # Group by game phase (early/mid/late based on year)
        phase_buckets: dict[str, list[dict]] = {"early": [], "mid": [], "late": []}
        for rec in scored:
            year = rec.get("year", 2200)
            if year < 2240:
                phase_buckets["early"].append(rec)
            elif year < 2320:
                phase_buckets["mid"].append(rec)
            else:
                phase_buckets["late"].append(rec)

        pairs = []
        for phase, bucket in phase_buckets.items():
            # Sort by composite score
            bucket.sort(key=lambda r: r["composite_score"], reverse=True)

            # Pair top-half with bottom-half
            mid = len(bucket) // 2
            top = bucket[:mid]
            bottom = bucket[mid:]

            for good, bad in zip(top, bottom):
                margin = good["composite_score"] - bad["composite_score"]
                if margin < self._dpo_margin:
                    continue

                state = good["state_before"]
                event = good.get("event")
                prompt = build_prompt(ruleset, personality, state, event)

                good_d = good["decision"]
                bad_d = bad["decision"]

                chosen = (
                    f"ACTION: {good_d.get('action', 'CONSOLIDATE')}\n"
                    f"TARGET: {good_d.get('target', 'NONE')}\n"
                    f"REASON: {good_d.get('reason', 'N/A')}"
                )
                rejected = (
                    f"ACTION: {bad_d.get('action', 'CONSOLIDATE')}\n"
                    f"TARGET: {bad_d.get('target', 'NONE')}\n"
                    f"REASON: {bad_d.get('reason', 'N/A')}"
                )

                pairs.append(DPOPair(
                    prompt=prompt,
                    chosen=chosen,
                    rejected=rejected,
                    chosen_score=good["composite_score"],
                    rejected_score=bad["composite_score"],
                ))

        log.info(
            "Generated %d DPO pairs (margin=%.2f)",
            len(pairs), self._dpo_margin,
        )
        return pairs

    @staticmethod
    def _write_jsonl(path: Path, items: list[dict]) -> None:
        """Write a list of dicts as JSONL."""
        with open(path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, separators=(",", ":")) + "\n")
        log.info("Wrote %d records to %s", len(items), path)
