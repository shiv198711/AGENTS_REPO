"""Filesystem-backed execution store.

Each execution is persisted as `data/jobs/<execution_id>.json` for durable
history, status tracking, log inspection and dashboard queries.
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from ..config import Settings, get_settings
from ..models.execution import ExecutionRecord


class JobStore:
    def __init__(self, base_path: Path) -> None:
        self.base = base_path
        self.base.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def _path(self, execution_id: str) -> Path:
        return self.base / f"{execution_id}.json"

    # ------------------------------------------------------------------
    def save(self, record: ExecutionRecord) -> None:
        with self._lock:
            data = record.model_dump(mode="json")
            self._path(record.execution_id).write_text(
                json.dumps(data, indent=2, default=str), encoding="utf-8"
            )

    def get(self, execution_id: str) -> ExecutionRecord | None:
        p = self._path(execution_id)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return ExecutionRecord.model_validate(data)
        except Exception:  # noqa: BLE001
            return None

    def list(self, limit: int = 100) -> list[ExecutionRecord]:
        files = sorted(
            self.base.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]
        out: list[ExecutionRecord] = []
        for f in files:
            try:
                out.append(ExecutionRecord.model_validate_json(f.read_text("utf-8")))
            except Exception:  # noqa: BLE001
                continue
        return out

    def summary(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            {
                "execution_id": r.execution_id,
                "system_type": r.system_type,
                "system_tier": r.system_tier,
                "status": r.status,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "requested_by": r.requested_by,
                "notes": [n.note_number for n in r.notes],
                "transport_ids": [t.request_id for t in r.transports if t.request_id],
                "error_summary": r.error_summary,
            }
            for r in self.list(limit=limit)
        ]


_store: JobStore | None = None


def get_job_store(settings: Settings | None = None) -> JobStore:
    global _store
    if _store is None:
        s = settings or get_settings()
        _store = JobStore(s.jobs_path)
    return _store