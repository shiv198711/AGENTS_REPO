"""Execution / orchestration domain models."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .sap_note import (
    NoteAnalysisResult,
    NoteValidationResult,
    SAPNoteInput,
    SAPNoteMetadata,
)


class SystemType(str, Enum):
    ECC = "ECC"
    S4HANA = "S4HANA"


class SystemTier(str, Enum):
    DEV = "DEV"
    QA = "QA"
    PROD = "PROD"


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    ANALYZING = "ANALYZING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    IMPLEMENTING = "IMPLEMENTING"
    POST_CHECK = "POST_CHECK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ImplementationLog(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    step: str
    level: str = "INFO"  # INFO | WARN | ERROR
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class TransportInfo(BaseModel):
    request_id: str = ""
    description: str = ""
    owner: str = ""
    status: str = "created"  # created | released | failed
    tasks: list[str] = Field(default_factory=list)


class CockpitCheckResult(BaseModel):
    cockpit: str  # CVI_COCKPIT | MDS_LOAD_COCKPIT
    passed: bool = True
    checks: dict[str, str] = Field(default_factory=dict)  # check -> status
    findings: list[str] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)


class ImplementationRequest(BaseModel):
    """Payload from UI to trigger orchestrated implementation."""

    system_type: SystemType
    system_tier: SystemTier = SystemTier.DEV
    notes: list[SAPNoteInput] = Field(default_factory=list)
    user_prompt: str = ""
    requested_by: str = "anonymous"
    approvals: list[str] = Field(default_factory=list)


class ExecutionRecord(BaseModel):
    execution_id: str
    system_type: SystemType
    system_tier: SystemTier = SystemTier.DEV
    status: ExecutionStatus = ExecutionStatus.PENDING
    requested_by: str = "anonymous"
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    finished_at: str = ""

    notes: list[SAPNoteInput] = Field(default_factory=list)
    metadata: list[SAPNoteMetadata] = Field(default_factory=list)
    validation: list[NoteValidationResult] = Field(default_factory=list)
    analysis: NoteAnalysisResult | None = None

    logs: list[ImplementationLog] = Field(default_factory=list)
    transports: list[TransportInfo] = Field(default_factory=list)
    cockpit_result: CockpitCheckResult | None = None

    error_summary: str = ""
    rollback_recommendation: str = ""
    user_prompt: str = ""