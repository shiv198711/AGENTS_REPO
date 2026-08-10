"""SAP Cloud Connector abstraction.

Wraps the notion of a Cloud Connector Location ID so BTP-hosted calls
can be routed to on-premise SAP systems. In simulate mode simply
records the intended destination and returns success.
"""
from __future__ import annotations

from typing import Any

from ..config import Settings, get_settings


class CloudConnector:
    def __init__(self, location_id: str = "") -> None:
        self.location_id = location_id or ""

    def resolve_destination(self, name: str) -> dict[str, Any]:
        return {
            "name": name,
            "location_id": self.location_id or "(none)",
            "resolved": True,
            "mode": "simulate",
        }

    def health(self) -> dict[str, Any]:
        return {
            "location_id": self.location_id or None,
            "configured": bool(self.location_id),
        }


def build_cloud_connector(settings: Settings | None = None) -> CloudConnector:
    s = settings or get_settings()
    return CloudConnector(location_id=s.sap_cloud_connector_location_id)