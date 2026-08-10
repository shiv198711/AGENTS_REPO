"""SAP AI Core — Generative AI Hub — Anthropic Claude client.

Uses OAuth2 client-credentials flow to obtain a bearer token, then invokes
the Anthropic Messages API through AI Core's
``/v2/inference/deployments/{id}/invoke`` endpoint. Streaming uses the
``/invoke-with-response-stream`` endpoint and yields text-delta chunks.

Robustness features (matched to the SAPFULLSTACKNG reference):

  * 401 → refresh token once and retry.
  * 400 "temperature is deprecated" → drop the sampling parameter
    permanently and retry.
  * ``anthropic-version`` request header sent on every call.
  * Proper AI-Resource-Group routing.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterable, Iterator

import httpx

from .base import LLMResponse


log = logging.getLogger(__name__)


class AICoreAnthropicLLM:
    provider_name = "aicore-anthropic"
    supports_streaming = True

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        auth_url: str,
        base_url: str,
        deployment_id: str,
        resource_group: str = "default",
        anthropic_version: str = "bedrock-2023-05-31",
        timeout: int = 180,
        default_max_tokens: int = 4000,
        default_temperature: float = 0.2,
    ) -> None:
        missing = [
            k
            for k, v in {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_url": auth_url,
                "base_url": base_url,
                "deployment_id": deployment_id,
            }.items()
            if not v
        ]
        if missing:
            raise RuntimeError(f"AI Core config missing: {', '.join(missing)}")

        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = auth_url.rstrip("/")
        self.base_url = base_url.rstrip("/")
        self.deployment_id = deployment_id
        self.resource_group = resource_group or "default"
        self.anthropic_version = anthropic_version
        self.timeout = timeout
        self.default_max_tokens = default_max_tokens
        self.default_temperature = default_temperature

        self._token: str | None = None
        self._token_expiry: float = 0.0

        # Some deployments (e.g. Claude Opus 4.1) reject `temperature`.
        # Once we see that error we set this flag and drop the parameter
        # for all subsequent calls in this process.
        self._drop_temperature: bool = False

        self._invoke_url = (
            f"{self.base_url}/v2/inference/deployments/"
            f"{self.deployment_id}/invoke"
        )
        self._invoke_stream_url = (
            f"{self.base_url}/v2/inference/deployments/"
            f"{self.deployment_id}/invoke-with-response-stream"
        )

        log.info(
            "AICoreAnthropicLLM initialised (deployment=%s, resource_group=%s)",
            self.deployment_id,
            self.resource_group,
        )

    # ------------------------------------------------------------------
    # OAuth2 token
    # ------------------------------------------------------------------
    def _token_valid(self) -> bool:
        return bool(self._token) and time.time() < (self._token_expiry - 30)

    def _fetch_token(self) -> str:
        url = f"{self.auth_url}/oauth/token"
        try:
            resp = httpx.post(
                url,
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30.0,
            )
        except httpx.HTTPError as exc:  # pragma: no cover
            raise RuntimeError(f"AI Core OAuth request failed: {exc}") from exc

        if resp.status_code >= 400:
            raise RuntimeError(
                f"AI Core OAuth failed [{resp.status_code}]: {resp.text[:400]}"
            )
        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise RuntimeError("AI Core OAuth returned no access_token")
        self._token = access_token
        expires_in = int(data.get("expires_in", 3600))
        self._token_expiry = time.time() + max(expires_in - 60, 60)
        return access_token

    def _get_token(self) -> str:
        if self._token_valid():
            return self._token  # type: ignore[return-value]
        return self._fetch_token()

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------
    def _headers(self, token: str, stream: bool = False) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {token}",
            "AI-Resource-Group": self.resource_group,
            "Content-Type": "application/json",
            "anthropic-version": self.anthropic_version,
        }
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers

    def _build_body(
        self,
        prompt: str,
        system: str | None,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "anthropic_version": self.anthropic_version,
            "max_tokens": max_tokens or self.default_max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if not self._drop_temperature:
            body["temperature"] = (
                temperature if temperature is not None else self.default_temperature
            )
        if system:
            body["system"] = system
        if stream:
            body["stream"] = True
        return body

    @staticmethod
    def _temperature_rejected(status: int, err_text: str) -> bool:
        if status != 400 or not err_text:
            return False
        low = err_text.lower()
        return "temperature" in low and (
            "deprecat" in low or "not supported" in low or "unsupported" in low
        )

    # ------------------------------------------------------------------
    # Chat (non-streaming)
    # ------------------------------------------------------------------
    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        body = self._build_body(prompt, system, temperature, max_tokens, stream=False)
        last_exc: Exception | None = None

        for attempt in range(3):
            token = self._get_token()
            headers = self._headers(token, stream=False)
            t0 = time.time()
            try:
                resp = httpx.post(
                    self._invoke_url,
                    headers=headers,
                    json=body,
                    timeout=self.timeout,
                )
            except httpx.HTTPError as exc:  # pragma: no cover
                last_exc = exc
                log.warning(
                    "AI Core invoke transport error (attempt %d): %s",
                    attempt + 1,
                    exc,
                )
                continue

            elapsed_ms = int((time.time() - t0) * 1000)

            if resp.status_code == 401 and attempt == 0:
                log.info("AI Core token rejected — refreshing and retrying once.")
                self._token = None
                continue

            if resp.status_code == 400 and not self._drop_temperature:
                if self._temperature_rejected(resp.status_code, resp.text):
                    log.warning(
                        "AI Core deployment rejected `temperature` — "
                        "dropping it and retrying."
                    )
                    self._drop_temperature = True
                    body = self._build_body(
                        prompt, system, temperature, max_tokens, stream=False
                    )
                    continue

            if resp.status_code >= 400:
                log.error(
                    "AI Core invoke error %s: %s",
                    resp.status_code,
                    resp.text[:500],
                )
                raise RuntimeError(
                    f"AI Core invoke failed [{resp.status_code}]: "
                    f"{resp.text[:400]}"
                )

            data = resp.json()
            text = ""
            for block in data.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
            if not text and "completion" in data:
                text = str(data.get("completion") or "")

            return LLMResponse(
                text=text,
                provider=self.provider_name,
                model=str(data.get("model") or "claude-on-aicore"),
                latency_ms=elapsed_ms,
                raw=data,
            )

        raise RuntimeError(f"AI Core invoke failed after retries: {last_exc}")

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterable[str]:
        body = self._build_body(prompt, system, temperature, max_tokens, stream=True)
        last_exc: Exception | None = None

        for attempt in range(3):
            token = self._get_token()
            headers = self._headers(token, stream=True)
            try:
                with httpx.stream(
                    "POST",
                    self._invoke_stream_url,
                    headers=headers,
                    json=body,
                    timeout=self.timeout,
                ) as resp:
                    if resp.status_code == 401 and attempt == 0:
                        log.info("AI Core stream 401 — refreshing token.")
                        self._token = None
                        try:
                            resp.read()
                        except Exception:
                            pass
                        continue

                    if resp.status_code >= 400:
                        try:
                            err_text = resp.read().decode("utf-8", "replace")[:500]
                        except Exception:
                            err_text = ""
                        if (
                            resp.status_code == 400
                            and not self._drop_temperature
                            and self._temperature_rejected(resp.status_code, err_text)
                        ):
                            log.warning(
                                "AI Core stream rejected `temperature` — "
                                "dropping and retrying."
                            )
                            self._drop_temperature = True
                            body = self._build_body(
                                prompt, system, temperature, max_tokens, stream=True
                            )
                            continue
                        log.error(
                            "AI Core stream error %s: %s",
                            resp.status_code,
                            err_text,
                        )
                        raise RuntimeError(
                            f"AI Core stream failed [{resp.status_code}]: {err_text}"
                        )

                    for chunk in _iter_sse_deltas(resp.iter_lines()):
                        if chunk:
                            yield chunk
                    return
            except httpx.HTTPError as exc:  # pragma: no cover
                last_exc = exc
                log.warning(
                    "AI Core stream transport error (attempt %d): %s",
                    attempt + 1,
                    exc,
                )
                continue

        raise RuntimeError(f"AI Core stream failed after retries: {last_exc}")

    # ------------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        try:
            self._get_token()
            return {
                "provider": self.provider_name,
                "status": "ok",
                "reason": "",
                "deployment_id": self.deployment_id,
                "resource_group": self.resource_group,
                "supports_streaming": self.supports_streaming,
                "temperature_supported": not self._drop_temperature,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "provider": self.provider_name,
                "status": "error",
                "reason": str(exc),
                "deployment_id": self.deployment_id,
                "resource_group": self.resource_group,
                "supports_streaming": self.supports_streaming,
                "temperature_supported": not self._drop_temperature,
            }


# ---------------------------------------------------------------------------
# SSE parser
# ---------------------------------------------------------------------------
def _iter_sse_deltas(lines: Iterator[str]) -> Iterator[str]:
    """Yield text deltas from an Anthropic-shaped SSE stream."""
    for raw in lines:
        if raw is None:
            continue
        line = (
            raw.strip()
            if isinstance(raw, str)
            else raw.decode("utf-8", "replace").strip()
        )
        if not line or not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            evt = json.loads(payload)
        except json.JSONDecodeError:
            continue
        delta = evt.get("delta") if isinstance(evt, dict) else None
        if isinstance(delta, dict):
            if delta.get("type") == "text_delta":
                text = delta.get("text") or ""
                if text:
                    yield text
                    continue
            text = delta.get("text")
            if isinstance(text, str) and text:
                yield text
                continue
        if isinstance(evt, dict) and isinstance(evt.get("completion"), str):
            yield evt["completion"]