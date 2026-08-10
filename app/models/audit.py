"""Audit models."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    NOTE_UPLOAD = "NOTE_UPLOAD"
    NOTE_VALIDATE = "NOTE_VALIDATE"
    NOTE_ANALYZE = "NOTE_ANALYZE"
    IMPLEMENTATION_START = "IMPLEMENTATION_START"
    IMPLEMENTATION_COMPLETE = "IMPLEMENTATION_COMPLETE"
    IMPLEMENTATION_FAIL = "IMPLEMENTATION_FAIL"
    TRANSPORT_CREATE = "TRANSPORT_CREATE"
    TRANSPORT_RELEASE = "TRANSPORT_RELEASE"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    RBAC_DENIED = "RBAC_DENIED"
    PROMPT_SUBMIT = "PROMPT_SUBMIT"
    ROLLBACK_RECOMMENDED = "ROLLBACK_RECOMMENDED"


class AuditEntry(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: AuditAction
    actor: str = "anonymous"
    execution_id: str = ""
    system: str = ""
    detail: dict[str, Any] = Field(default_factory=dict)
    outcome: str = "ok"  # ok | error | denied