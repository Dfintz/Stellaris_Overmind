"""
Outcome Scorer — Evaluates how good a decision was after the fact.

Takes a DecisionRecord with both ``state_before`` and ``state_after`` filled
and produces numeric scores across multiple dimensions.

Scoring philosophy:
  - We measure *deltas* (how much did things change after the decision)
  - We measure *meta alignment* (did the decision follow the curated meta)
  - We measure *survival* (is the empire still alive / growing)
  - We do NOT score based on hidden information (fog-of-war safe)

Scores are normalized to [-1.0, +1.0] where:
  - +1.0 = excellent outcome
  -  0.0 = neutral / no change
  - -1.0 = terrible outcome

The composite score is a weighted sum used to rank decisions for training.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from engine.ruleset_generator import (
    ORIGIN_OVERRIDES,
    GamePhase,
    get_phase_priorities,
)

log = logging.getLogger(__name__)


@dataclass
class OutcomeScores:
    """Multi-dimensional outcome assessment."""

    economy_delta: float = 0.0      # resource trajectory improvement
    fleet_delta: float = 0.0        # military power change
    tech_delta: float = 0.0         # research progress
    expansion_delta: float = 0.0    # colony / system growth
    stability_score: float = 0.0    # survived threats, no deficits
    meta_alignment: float = 0.0     # adherence to META_4.3.4 rules
    composite: float = 0.0          # weighted final score

    def to_dict(self) -> dict:
        return {
            "economy_delta": round(self.economy_delta, 3),
            "fleet_delta": round(self.fleet_delta, 3),
            "tech_delta": round(self.tech_delta, 3),
            "expansion_delta": round(self.expansion_delta, 3),
            "stability_score": round(self.stability_score, 3),
            "meta_alignment": round(self.meta_alignment, 3),
            "composite": round(self.composite, 3),
        }


# Dimension weights for composite score (tuned to 4.3 meta priorities)
SCORE_WEIGHTS: dict[str, float] = {
    "economy_delta": 0.25,
    "fleet_delta": 0.20,
    "tech_delta": 0.15,
    "expansion_delta": 0.15,
    "stability_score": 0.10,
    "meta_alignment": 0.15,
}


def score_outcome(
    state_before: dict,
    state_after: dict,
    decision: dict,
    ruleset: dict,
) -> OutcomeScores:
    """Score a decision by comparing before/after states.

    Parameters
    ----------
    state_before : dict
        Game state when the decision was made.
    state_after : dict
        Game state N months after the decision.
    decision : dict
        The directive that was executed.
    ruleset : dict
        The empire's composite ruleset.

    Returns
    -------
    OutcomeScores
        Multi-dimensional scores normalized to [-1, +1].
    """
    scores = OutcomeScores()

    eco_before = state_before.get("economy", {})
    eco_after = state_after.get("economy", {})

    # --- Economy delta ---
    scores.economy_delta = _score_economy(eco_before, eco_after)

    # --- Fleet delta ---
    scores.fleet_delta = _score_fleet(state_before, state_after)

    # --- Tech delta (proxy: research output) ---
    scores.tech_delta = _score_tech(eco_before, eco_after)

    # --- Expansion delta ---
    scores.expansion_delta = _score_expansion(state_before, state_after)

    # --- Stability (survival check) ---
    scores.stability_score = _score_stability(eco_after)

    # --- Meta alignment ---
    scores.meta_alignment = _score_meta_alignment(
        decision, state_before, ruleset,
    )

    # --- Composite ---
    scores.composite = sum(
        getattr(scores, dim) * w
        for dim, w in SCORE_WEIGHTS.items()
    )

    return scores


def _score_economy(before: dict, after: dict) -> float:
    """Score economic trajectory.  Positive = growing, negative = shrinking."""
    key_resources = ["energy", "minerals", "alloys", "consumer_goods", "unity"]
    deltas = []
    for r in key_resources:
        b = before.get(r, 0)
        a = after.get(r, 0)
        if b > 0:
            deltas.append((a - b) / max(b, 1))
        elif a > 0:
            deltas.append(1.0)
        else:
            deltas.append(0.0)
    avg = sum(deltas) / len(deltas) if deltas else 0.0
    return _clamp(avg, -1.0, 1.0)


def _score_fleet(before: dict, after: dict) -> float:
    """Score fleet power trajectory."""
    power_before = sum(f.get("power", 0) for f in before.get("fleets", []))
    power_after = sum(f.get("power", 0) for f in after.get("fleets", []))
    if power_before > 0:
        delta = (power_after - power_before) / power_before
    elif power_after > 0:
        delta = 1.0
    else:
        delta = 0.0
    return _clamp(delta, -1.0, 1.0)


def _score_tech(before: dict, after: dict) -> float:
    """Score research progress (proxy: unity and influence growth)."""
    # In 4.3, tech costs halved but output halved — use unity as proxy
    unity_b = before.get("unity", 0)
    unity_a = after.get("unity", 0)
    if unity_b > 0:
        return _clamp((unity_a - unity_b) / max(unity_b, 1), -1.0, 1.0)
    return 0.0 if unity_a == 0 else 0.5


def _score_expansion(before: dict, after: dict) -> float:
    """Score territorial growth (colony count)."""
    colonies_b = len(before.get("colonies", []))
    colonies_a = len(after.get("colonies", []))
    if colonies_b > 0:
        return _clamp((colonies_a - colonies_b) / colonies_b, -1.0, 1.0)
    return 1.0 if colonies_a > 0 else 0.0


def _score_stability(eco_after: dict) -> float:
    """Score survival — penalize deficits, reward healthy economy."""
    score = 0.5  # baseline: alive
    # Deficit penalties
    for resource in ["energy", "minerals", "food"]:
        if eco_after.get(resource, 0) < 0:
            score -= 0.25
    # Surplus bonus
    alloys = eco_after.get("alloys", 0)
    if alloys > 100:
        score += 0.25
    if alloys > 300:
        score += 0.25
    return _clamp(score, -1.0, 1.0)


def _score_meta_alignment(
    decision: dict,
    state: dict,
    ruleset: dict,
) -> float:
    """Score how well the decision aligns with META_4.3.4 rules."""
    score = 0.5  # baseline: neutral
    action = decision.get("action", "")
    year = state.get("year", 2200)
    phase = get_phase_priorities(year)
    reason = decision.get("reason", "").lower()

    # Early game: IMPROVE_ECONOMY and EXPAND are meta-correct
    if phase["phase"] == "early":
        if action in ("IMPROVE_ECONOMY", "EXPAND", "COLONIZE"):
            score += 0.3
        elif action == "PREPARE_WAR" and year < 2220:
            score -= 0.2  # too aggressive too early

    # Mid game: BUILD_FLEET and FOCUS_TECH are meta-correct
    elif phase["phase"] == "mid":
        if action in ("BUILD_FLEET", "FOCUS_TECH", "DIPLOMACY"):
            score += 0.2

    # Late game: crisis prep is critical
    elif phase["phase"] == "late":
        if action in ("BUILD_FLEET", "DEFEND", "FOCUS_TECH"):
            score += 0.3
        elif action == "EXPAND":
            score -= 0.1  # overexpansion late is risky

    # Bonus: reason cites meta rules
    meta_terms = ["meta", "4.3", "efficiency", "stability", "chokepoint", "titan"]
    for term in meta_terms:
        if term in reason:
            score += 0.05

    # Penalty: reason mentions forbidden patterns
    forbidden = ["disruptor", "corvette only", "pre-4.3"]
    for term in forbidden:
        if term in reason:
            score -= 0.3

    return _clamp(score, -1.0, 1.0)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))
