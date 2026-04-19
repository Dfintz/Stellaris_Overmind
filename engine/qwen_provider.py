"""
Qwen vLLM Provider — Connects to Qwen2.5-Omni served via vLLM Docker.

The vLLM server exposes an OpenAI-compatible ``/v1/chat/completions`` endpoint.
This provider uses ``httpx`` (sync) to call it.  Falls back to the stdlib
``urllib`` if httpx is not installed.

Deployment:
  docker run --gpus all -p 8000:8000 qwenllm/qwen-omni:2.5-cu121 \\
      vllm serve Qwen/Qwen2.5-Omni-7B --port 8000 --dtype bfloat16

Or use the project's ``docker-compose.yml``.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from engine.llm_provider import LLMProvider, LLMProviderError, LLMResponse

log = logging.getLogger(__name__)


class QwenVLLMProvider(LLMProvider):
    """Talk to a local Qwen2.5-Omni instance via the vLLM OpenAI-compat API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        model: str = "Qwen/Qwen2.5-Omni-7B",
        max_tokens: int = 256,
        temperature: float = 0.3,
        timeout_s: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout_s = timeout_s

    # ------------------------------------------------------------------ #
    # LLMProvider interface
    # ------------------------------------------------------------------ #

    def complete(self, prompt: str) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a Stellaris 4.3.4 strategic AI advisor. "
                        "Respond ONLY in the exact format requested. "
                        "Never invent game mechanics."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "stream": False,
        }
        t0 = time.monotonic()
        data = self._post("/v1/chat/completions", payload)
        latency = (time.monotonic() - t0) * 1000

        try:
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(f"Unexpected vLLM response shape: {data}") from exc

        return LLMResponse(
            text=text.strip(),
            model=data.get("model", self._model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency,
        )

    def is_available(self) -> bool:
        try:
            self._get("/health")
            return True
        except Exception:
            return False

    @property
    def name(self) -> str:
        return f"qwen-vllm-local ({self._model})"

    # ------------------------------------------------------------------ #
    # HTTP helpers (stdlib — no external deps required)
    # ------------------------------------------------------------------ #

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self._base_url}{path}"
        payload = json.dumps(body).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode() if exc.fp else str(exc)
            raise LLMProviderError(
                f"vLLM returned HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError(
                f"Cannot reach vLLM at {url}: {exc.reason}"
            ) from exc

    def _get(self, path: str) -> dict:
        url = f"{self._base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            raise LLMProviderError(f"Health check failed: {exc}") from exc


class OpenAICompatProvider(LLMProvider):
    """Generic OpenAI-compatible provider for any endpoint (Ollama, LM Studio, etc.)."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        api_key: str = "not-needed",
        max_tokens: int = 256,
        temperature: float = 0.3,
        timeout_s: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout_s = timeout_s

    def complete(self, prompt: str) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a Stellaris 4.3.4 strategic AI advisor. "
                        "Respond ONLY in the exact format requested."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "stream": False,
        }
        t0 = time.monotonic()
        data = self._post("/v1/chat/completions", payload)
        latency = (time.monotonic() - t0) * 1000

        try:
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(f"Unexpected response: {data}") from exc

        return LLMResponse(
            text=text.strip(),
            model=data.get("model", self._model),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=latency,
        )

    def is_available(self) -> bool:
        try:
            self._get("/v1/models")
            return True
        except Exception:
            return False

    @property
    def name(self) -> str:
        return f"openai-compat ({self._model})"

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self._base_url}{path}"
        payload = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if self._api_key and self._api_key != "not-needed":
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode() if exc.fp else str(exc)
            raise LLMProviderError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError(f"Cannot reach {url}: {exc.reason}") from exc

    def _get(self, path: str) -> dict:
        url = f"{self._base_url}{path}"
        headers = {}
        if self._api_key and self._api_key != "not-needed":
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            raise LLMProviderError(f"Health check failed: {exc}") from exc
