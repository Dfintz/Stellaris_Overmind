"""Tests for training pipeline — evaluate, distill, quantize."""

from __future__ import annotations

import json

from engine.config import TrainingConfig
from engine.llm_provider import StubProvider
from engine.ruleset_generator import ALLOWED_ACTIONS
from training.evaluate import (
    SCENARIOS,
    EvalResult,
    EvalSummary,
    evaluate_scenario,
    run_eval,
)

# ======================================================================== #
# Eval Scenarios Validation
# ======================================================================== #


class TestEvalScenarios:

    def test_all_scenarios_have_required_fields(self) -> None:
        for s in SCENARIOS:
            assert s.name, "Scenario missing name"
            assert s.empire, f"{s.name} missing empire"
            assert s.state, f"{s.name} missing state"
            assert s.state.get("version") == "4.3.4", f"{s.name} wrong version"

    def test_expected_actions_are_valid(self) -> None:
        for s in SCENARIOS:
            for a in s.expected_actions:
                assert a in ALLOWED_ACTIONS, f"{s.name}: {a} not in whitelist"

    def test_forbidden_actions_are_valid(self) -> None:
        for s in SCENARIOS:
            for a in s.forbidden_actions:
                assert a in ALLOWED_ACTIONS, f"{s.name}: {a} not in whitelist"

    def test_scenario_count(self) -> None:
        assert len(SCENARIOS) >= 5, "Need at least 5 eval scenarios"

    def test_covers_game_phases(self) -> None:
        tags = set()
        for s in SCENARIOS:
            tags.update(s.tags)
        assert "early" in tags
        assert "mid" in tags or "war" in tags
        assert "late" in tags


# ======================================================================== #
# Single Scenario Evaluation
# ======================================================================== #


class TestEvaluateScenario:

    def test_stub_produces_result(self) -> None:
        scenario = SCENARIOS[0]
        result = evaluate_scenario(scenario, provider=StubProvider())
        assert isinstance(result, EvalResult)
        assert result.format_ok is True
        assert result.action == "CONSOLIDATE"  # stub always returns CONSOLIDATE
        assert result.action_valid is True

    def test_format_check(self) -> None:
        scenario = SCENARIOS[0]
        result = evaluate_scenario(scenario, provider=StubProvider())
        assert result.format_ok is True

    def test_fow_clean_for_stub(self) -> None:
        scenario = SCENARIOS[0]
        result = evaluate_scenario(scenario, provider=StubProvider())
        assert result.fow_clean is True

    def test_meta_clean_for_stub(self) -> None:
        scenario = SCENARIOS[0]
        result = evaluate_scenario(scenario, provider=StubProvider())
        assert result.meta_clean is True

    def test_composite_score_range(self) -> None:
        scenario = SCENARIOS[0]
        result = evaluate_scenario(scenario, provider=StubProvider())
        assert 0.0 <= result.composite <= 1.0

    def test_latency_recorded(self) -> None:
        scenario = SCENARIOS[0]
        result = evaluate_scenario(scenario, provider=StubProvider())
        assert result.latency_ms >= 0

    def test_validation_passes_for_stub(self) -> None:
        scenario = SCENARIOS[0]
        result = evaluate_scenario(scenario, provider=StubProvider())
        assert result.validation_passed is True


# ======================================================================== #
# Full Eval Run
# ======================================================================== #


class TestRunEval:

    def test_full_eval_with_stub(self, tmp_path) -> None:
        summary = run_eval(
            provider=StubProvider(),
            model_name="test-stub",
            output_dir=tmp_path / "eval",
        )
        assert isinstance(summary, EvalSummary)
        assert summary.total_scenarios == len(SCENARIOS)
        assert summary.format_pass_rate == 1.0
        assert summary.action_valid_rate == 1.0
        assert summary.mean_composite > 0

    def test_eval_output_saved(self, tmp_path) -> None:
        run_eval(
            provider=StubProvider(),
            model_name="test",
            output_dir=tmp_path / "eval",
        )
        files = list((tmp_path / "eval").glob("eval_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["model"] == "test"
        assert len(data["results"]) == len(SCENARIOS)

    def test_custom_scenarios(self, tmp_path) -> None:
        custom = [SCENARIOS[0]]
        summary = run_eval(
            provider=StubProvider(),
            scenarios=custom,
            output_dir=tmp_path / "eval",
        )
        assert summary.total_scenarios == 1


# ======================================================================== #
# Distill Validation
# ======================================================================== #


class TestDistillValidation:

    def test_validate_teacher_data(self, tmp_path) -> None:
        from training.distill import validate_teacher_data

        # Create mock teacher data
        data_path = tmp_path / "teacher.jsonl"
        records = [
            {
                "messages": [
                    {"role": "system", "content": "test"},
                    {"role": "user", "content": "test prompt"},
                    {"role": "assistant", "content": "ACTION: BUILD_FLEET\nTARGET: Sol\nREASON: Fleet needed."},
                ],
            },
            {
                "messages": [
                    {"role": "system", "content": "test"},
                    {"role": "user", "content": "test prompt 2"},
                    {"role": "assistant", "content": "ACTION: FOCUS_TECH\nTARGET: NONE\nREASON: Research priority."},
                ],
            },
            {
                "messages": [{"role": "user", "content": "incomplete"}],
            },
        ]
        with open(data_path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        stats = validate_teacher_data(data_path)
        assert stats["total"] == 3
        assert stats["valid"] == 2
        assert stats["invalid"] == 1
        assert "BUILD_FLEET" in stats["action_distribution"]
        assert "FOCUS_TECH" in stats["action_distribution"]

    def test_empty_teacher_data(self, tmp_path) -> None:
        from training.distill import validate_teacher_data

        data_path = tmp_path / "empty.jsonl"
        data_path.write_text("")
        stats = validate_teacher_data(data_path)
        assert stats["valid"] == 0


# ======================================================================== #
# Quantize Calibration
# ======================================================================== #


class TestQuantizeCalibration:

    def test_build_calibration_data(self) -> None:
        from training.quantize import build_calibration_data

        prompts = build_calibration_data()
        assert len(prompts) == len(SCENARIOS)
        for p in prompts:
            assert isinstance(p, str)
            assert len(p) > 100  # non-trivial prompt
            assert "4.3.4" in p


# ======================================================================== #
# Config
# ======================================================================== #


class TestTrainingConfig:

    def test_defaults(self) -> None:
        cfg = TrainingConfig()
        assert cfg.sft_threshold == 0.3
        assert cfg.quantize_method == "gptq"
        assert cfg.quantize_bits == 4

    def test_custom(self) -> None:
        cfg = TrainingConfig(
            teacher_model="qwen/qwen-2.5-72b",
            quantize_method="awq",
        )
        assert cfg.teacher_model == "qwen/qwen-2.5-72b"
        assert cfg.quantize_method == "awq"
