"""LLM factory — pick best available provider with safe fallback to Mock."""
from __future__ import annotations

import logging
from typing import Any

from ..config import Settings, get_settings
from .anthropic_client import AnthropicDirectLLM
from .base import LLMClient
from .mock_client import MockLLM
from .sap_genai_hub import AICoreAnthropicLLM


logger = logging.getLogger(__name__)


class _LLMBuildOutcome:
    def __init__(self) -> None:
        self.client: LLMClient | None = None
        self.provider: str = "mock"
        self.fallback_reason: str = ""
        self.init_error: str = ""


def _try_aicore(settings: Settings, outcome: _LLMBuildOutcome) -> LLMClient | None:
    if not settings.aicore_ready():
        outcome.fallback_reason = "AI Core credentials incomplete"
        return None
    try:
        return AICoreAnthropicLLM(
            client_id=settings.aicore_client_id,
            client_secret=settings.aicore_client_secret,
            auth_url=settings.aicore_auth_url,
            base_url=settings.aicore_base_url,
            deployment_id=settings.aicore_deployment_id,
            resource_group=settings.aicore_resource_group,
            anthropic_version=settings.aicore_anthropic_version,
            timeout=settings.llm_timeout_seconds,
            default_max_tokens=settings.llm_max_tokens,
            default_temperature=settings.llm_temperature,
        )
    except Exception as exc:  # noqa: BLE001
        outcome.init_error = f"AI Core init failed: {exc}"
        outcome.fallback_reason = outcome.init_error
        return None


def _try_anthropic(settings: Settings, outcome: _LLMBuildOutcome) -> LLMClient | None:
    if not settings.anthropic_ready():
        outcome.fallback_reason = "Direct Anthropic API key not configured"
        return None
    try:
        return AnthropicDirectLLM(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            timeout=settings.llm_timeout_seconds,
            default_max_tokens=settings.llm_max_tokens,
            default_temperature=settings.llm_temperature,
        )
    except Exception as exc:  # noqa: BLE001
        outcome.init_error = f"Anthropic init failed: {exc}"
        outcome.fallback_reason = outcome.init_error
        return None


def build_llm(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    outcome = _LLMBuildOutcome()

    attempted_provider = (settings.llm_provider or "mock").lower()

    if not settings.studio_llm_enabled:
        outcome.fallback_reason = "STUDIO_LLM_ENABLED=false"
        client = MockLLM(reason=outcome.fallback_reason)
        outcome.client = client
        outcome.provider = client.provider_name
        _last_build["outcome"] = outcome
        _last_build["provider"] = client.provider_name
        _last_build["attempted_provider"] = attempted_provider
        _last_build["settings"] = settings
        return client

    provider = attempted_provider
    client: LLMClient | None = None

    if provider == "aicore-anthropic":
        client = _try_aicore(settings, outcome)
        if client is None:
            # Fallback chain: try direct Anthropic
            client = _try_anthropic(settings, outcome)
    elif provider == "anthropic":
        client = _try_anthropic(settings, outcome)
    elif provider == "mock":
        outcome.fallback_reason = "LLM_PROVIDER=mock"
    else:
        outcome.fallback_reason = f"Unknown LLM_PROVIDER '{provider}'"

    if client is None:
        client = MockLLM(reason=outcome.fallback_reason or "no provider available")

    outcome.client = client
    outcome.provider = client.provider_name
    _last_build["outcome"] = outcome
    _last_build["provider"] = client.provider_name
    _last_build["attempted_provider"] = attempted_provider
    _last_build["settings"] = settings
    logger.info("LLM provider active: %s (reason=%s)", client.provider_name, outcome.fallback_reason)
    return client


# In-process diagnostics captured on the last build_llm call.
_last_build: dict[str, Any] = {}


def last_build_info() -> dict[str, Any]:
    outcome: _LLMBuildOutcome | None = _last_build.get("outcome")
    settings: Settings | None = _last_build.get("settings")
    if not outcome:
        return {"provider": "unknown"}
    return {
        "provider": outcome.provider,
        "attempted_provider": _last_build.get("attempted_provider", "unknown"),
        "fallback_reason": outcome.fallback_reason,
        "init_error": outcome.init_error,
        "supports_streaming": bool(getattr(outcome.client, "supports_streaming", False)),
        "aicore_ready": bool(settings.aicore_ready()) if settings else False,
        "anthropic_ready": bool(settings.anthropic_ready()) if settings else False,
    }
