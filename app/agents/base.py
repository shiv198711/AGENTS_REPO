"""Base agent class with shared helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models.execution import ExecutionRecord, ImplementationLog


class BaseAgent:
    """Common utilities for concrete agents."""

    name: str = "BaseAgent"

    def log(
        self,
        record: ExecutionRecord,
        step: str,
        message: str,
        level: str = "INFO",
        detail: dict[str, Any] | None = None,
    ) -> ImplementationLog:
        entry = ImplementationLog(
            ts=datetime.now(timezone.utc).isoformat(),
            step=step,
            level=level,
            message=f"[{self.name}] {message}",
            detail=detail or {},
        )
        record.logs.append(entry)
        return entry