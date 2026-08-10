"""OData connector — abstracts SAP Gateway / RAP service consumption.

Mocked by default. When a base URL is configured, `real=True` allows
HTTP calls via `httpx`.
"""
from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings, get_settings


class ODataConnector:
    def __init__(
        self,
        base_url: str = "",
        auth: tuple[str, str] | None = None,
        real: bool = False,
        timeout: int = 60,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.auth = auth
        self.real = bool(real and self.base_url)
        self.timeout = timeout

    # ------------------------------------------------------------------
    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.real:
            return self._mock_get(path, params or {})
        url = f"{self.base_url}/{path.lstrip('/')}"
        with httpx.Client(timeout=self.timeout, auth=self.auth) as client:
            resp = client.get(url, params=params, headers={"Accept": "application/json"})
            resp.raise_for_status()
            return resp.json()

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if not self.real:
            return self._mock_post(path, body)
        url = f"{self.base_url}/{path.lstrip('/')}"
        with httpx.Client(timeout=self.timeout, auth=self.auth) as client:
            resp = client.post(
                url,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    def _mock_get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "d": {
                "__metadata": {"type": "mock.Entity"},
                "path": path,
                "params": params,
                "results": [],
            }
        }

    def _mock_post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return {
            "d": {
                "__metadata": {"type": "mock.Entity"},
                "created": True,
                "path": path,
                "echo": body,
            }
        }


def build_odata_connector(settings: Settings | None = None) -> ODataConnector:
    s = settings or get_settings()
    return ODataConnector(
        base_url=s.sap_odata_base_url,
        real=bool(s.sap_odata_base_url),
    )