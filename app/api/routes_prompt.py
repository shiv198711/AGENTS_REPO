"""User-prompt endpoint (free-form conversation with the AI agent)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..llm.factory import build_llm
from ..models.audit import AuditAction
from ..storage.audit_store import get_audit_store


router = APIRouter(prefix="/prompt", tags=["prompt"])


_SYSTEM = (
    "You are the CVI/MDS SAP Note Implementation Assistant. You help users "
    "reason about SAP Notes for Customer Vendor Integration (ECC "
    "CVI_COCKPIT) and Master Data Synchronization (S/4HANA "
    "MDS_LOAD_COCKPIT). Provide concise, senior-architect-quality answers. "
    "Never claim to have executed real transactions; describe what you "
    "would do and how the automated agent would run it."
)


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str = ""
    requested_by: str = "anonymous"
    temperature: float | None = None
    max_tokens: int | None = None


class PromptResponse(BaseModel):
    provider: str
    model: str
    latency_ms: int
    answer: str


@router.post("", response_model=PromptResponse)
def prompt(body: PromptRequest) -> PromptResponse:
    llm = build_llm()
    resp = llm.complete(
        body.prompt,
        system=body.system or _SYSTEM,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    get_audit_store().log(
        AuditAction.PROMPT_SUBMIT,
        actor=body.requested_by,
        detail={"chars": len(body.prompt), "provider": resp.provider},
    )
    return PromptResponse(
        provider=resp.provider,
        model=resp.model,
        latency_ms=resp.latency_ms,
        answer=resp.text,
    )