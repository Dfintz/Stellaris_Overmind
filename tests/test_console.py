"""Tests for engine/metrics.py and engine/console.py — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.console import ConsoleConfig, LogCapture, _format_histogram, _format_uptime
from engine.metrics import DashboardMetrics, MetricsCollector


# ======================================================================== #
# MetricsCollector Tests
# ======================================================================== #


class TestMetricsCollector:

    def test_initial_snapshot(self) -> None:
        mc = MetricsCollector()
        m = mc.snapshot()
        assert isinstance(m, DashboardMetrics)
        assert m.decisions_made == 0
        assert m.uptime_s >= 0

    def test_record_decision(self) -> None:
        mc = MetricsCollector()
        mc.record_decision("BUILD_FLEET", 150.0, tokens=120)
        m = mc.snapshot()
        assert m.last_action == "BUILD_FLEET"
        assert m.last_latency_ms == 150.0
        assert m.actions_histogram == {"BUILD_FLEET": 1}

    def test_action_histogram_accumulates(self) -> None:
        mc = MetricsCollector()
        mc.record_decision("BUILD_FLEET", 100.0)
        mc.record_decision("BUILD_FLEET", 120.0)
        mc.record_decision("FOCUS_TECH", 80.0)
        m = mc.snapshot()
        assert m.actions_histogram["BUILD_FLEET"] == 2
        assert m.actions_histogram["FOCUS_TECH"] == 1

    def test_avg_latency(self) -> None:
        mc = MetricsCollector()
        mc.record_decision("A", 100.0)
        mc.record_decision("B", 200.0)
        m = mc.snapshot()
        assert m.avg_latency_ms == pytest.approx(150.0)

    def test_tokens_per_second(self) -> None:
        mc = MetricsCollector()
        mc.record_decision("A", 1000.0, tokens=200)  # 200 tok / 1s = 200 tok/s
        m = mc.snapshot()
        assert m.tokens_per_second == pytest.approx(200.0)

    def test_update_from_loop(self) -> None:
        mc = MetricsCollector()

        class FakeStats:
            decisions_made = 42
            decisions_failed = 3
            llm_errors = 1
            validation_errors = 2
            snapshots_processed = 50
            last_action = "DEFEND"
            last_decision_time_ms = 250.0

        mc.update_from_loop(FakeStats())
        m = mc.snapshot()
        assert m.decisions_made == 42
        assert m.llm_errors == 1
        assert m.last_action == "DEFEND"

    def test_update_from_provider_dict(self) -> None:
        mc = MetricsCollector()
        mc.update_from_provider({
            "local_calls": 10,
            "online_calls": 5,
            "local_tokens": 5000,
            "online_tokens": 2000,
            "fallbacks": 2,
        })
        m = mc.snapshot()
        assert m.local_calls == 10
        assert m.online_calls == 5
        assert m.fallbacks == 2

    def test_update_from_cache(self) -> None:
        mc = MetricsCollector()
        mc.update_from_cache({"hits": 80, "misses": 20})
        m = mc.snapshot()
        assert m.cache_hits == 80
        assert m.cache_misses == 20

    def test_update_settings(self) -> None:
        mc = MetricsCollector()
        mc.update_settings(
            llm_mode="hybrid",
            council_enabled=True,
            planner_enabled=True,
            recording_enabled=False,
            game_year=2250,
        )
        m = mc.snapshot()
        assert m.llm_mode == "hybrid"
        assert m.council_enabled is True
        assert m.planner_enabled is True
        assert m.recording_enabled is False
        assert m.game_year == 2250


# ======================================================================== #
# DashboardMetrics Tests
# ======================================================================== #


class TestDashboardMetrics:

    def test_to_dict(self) -> None:
        m = DashboardMetrics(
            decisions_made=10,
            local_calls=8,
            online_calls=2,
            cache_hits=50,
            cache_misses=10,
        )
        d = m.to_dict()
        assert d["decisions_made"] == 10
        assert d["total_calls"] == 10
        assert d["cache_hit_rate"] == pytest.approx(83.3, abs=0.1)

    def test_zero_calls_no_division_error(self) -> None:
        m = DashboardMetrics()
        d = m.to_dict()
        assert d["cache_hit_rate"] == 0.0
        assert d["total_calls"] == 0


# ======================================================================== #
# Console Helpers
# ======================================================================== #


class TestConsoleHelpers:

    def test_format_uptime(self) -> None:
        assert _format_uptime(0) == "00:00:00"
        assert _format_uptime(3661) == "01:01:01"
        assert _format_uptime(90) == "00:01:30"

    def test_format_histogram_empty(self) -> None:
        assert _format_histogram({}) == "none yet"

    def test_format_histogram(self) -> None:
        hist = {"BUILD_FLEET": 10, "FOCUS_TECH": 5, "EXPAND": 3}
        result = _format_histogram(hist)
        assert "BUILD_FLEET=10" in result
        assert "FOCUS_TECH=5" in result

    def test_format_histogram_truncates(self) -> None:
        hist = {f"ACTION_{i}": i for i in range(10)}
        result = _format_histogram(hist, max_items=3)
        assert len(result.split(" ")) == 3


# ======================================================================== #
# LogCapture
# ======================================================================== #


class TestLogCapture:

    def test_captures_records(self) -> None:
        import logging

        capture = LogCapture(maxlen=5)
        capture.setFormatter(logging.Formatter("%(message)s"))

        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "hello world", (), None,
        )
        capture.emit(record)
        assert len(capture.records) == 1
        assert "hello world" in capture.records[0]

    def test_max_length(self) -> None:
        import logging

        capture = LogCapture(maxlen=3)
        capture.setFormatter(logging.Formatter("%(message)s"))

        for i in range(5):
            record = logging.LogRecord(
                "test", logging.INFO, "", 0, f"msg {i}", (), None,
            )
            capture.emit(record)

        assert len(capture.records) == 3
        assert "msg 2" in capture.records[0]
        assert "msg 4" in capture.records[2]


# ======================================================================== #
# ConsoleConfig
# ======================================================================== #


class TestConsoleConfig:

    def test_defaults(self) -> None:
        cfg = ConsoleConfig()
        assert cfg.llm_mode == "local"
        assert cfg.council_enabled is False
        assert cfg.planner_enabled is False
        assert cfg.recording_enabled is False

    def test_mode_cycle(self) -> None:
        from engine.console import _MODE_CYCLE
        assert _MODE_CYCLE == ["local", "online", "hybrid"]
        # Verify cycle wraps
        idx = _MODE_CYCLE.index("hybrid")
        next_mode = _MODE_CYCLE[(idx + 1) % len(_MODE_CYCLE)]
        assert next_mode == "local"
