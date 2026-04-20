"""
Metrics — Unified runtime metrics aggregator for the Overmind dashboard.

Collects stats from LoopStats, ProviderStats, and PromptCache into a
single ``DashboardMetrics`` snapshot consumed by the console TUI and
(optionally) a Prometheus-compatible /metrics endpoint.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class DashboardMetrics:
    """Aggregated metrics snapshot for display."""

    # Loop stats
    decisions_made: int = 0
    decisions_failed: int = 0
    llm_errors: int = 0
    validation_errors: int = 0
    snapshots_processed: int = 0
    last_action: str = ""
    last_latency_ms: float = 0.0

    # Provider stats
    local_calls: int = 0
    online_calls: int = 0
    local_failures: int = 0
    online_failures: int = 0
    local_tokens: int = 0
    online_tokens: int = 0
    fallbacks: int = 0

    # Cache stats
    cache_hits: int = 0
    cache_misses: int = 0

    # Computed
    uptime_s: float = 0.0
    avg_latency_ms: float = 0.0
    tokens_per_second: float = 0.0
    actions_histogram: dict[str, int] = field(default_factory=dict)

    # Live settings
    llm_mode: str = "local"
    council_enabled: bool = False
    planner_enabled: bool = False
    recording_enabled: bool = False
    game_year: int = 0

    def to_dict(self) -> dict:
        total_calls = self.local_calls + self.online_calls
        total_tokens = self.local_tokens + self.online_tokens
        return {
            "decisions_made": self.decisions_made,
            "decisions_failed": self.decisions_failed,
            "llm_errors": self.llm_errors,
            "validation_errors": self.validation_errors,
            "last_action": self.last_action,
            "last_latency_ms": round(self.last_latency_ms, 1),
            "local_calls": self.local_calls,
            "online_calls": self.online_calls,
            "fallbacks": self.fallbacks,
            "total_tokens": total_tokens,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": (
                round(self.cache_hits / (self.cache_hits + self.cache_misses) * 100, 1)
                if (self.cache_hits + self.cache_misses) > 0 else 0.0
            ),
            "uptime_s": round(self.uptime_s, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "tokens_per_second": round(self.tokens_per_second, 1),
            "actions_histogram": self.actions_histogram,
            "total_calls": total_calls,
        }


class MetricsCollector:
    """Collects and aggregates metrics from engine components.

    Call ``update()`` after each tick to refresh. Call ``snapshot()``
    to get the current ``DashboardMetrics``.
    """

    def __init__(self) -> None:
        self._start_time = time.monotonic()
        self._latencies: deque[float] = deque(maxlen=100)
        self._token_times: deque[tuple[int, float]] = deque(maxlen=100)
        self._actions: dict[str, int] = {}
        self._metrics = DashboardMetrics()

    def record_decision(
        self,
        action: str,
        latency_ms: float,
        tokens: int = 0,
    ) -> None:
        """Record a completed decision."""
        self._latencies.append(latency_ms)
        self._actions[action] = self._actions.get(action, 0) + 1
        if tokens > 0:
            self._token_times.append((tokens, latency_ms))
        self._metrics.last_action = action
        self._metrics.last_latency_ms = latency_ms

    def update_from_loop(self, loop_stats: object) -> None:
        """Pull stats from a LoopStats dataclass."""
        self._metrics.decisions_made = getattr(loop_stats, "decisions_made", 0)
        self._metrics.decisions_failed = getattr(loop_stats, "decisions_failed", 0)
        self._metrics.llm_errors = getattr(loop_stats, "llm_errors", 0)
        self._metrics.validation_errors = getattr(loop_stats, "validation_errors", 0)
        self._metrics.snapshots_processed = getattr(loop_stats, "snapshots_processed", 0)
        self._metrics.last_action = getattr(loop_stats, "last_action", "")
        self._metrics.last_latency_ms = getattr(loop_stats, "last_decision_time_ms", 0.0)

    def update_from_provider(self, provider_stats: object) -> None:
        """Pull stats from a ProviderStats dataclass (or dict)."""
        if isinstance(provider_stats, dict):
            d = provider_stats
        elif hasattr(provider_stats, "to_dict"):
            d = provider_stats.to_dict()
        else:
            return
        self._metrics.local_calls = d.get("local_calls", 0)
        self._metrics.online_calls = d.get("online_calls", 0)
        self._metrics.local_failures = d.get("local_failures", 0)
        self._metrics.online_failures = d.get("online_failures", 0)
        self._metrics.local_tokens = d.get("local_tokens", 0)
        self._metrics.online_tokens = d.get("online_tokens", 0)
        self._metrics.fallbacks = d.get("fallbacks", 0)

    def update_from_cache(self, cache_stats: dict) -> None:
        """Pull stats from PromptCache.stats."""
        self._metrics.cache_hits = cache_stats.get("hits", 0)
        self._metrics.cache_misses = cache_stats.get("misses", 0)

    def update_settings(
        self,
        llm_mode: str = "",
        council_enabled: bool | None = None,
        planner_enabled: bool | None = None,
        recording_enabled: bool | None = None,
        game_year: int | None = None,
    ) -> None:
        """Update live settings display."""
        if llm_mode:
            self._metrics.llm_mode = llm_mode
        if council_enabled is not None:
            self._metrics.council_enabled = council_enabled
        if planner_enabled is not None:
            self._metrics.planner_enabled = planner_enabled
        if recording_enabled is not None:
            self._metrics.recording_enabled = recording_enabled
        if game_year is not None:
            self._metrics.game_year = game_year

    def snapshot(self) -> DashboardMetrics:
        """Return current metrics snapshot."""
        m = self._metrics
        m.uptime_s = time.monotonic() - self._start_time
        m.actions_histogram = dict(self._actions)

        # Avg latency
        if self._latencies:
            m.avg_latency_ms = sum(self._latencies) / len(self._latencies)

        # Tokens per second
        if self._token_times:
            total_tok = sum(t for t, _ in self._token_times)
            total_ms = sum(ms for _, ms in self._token_times)
            m.tokens_per_second = (total_tok / total_ms * 1000) if total_ms > 0 else 0.0

        return m
