"""Append-only audit log store.

Persists one JSON-line per audit entry under `data/audit/audit.log`.
Suitable for demo / dev; production would ship these to SAP BTP
Audit Log service or Alert Notification service.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from ..models.audit import AuditAction, AuditEntry


class AuditStore:
    def __init__(self, base_path: Path) -> None:
        self.base = base_path
        self.base.mkdir(parents=True, exist_ok=True)
        self.file = self.base / "audit.log"
        self._lock = threading.RLock()

    def write(self, entry: AuditEntry) -> None:
        with self._lock:
            with self.file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry.model_dump(mode="json"), default=str))
                fh.write("\n")

    def log(
        self,
        action: AuditAction,
        actor: str = "anonymous",
        execution_id: str = "",
        system: str = "",
        detail: dict[str, Any] | None = None,
        outcome: str = "ok",
    ) -> AuditEntry:
        entry = AuditEntry(
            action=action,
            actor=actor,
            execution_id=execution_id,
            system=system,
            detail=detail or {},
            outcome=outcome,
        )
        self.write(entry)
        return entry

    def tail(self, limit: int = 100) -> list[AuditEntry]:
        if not self.file.exists():
            return []
        lines = self.file.read_text("utf-8").splitlines()[-limit:]
        out: list[AuditEntry] = []
        for ln in lines:
            try:
                out.append(AuditEntry.model_validate_json(ln))
            except Exception:  # noqa: BLE001
                continue
        return out


_store: AuditStore | None = None


def get_audit_store(settings: Settings | None = None) -> AuditStore:
    global _store
    if _store is None:
        s = settings or get_settings()
        _store = AuditStore(s.audit_path)
    return _store