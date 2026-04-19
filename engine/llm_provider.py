"""
LLM Provider — Abstract interface for LLM backends.

The Overmind engine is model-agnostic.  Any backend that can accept a text
prompt and return a text completion can be plugged in.

Implementations:
  - QwenVLLMProvider   → local Qwen2.5-Omni via vLLM Docker (OpenAI-compat API)
  - OpenAIProvider     → any OpenAI-compatible endpoint (remote or local)
  - StubProvider       → deterministic stub for testing (no GPU required)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Raw response from an LLM provider."""

    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class LLMProvider(ABC):
    """Protocol that every LLM backend must implement."""

    @abstractmethod
    def complete(self, prompt: str) -> LLMResponse:
        """Send *prompt* and return the model's text completion.

        Must be **synchronous** from the caller's perspective.
        Implementations may use async I/O internally but must block until
        the response is available.

        Raises ``LLMProviderError`` on transient failures.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return *True* if the backend is reachable and ready."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. ``'qwen-vllm-local'``)."""


class LLMProviderError(Exception):
    """Raised when the LLM backend is unreachable or returns an error."""


# ------------------------------------------------------------------ #
# Stub provider — for tests and offline development
# ------------------------------------------------------------------ #

class StubProvider(LLMProvider):
    """Returns a fixed CONSOLIDATE directive.  No GPU needed."""

    def complete(self, prompt: str) -> LLMResponse:
        return LLMResponse(
            text=(
                "ACTION: CONSOLIDATE\n"
                "TARGET: NONE\n"
                "REASON: No LLM connected; defaulting to safe posture "
                "per 4.3 meta (stability is scarce, consolidate first)."
            ),
            model="stub",
        )

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "stub"
