"""Tests for prompt_cache, hybrid_provider, and mcp_client — Stellaris 4.3.4."""

from __future__ import annotations

import pytest

from engine.hybrid_provider import HybridProvider, ProviderStats
from engine.llm_provider import LLMProvider, LLMProviderError, LLMResponse, StubProvider
from engine.mcp_client import MCPClient, MCPToolResult
from engine.prompt_cache import PromptCache, _compact_json, estimate_tokens


# ======================================================================== #
# Prompt Cache Tests
# ======================================================================== #


class TestPromptCache:

    def test_cache_hit(self) -> None:
        cache = PromptCache()
        built = cache.get_or_build("test", "early", "4.3.4", lambda: "prefix text")
        assert built == "prefix text"
        assert cache.stats["misses"] == 1
        assert cache.stats["hits"] == 0

        # Second call: should hit
        built2 = cache.get_or_build("test", "early", "4.3.4", lambda: "WRONG")
        assert built2 == "prefix text"
        assert cache.stats["hits"] == 1

    def test_cache_invalidate_on_phase_change(self) -> None:
        cache = PromptCache()
        cache.get_or_build("test", "early", "4.3.4", lambda: "early text")
        result = cache.get_or_build("test", "mid", "4.3.4", lambda: "mid text")
        assert result == "mid text"
        assert cache.stats["misses"] == 2

    def test_cache_invalidate_on_version_change(self) -> None:
        cache = PromptCache()
        cache.get_or_build("test", "early", "4.3.4", lambda: "v1")
        result = cache.get_or_build("test", "early", "4.3.5", lambda: "v2")
        assert result == "v2"

    def test_separate_keys(self) -> None:
        cache = PromptCache()
        cache.get_or_build("domestic", "early", "4.3.4", lambda: "dom")
        cache.get_or_build("military", "early", "4.3.4", lambda: "mil")
        assert cache.stats["misses"] == 2

        # Each key has its own cache
        dom = cache.get_or_build("domestic", "early", "4.3.4", lambda: "X")
        mil = cache.get_or_build("military", "early", "4.3.4", lambda: "X")
        assert dom == "dom"
        assert mil == "mil"
        assert cache.stats["hits"] == 2

    def test_invalidate_clears_all(self) -> None:
        cache = PromptCache()
        cache.get_or_build("a", "early", "4.3.4", lambda: "aaa")
        cache.invalidate()
        result = cache.get_or_build("a", "early", "4.3.4", lambda: "bbb")
        assert result == "bbb"


class TestTokenEstimation:

    def test_estimate(self) -> None:
        assert estimate_tokens("") == 0
        assert estimate_tokens("a" * 400) == 100

    def test_compact_json(self) -> None:
        data = {"key": "value", "list": [1, 2, 3]}
        compact = _compact_json(data)
        assert " " not in compact
        assert '"key":"value"' in compact


# ======================================================================== #
# Hybrid Provider Tests
# ======================================================================== #


class OnlineStub(LLMProvider):
    """Simulates an online provider."""

    def complete(self, prompt: str) -> LLMResponse:
        return LLMResponse(
            text="ACTION: FOCUS_TECH\nTARGET: NONE\nREASON: Online model response.",
            model="online-stub",
            prompt_tokens=100,
            completion_tokens=20,
        )

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "online-stub"


class FailingLocal(LLMProvider):
    """Local provider that always fails."""

    def complete(self, prompt: str) -> LLMResponse:
        raise LLMProviderError("GPU out of memory")

    def is_available(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return "failing-local"


class TestHybridProvider:

    def test_local_mode(self) -> None:
        provider = HybridProvider(
            local_provider=StubProvider(),
            mode="local",
        )
        resp = provider.complete("test")
        assert "CONSOLIDATE" in resp.text
        assert provider.stats.local_calls == 1
        assert provider.stats.online_calls == 0

    def test_online_mode(self) -> None:
        provider = HybridProvider(
            online_provider=OnlineStub(),
            mode="online",
        )
        resp = provider.complete("test")
        assert "FOCUS_TECH" in resp.text
        assert provider.stats.online_calls == 1
        assert provider.stats.local_calls == 0

    def test_hybrid_uses_local_first(self) -> None:
        provider = HybridProvider(
            local_provider=StubProvider(),
            online_provider=OnlineStub(),
            mode="hybrid",
        )
        resp = provider.complete("test")
        assert "CONSOLIDATE" in resp.text  # local stub wins
        assert provider.stats.local_calls == 1
        assert provider.stats.online_calls == 0
        assert provider.stats.fallbacks == 0

    def test_hybrid_falls_back_on_failure(self) -> None:
        provider = HybridProvider(
            local_provider=FailingLocal(),
            online_provider=OnlineStub(),
            mode="hybrid",
        )
        resp = provider.complete("test")
        assert "FOCUS_TECH" in resp.text  # online fallback
        assert provider.stats.fallbacks == 1
        assert provider.stats.local_failures == 1
        assert provider.stats.online_calls == 1

    def test_hybrid_is_available_if_either_works(self) -> None:
        provider = HybridProvider(
            local_provider=FailingLocal(),
            online_provider=OnlineStub(),
            mode="hybrid",
        )
        assert provider.is_available() is True

    def test_local_mode_requires_local_provider(self) -> None:
        with pytest.raises(ValueError, match="Local provider"):
            HybridProvider(mode="local")

    def test_online_mode_requires_online_provider(self) -> None:
        with pytest.raises(ValueError, match="Online provider"):
            HybridProvider(mode="online")

    def test_hybrid_requires_both(self) -> None:
        with pytest.raises(ValueError, match="Both providers"):
            HybridProvider(local_provider=StubProvider(), mode="hybrid")

    def test_name_describes_mode(self) -> None:
        provider = HybridProvider(
            local_provider=StubProvider(),
            online_provider=OnlineStub(),
            mode="hybrid",
        )
        assert "hybrid" in provider.name
        assert "local=stub" in provider.name
        assert "online=online-stub" in provider.name

    def test_token_tracking(self) -> None:
        provider = HybridProvider(
            local_provider=FailingLocal(),
            online_provider=OnlineStub(),
            mode="hybrid",
        )
        provider.complete("test")
        stats = provider.stats.to_dict()
        assert stats["online_tokens"] == 120
        assert stats["online_pct"] == 100.0

    def test_stats_dict(self) -> None:
        stats = ProviderStats()
        d = stats.to_dict()
        assert d["total_calls"] == 0
        assert d["online_pct"] == 0.0


# ======================================================================== #
# MCP Client Tests (unit — no actual server)
# ======================================================================== #


class TestMCPToolResult:

    def test_text_extraction(self) -> None:
        result = MCPToolResult(
            tool_name="test",
            content=[{"type": "text", "text": '{"origins": ["Prosperous Unification"]}'}],
        )
        assert "Prosperous Unification" in result.text

    def test_data_json_parse(self) -> None:
        result = MCPToolResult(
            tool_name="test",
            content=[{"type": "text", "text": '{"count": 42}'}],
        )
        assert result.data == {"count": 42}

    def test_data_fallback_to_text(self) -> None:
        result = MCPToolResult(
            tool_name="test",
            content=[{"type": "text", "text": "not json"}],
        )
        assert result.data == "not json"

    def test_empty_content(self) -> None:
        result = MCPToolResult(tool_name="test", content=[])
        assert result.text == ""
        assert result.data == ""

    def test_is_error(self) -> None:
        result = MCPToolResult(
            tool_name="test",
            content=[{"type": "text", "text": "error msg"}],
            is_error=True,
        )
        assert result.is_error


class TestMCPClient:

    def test_init(self) -> None:
        client = MCPClient("node", ["test.js"])
        assert client._command == "node"
        assert client._args == ["test.js"]

    def test_context_manager(self) -> None:
        client = MCPClient("echo", ["test"])
        with client:
            pass
        # Should not raise
