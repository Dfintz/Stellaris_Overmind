"""
Hybrid Provider — Falls back between local and online LLM backends.

Supports three modes:
  - ``local``   → local model only (current default)
  - ``online``  → online API only (OpenAI-compat endpoint)
  - ``hybrid``  → try local first, fall back to online on failure

The online endpoint can be any OpenAI-compatible API: OpenRouter, Together,
Groq, a self-hosted proxy, etc.  The config uses ``[llm.online]`` to set
the endpoint separately from the local ``[llm]`` section.

This provider wraps two inner providers and adds:
  - Automatic failover (hybrid mode)
  - Token usage tracking across both backends
  - Latency comparison logging
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from engine.llm_provider import LLMProvider, LLMProviderError, LLMResponse

log = logging.getLogger(__name__)


@dataclass
class ProviderStats:
    """Tracks cumulative usage across local and online backends."""

    local_calls: int = 0
    online_calls: int = 0
    local_failures: int = 0
    online_failures: int = 0
    local_tokens: int = 0
    online_tokens: int = 0
    fallbacks: int = 0

    def to_dict(self) -> dict:
        total_calls = self.local_calls + self.online_calls
        return {
            "local_calls": self.local_calls,
            "online_calls": self.online_calls,
            "local_failures": self.local_failures,
            "online_failures": self.online_failures,
            "local_tokens": self.local_tokens,
            "online_tokens": self.online_tokens,
            "fallbacks": self.fallbacks,
            "total_calls": total_calls,
            "online_pct": (
                round(self.online_calls / total_calls * 100, 1)
                if total_calls > 0 else 0.0
            ),
        }


class HybridProvider(LLMProvider):
    """Wraps a local and an online provider with automatic failover.

    Modes:
      - ``local``  — only use ``local_provider``
      - ``online`` — only use ``online_provider``
      - ``hybrid`` — try local first; on failure, fall back to online
    """

    def __init__(
        self,
        local_provider: LLMProvider | None = None,
        online_provider: LLMProvider | None = None,
        mode: str = "local",
    ) -> None:
        if mode == "local" and local_provider is None:
            raise ValueError("Local provider required for mode='local'")
        if mode == "online" and online_provider is None:
            raise ValueError("Online provider required for mode='online'")
        if mode == "hybrid" and (local_provider is None or online_provider is None):
            raise ValueError("Both providers required for mode='hybrid'")

        self._local = local_provider
        self._online = online_provider
        self._mode = mode
        self.stats = ProviderStats()

    def complete(self, prompt: str) -> LLMResponse:
        if self._mode == "online":
            return self._call_online(prompt)

        if self._mode == "local":
            return self._call_local(prompt)

        # hybrid: try local, fall back to online
        try:
            return self._call_local(prompt)
        except LLMProviderError as local_err:
            self.stats.fallbacks += 1
            log.warning(
                "Local LLM failed (%s), falling back to online", local_err,
            )
            return self._call_online(prompt)

    def is_available(self) -> bool:
        if self._mode == "online":
            return self._online is not None and self._online.is_available()
        if self._mode == "local":
            return self._local is not None and self._local.is_available()
        # hybrid: either one being available is enough
        local_ok = self._local is not None and self._local.is_available()
        online_ok = self._online is not None and self._online.is_available()
        return local_ok or online_ok

    @property
    def name(self) -> str:
        parts = []
        if self._local is not None:
            parts.append(f"local={self._local.name}")
        if self._online is not None:
            parts.append(f"online={self._online.name}")
        return f"hybrid-{self._mode} ({', '.join(parts)})"

    def _call_local(self, prompt: str) -> LLMResponse:
        try:
            response = self._local.complete(prompt)
            self.stats.local_calls += 1
            self.stats.local_tokens += (
                response.prompt_tokens + response.completion_tokens
            )
            return response
        except LLMProviderError:
            self.stats.local_failures += 1
            raise

    def _call_online(self, prompt: str) -> LLMResponse:
        try:
            response = self._online.complete(prompt)
            self.stats.online_calls += 1
            self.stats.online_tokens += (
                response.prompt_tokens + response.completion_tokens
            )
            return response
        except LLMProviderError:
            self.stats.online_failures += 1
            raise
