"""LLM client protocol used by CVI_ERROR_R_AUTO."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, runtime_checkable


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str = ""
    latency_ms: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class LLMClient(Protocol):
    provider_name: str
    supports_streaming: bool

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        ...

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterable[str]:
        ...

    def health(self) -> dict[str, Any]:
        ...