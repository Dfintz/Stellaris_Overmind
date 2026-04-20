"""
Evaluate — Benchmark suite for measuring model decision quality.

Runs a set of fixed game scenarios through the decision pipeline and
scores the outputs across multiple dimensions:

  1. **Action Quality** — does the model pick strategically sound actions?
  2. **FoW Compliance** — does the model reference hidden information?
  3. **Meta Alignment** — does the model follow 4.3.4 meta rules?
  4. **Format Compliance** — does the model produce parseable ACTION/TARGET/REASON?
  5. **Whitelist Compliance** — are all actions from the allowed list?

Usage:
    python -m training.evaluate --model models/overmind-sft-v1
    python -m training.evaluate --provider stub  # baseline

Output: ``training/eval_results/eval_YYYYMMDD_HHMMSS.json``
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from engine.decision_engine import build_prompt, parse_llm_response
from engine.personality_shards import build_personality
from engine.ruleset_generator import ALLOWED_ACTIONS, generate_ruleset
from engine.validator import (
    FORBIDDEN_FLEET_PATTERNS,
    FORBIDDEN_WEAPONS,
    validate_directive,
)

log = logging.getLogger(__name__)


# ======================================================================== #
# Eval Scenario
# ======================================================================== #

@dataclass
class EvalScenario:
    """A fixed game scenario for benchmarking."""

    name: str
    description: str
    empire: dict          # ethics, civics, traits, origin, government
    state: dict           # game state snapshot
    expected_actions: list[str] = field(default_factory=list)  # acceptable actions
    forbidden_actions: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of evaluating one scenario."""

    scenario_name: str
    action: str
    target: str | None
    reason: str
    # Scores (0.0 to 1.0)
    format_ok: bool = False
    action_valid: bool = False
    action_expected: bool = False
    action_not_forbidden: bool = False
    fow_clean: bool = False
    meta_clean: bool = False
    validation_passed: bool = False
    latency_ms: float = 0.0
    error: str = ""

    @property
    def composite(self) -> float:
        """Weighted composite score (0.0 to 1.0)."""
        scores = [
            (self.format_ok, 0.15),
            (self.action_valid, 0.15),
            (self.action_expected, 0.20),
            (self.action_not_forbidden, 0.10),
            (self.fow_clean, 0.15),
            (self.meta_clean, 0.10),
            (self.validation_passed, 0.15),
        ]
        return sum(w for ok, w in scores if ok)


@dataclass
class EvalSummary:
    """Summary of a full eval run."""

    model: str
    timestamp: str
    total_scenarios: int = 0
    format_pass_rate: float = 0.0
    action_valid_rate: float = 0.0
    expected_action_rate: float = 0.0
    fow_clean_rate: float = 0.0
    meta_clean_rate: float = 0.0
    validation_pass_rate: float = 0.0
    mean_composite: float = 0.0
    mean_latency_ms: float = 0.0
    results: list[dict] = field(default_factory=list)


# ======================================================================== #
# Built-in Scenarios
# ======================================================================== #

SCENARIOS: list[EvalScenario] = [
    EvalScenario(
        name="early_economy_focus",
        description="Early game, stable economy, no threats. Should focus economy/tech.",
        empire={
            "ethics": ["Materialist", "Xenophile"],
            "civics": ["Technocracy"],
            "traits": ["Intelligent"],
            "origin": "Prosperous Unification",
            "government": "Oligarchy",
        },
        state={
            "version": "4.3.4",
            "year": 2210, "month": 3,
            "empire": {"name": "Test", "ethics": ["Materialist", "Xenophile"],
                       "civics": ["Technocracy"], "origin": "Prosperous Unification",
                       "government": "Oligarchy"},
            "economy": {"energy": 120, "minerals": 250, "food": 80,
                        "alloys": 35, "consumer_goods": 25},
            "colonies": ["Earth", "Mars"],
            "known_empires": [],
            "fleets": [{"name": "1st Fleet", "power": 1200, "location_system": "Sol"}],
        },
        expected_actions=["IMPROVE_ECONOMY", "FOCUS_TECH", "EXPAND", "COLONIZE"],
        tags=["early", "economy"],
    ),
    EvalScenario(
        name="hostile_neighbour_response",
        description="Hostile empire detected, moderate fleet. Should build fleet or prepare war.",
        empire={
            "ethics": ["Militarist", "Xenophobe"],
            "civics": ["Distinguished Admiralty"],
            "traits": ["Strong"],
            "origin": "Prosperous Unification",
            "government": "Dictatorial",
        },
        state={
            "version": "4.3.4",
            "year": 2230, "month": 6,
            "empire": {"name": "Warlike", "ethics": ["Militarist", "Xenophobe"],
                       "civics": ["Distinguished Admiralty"],
                       "origin": "Prosperous Unification", "government": "Dictatorial"},
            "economy": {"energy": 200, "minerals": 400, "food": 100,
                        "alloys": 80, "consumer_goods": 40},
            "colonies": ["Homeworld", "Colony Alpha", "Colony Beta"],
            "known_empires": [
                {"name": "Hostile Empire", "attitude": "Hostile", "intel_level": "Medium"},
            ],
            "fleets": [{"name": "Grand Fleet", "power": 5000, "location_system": "Home"}],
        },
        expected_actions=["BUILD_FLEET", "PREPARE_WAR", "DEFEND", "EXPAND"],
        forbidden_actions=["DIPLOMACY"],
        tags=["mid", "military", "threat"],
    ),
    EvalScenario(
        name="active_war_defense",
        description="At war, enemy fleet spotted. Must defend.",
        empire={
            "ethics": ["Pacifist", "Xenophile"],
            "civics": ["Diplomatic Corps"],
            "traits": ["Charismatic"],
            "origin": "Prosperous Unification",
            "government": "Democracy",
        },
        state={
            "version": "4.3.4",
            "year": 2250, "month": 1,
            "empire": {"name": "Peaceful", "ethics": ["Pacifist", "Xenophile"],
                       "civics": ["Diplomatic Corps"],
                       "origin": "Prosperous Unification", "government": "Democracy"},
            "economy": {"energy": 300, "minerals": 500, "food": 150,
                        "alloys": 100, "consumer_goods": 60},
            "colonies": ["Homeworld", "Colony A", "Colony B", "Colony C"],
            "known_empires": [
                {"name": "Aggressor", "attitude": "Hostile", "intel_level": "High"},
            ],
            "fleets": [{"name": "Defense Fleet", "power": 8000, "location_system": "Home"}],
            "wars": [{"attacker": "Aggressor", "defender": "Peaceful"}],
        },
        expected_actions=["DEFEND", "BUILD_FLEET", "CONSOLIDATE"],
        tags=["mid", "war", "defensive"],
    ),
    EvalScenario(
        name="void_dwellers_early",
        description="Void Dwellers origin — must colonize habitats only.",
        empire={
            "ethics": ["Fanatic Materialist", "Xenophobe"],
            "civics": ["Technocracy", "Citizen Service"],
            "traits": ["Intelligent", "Natural Engineers"],
            "origin": "Void Dwellers",
            "government": "Oligarchy",
        },
        state={
            "version": "4.3.4",
            "year": 2215, "month": 1,
            "empire": {"name": "Void Empire", "ethics": ["Fanatic Materialist", "Xenophobe"],
                       "civics": ["Technocracy", "Citizen Service"],
                       "origin": "Void Dwellers", "government": "Oligarchy"},
            "economy": {"energy": 80, "minerals": 150, "food": 60,
                        "alloys": 40, "consumer_goods": 30},
            "colonies": ["Habitat Alpha"],
            "known_empires": [],
            "fleets": [{"name": "Patrol", "power": 800, "location_system": "Home"}],
        },
        expected_actions=["IMPROVE_ECONOMY", "FOCUS_TECH", "BUILD_STARBASE"],
        tags=["early", "origin", "void_dwellers"],
    ),
    EvalScenario(
        name="late_game_crisis_prep",
        description="Late game, strong economy, must prepare for crisis.",
        empire={
            "ethics": ["Fanatic Militarist", "Materialist"],
            "civics": ["Distinguished Admiralty", "Technocracy"],
            "traits": ["Intelligent", "Strong"],
            "origin": "Prosperous Unification",
            "government": "Oligarchy",
        },
        state={
            "version": "4.3.4",
            "year": 2380, "month": 1,
            "empire": {"name": "Late Empire",
                       "ethics": ["Fanatic Militarist", "Materialist"],
                       "civics": ["Distinguished Admiralty", "Technocracy"],
                       "origin": "Prosperous Unification", "government": "Oligarchy"},
            "economy": {"energy": 800, "minerals": 1200, "food": 300,
                        "alloys": 400, "consumer_goods": 150},
            "colonies": ["World " + str(i) for i in range(8)],
            "known_empires": [
                {"name": "Neighbour", "attitude": "Cordial", "intel_level": "High"},
            ],
            "fleets": [
                {"name": "Grand Fleet", "power": 45000, "location_system": "Home"},
            ],
        },
        expected_actions=["BUILD_FLEET", "FOCUS_TECH", "IMPROVE_ECONOMY"],
        tags=["late", "crisis", "military"],
    ),
    EvalScenario(
        name="economy_crash",
        description="Energy deficit, must consolidate immediately.",
        empire={
            "ethics": ["Egalitarian", "Materialist"],
            "civics": ["Meritocracy"],
            "traits": ["Intelligent"],
            "origin": "Prosperous Unification",
            "government": "Democracy",
        },
        state={
            "version": "4.3.4",
            "year": 2240, "month": 6,
            "empire": {"name": "Crashing", "ethics": ["Egalitarian", "Materialist"],
                       "civics": ["Meritocracy"],
                       "origin": "Prosperous Unification", "government": "Democracy"},
            "economy": {"energy": -15, "minerals": 50, "food": 20,
                        "alloys": 5, "consumer_goods": 2},
            "colonies": ["Homeworld", "Colony A", "Colony B"],
            "known_empires": [],
            "fleets": [{"name": "Fleet", "power": 3000, "location_system": "Home"}],
        },
        expected_actions=["CONSOLIDATE", "IMPROVE_ECONOMY"],
        forbidden_actions=["EXPAND", "BUILD_FLEET", "PREPARE_WAR"],
        tags=["mid", "crisis", "economy"],
    ),
]


# ======================================================================== #
# Evaluation Engine
# ======================================================================== #

def evaluate_scenario(
    scenario: EvalScenario,
    llm_callable: callable | None = None,
    provider: object | None = None,
) -> EvalResult:
    """Evaluate a single scenario against a model."""
    from engine.llm_provider import LLMProviderError

    ruleset = generate_ruleset(**scenario.empire)
    personality = build_personality(**scenario.empire)
    prompt = build_prompt(ruleset, personality, scenario.state, None)

    result = EvalResult(scenario_name=scenario.name, action="", target=None, reason="")

    # Query model
    t0 = time.monotonic()
    try:
        if provider is not None:
            response = provider.complete(prompt)
            raw = response.text
        elif llm_callable is not None:
            raw = llm_callable(prompt)
        else:
            raw = (
                "ACTION: CONSOLIDATE\n"
                "TARGET: NONE\n"
                "REASON: No model provided."
            )
    except (LLMProviderError, Exception) as exc:
        result.error = str(exc)
        result.latency_ms = (time.monotonic() - t0) * 1000
        return result

    result.latency_ms = (time.monotonic() - t0) * 1000

    # Parse
    try:
        directive = parse_llm_response(raw)
        result.action = directive.action
        result.target = directive.target
        result.reason = directive.reason
        result.format_ok = True
    except ValueError:
        result.format_ok = False
        return result

    # Action valid (in whitelist)
    result.action_valid = directive.action in ALLOWED_ACTIONS

    # Action expected
    if scenario.expected_actions:
        result.action_expected = directive.action in scenario.expected_actions

    # Action not forbidden
    result.action_not_forbidden = directive.action not in scenario.forbidden_actions

    # FoW check — reason should not reference unseen info
    reason_lower = result.reason.lower()
    fow_violations = [
        "hidden fleet", "unknown system", "enemy economy",
        "crisis spawn", "shroud event", "precursor",
    ]
    result.fow_clean = not any(v in reason_lower for v in fow_violations)

    # Meta check — should not recommend forbidden weapons/patterns
    result.meta_clean = not any(
        w in reason_lower for w in FORBIDDEN_WEAPONS
    ) and not any(
        p in reason_lower for p in FORBIDDEN_FLEET_PATTERNS
    )

    # Full validation
    vresult = validate_directive(directive.to_dict(), ruleset, scenario.state)
    result.validation_passed = vresult.valid

    return result


def run_eval(
    provider: object | None = None,
    llm_callable: callable | None = None,
    scenarios: list[EvalScenario] | None = None,
    model_name: str = "unknown",
    output_dir: Path = Path("training/eval_results"),
    log_to_wandb: bool = False,
) -> EvalSummary:
    """Run the full evaluation suite.

    Parameters
    ----------
    provider : LLMProvider | None
        An LLM provider instance.
    llm_callable : callable | None
        Legacy callable fallback.
    scenarios : list | None
        Custom scenarios.  Defaults to the built-in SCENARIOS.
    model_name : str
        Human-readable model name for the report.
    output_dir : Path
        Where to save results.

    Returns
    -------
    EvalSummary
        Aggregate results.
    """
    if scenarios is None:
        scenarios = SCENARIOS

    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[EvalResult] = []
    for scenario in scenarios:
        log.info("Evaluating: %s", scenario.name)
        result = evaluate_scenario(scenario, llm_callable, provider)
        results.append(result)
        log.info(
            "  %s → %s (composite=%.2f, latency=%.0fms)",
            scenario.name, result.action, result.composite, result.latency_ms,
        )

    # Aggregate
    n = len(results) or 1
    summary = EvalSummary(
        model=model_name,
        timestamp=datetime.now().isoformat(),
        total_scenarios=len(results),
        format_pass_rate=sum(r.format_ok for r in results) / n,
        action_valid_rate=sum(r.action_valid for r in results) / n,
        expected_action_rate=sum(r.action_expected for r in results) / n,
        fow_clean_rate=sum(r.fow_clean for r in results) / n,
        meta_clean_rate=sum(r.meta_clean for r in results) / n,
        validation_pass_rate=sum(r.validation_passed for r in results) / n,
        mean_composite=sum(r.composite for r in results) / n,
        mean_latency_ms=sum(r.latency_ms for r in results) / n,
        results=[asdict(r) for r in results],
    )

    # Save
    out_path = output_dir / f"eval_{datetime.now():%Y%m%d_%H%M%S}.json"
    out_path.write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
    log.info(
        "Eval complete: model=%s composite=%.2f format=%.0f%% expected=%.0f%% fow=%.0f%%",
        model_name, summary.mean_composite,
        summary.format_pass_rate * 100,
        summary.expected_action_rate * 100,
        summary.fow_clean_rate * 100,
    )
    log.info("Results saved to %s", out_path)

    # Optional wandb logging
    if log_to_wandb:
        _log_wandb(summary, model_name)

    return summary


def _log_wandb(summary: EvalSummary, model_name: str) -> None:
    """Log eval metrics to Weights & Biases."""
    try:
        import wandb
    except ImportError:
        log.warning("wandb not installed — skipping. pip install wandb")
        return

    wandb.init(
        project="stellaris-overmind",
        name=f"eval-{model_name}",
        tags=["eval"],
        config={"model": model_name},
    )
    wandb.log({
        "eval/composite": summary.mean_composite,
        "eval/format_pass_rate": summary.format_pass_rate,
        "eval/action_valid_rate": summary.action_valid_rate,
        "eval/expected_action_rate": summary.expected_action_rate,
        "eval/fow_clean_rate": summary.fow_clean_rate,
        "eval/meta_clean_rate": summary.meta_clean_rate,
        "eval/validation_pass_rate": summary.validation_pass_rate,
        "eval/mean_latency_ms": summary.mean_latency_ms,
        "eval/total_scenarios": summary.total_scenarios,
    })
    wandb.finish()
    log.info("Eval metrics logged to wandb")


# ======================================================================== #
# CLI
# ======================================================================== #

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate a model against Stellaris decision benchmarks",
    )
    parser.add_argument("--model", default="", help="Model path or name")
    parser.add_argument("--provider", default="stub", help="Provider: stub | qwen-vllm | openai-compat")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", type=Path, default=Path("training/eval_results"))
    parser.add_argument("--wandb", action="store_true", help="Log metrics to wandb")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if args.provider == "stub":
        from engine.llm_provider import StubProvider
        provider = StubProvider()
        model_name = "stub"
    else:
        from engine.qwen_provider import OpenAICompatProvider
        provider = OpenAICompatProvider(
            base_url=args.base_url,
            model=args.model,
        )
        model_name = args.model or args.provider

    run_eval(
        provider=provider,
        model_name=model_name,
        output_dir=args.output,
        log_to_wandb=args.wandb,
    )


if __name__ == "__main__":
    main()
