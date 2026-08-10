"""Direct Anthropic Messages API client.

Used as a secondary provider when a raw ANTHROPIC_API_KEY is available.
Falls back gracefully by raising `RuntimeError` when misconfigured; the
factory will catch and downgrade to MockLLM.
"""
from __future__ import annotations

import time
from typing import Any, Iterable

import httpx

from .base import LLMResponse


ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class AnthropicDirectLLM:
    provider_name = "anthropic"
    supports_streaming = False

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-latest",
        timeout: int = 180,
        default_max_tokens: int = 4000,
        default_temperature: float = 0.2,
    ) -> None:
        if not api_key:
            raise RuntimeError("AnthropicDirectLLM requires ANTHROPIC_API_KEY")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.default_max_tokens = default_max_tokens
        self.default_temperature = default_temperature

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.default_max_tokens,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        t0 = time.time()
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(ANTHROPIC_URL, headers=self._headers(), json=body)
            resp.raise_for_status()
            data = resp.json()
        text = ""
        for block in data.get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "text":
                text += block.get("text", "")
        return LLMResponse(
            text=text,
            provider=self.provider_name,
            model=self.model,
            latency_ms=int((time.time() - t0) * 1000),
            raw=data,
        )

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterable[str]:
        # Non-streaming provider — yield the full response as a single chunk.
        yield self.complete(
            prompt, system=system, temperature=temperature, max_tokens=max_tokens
        ).text

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "status": "configured" if self.api_key else "missing_key",
            "model": self.model,
            "supports_streaming": self.supports_streaming,
        }