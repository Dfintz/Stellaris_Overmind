"""
Prompt Cache — Avoids re-serializing static prompt sections every tick.

The majority of the LLM prompt is static between ticks: system instructions,
meta rules, ruleset, personality, fleet templates, tradition/policy guidance.
Only the game state and event change.  This module caches the static prefix
and only rebuilds when the ruleset or game phase changes.

Token savings: ~40-60% of prompt tokens are static and only computed once
per phase transition instead of every tick.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class CachedPromptPrefix:
    """Immutable prefix valid until ruleset or phase changes."""

    text: str
    phase: str
    ruleset_version: str
    char_count: int


class PromptCache:
    """Caches the static portion of LLM prompts.

    The static prefix includes: system instructions, meta rules, ruleset,
    personality, phase priorities, domain guidance.  The dynamic suffix
    (game state, event) is appended fresh each tick.
    """

    def __init__(self) -> None:
        self._cache: dict[str, CachedPromptPrefix] = {}
        self._hits: int = 0
        self._misses: int = 0

    def get_or_build(
        self,
        cache_key: str,
        phase: str,
        ruleset_version: str,
        builder: callable,
    ) -> str:
        """Return cached prefix or build and cache a new one.

        Parameters
        ----------
        cache_key : str
            Unique key for this prompt type (e.g. "single", "domestic", "military").
        phase : str
            Current game phase ("early", "mid", "late").
        ruleset_version : str
            Ruleset version string — invalidates cache on reform.
        builder : callable
            Zero-arg callable that returns the static prefix string.
        """
        cached = self._cache.get(cache_key)
        if (
            cached is not None
            and cached.phase == phase
            and cached.ruleset_version == ruleset_version
        ):
            self._hits += 1
            return cached.text

        self._misses += 1
        text = builder()
        self._cache[cache_key] = CachedPromptPrefix(
            text=text,
            phase=phase,
            ruleset_version=ruleset_version,
            char_count=len(text),
        )
        log.debug(
            "Prompt cache MISS for '%s' (phase=%s, %d chars)",
            cache_key, phase, len(text),
        )
        return text

    def invalidate(self) -> None:
        """Clear all cached prefixes (e.g. after mid-game reform)."""
        self._cache.clear()
        log.debug("Prompt cache invalidated")

    @property
    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (~4 chars per token for English/JSON)."""
    return len(text) // 4


def _compact_json(obj: object) -> str:
    """Serialize to JSON with minimal whitespace (saves ~30% vs indent=2)."""
    return json.dumps(obj, separators=(",", ":"))
