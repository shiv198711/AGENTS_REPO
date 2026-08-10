"""Approval workflow endpoints."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agents.orchestrator import Orchestrator
from ..llm.factory import build_llm
from ..models.audit import AuditAction
from ..security.approval_workflow import get_approval_workflow
from ..security.rbac import get_rbac
from ..storage.audit_store import get_audit_store


router = APIRouter(prefix="/approvals", tags=["approvals"])


class DecisionRequest(BaseModel):
    approver: str
    grant: bool
    reason: str = ""
    resume: bool = True
    release_transports: bool = False


@router.get("")
def list_approvals(pending_only: bool = True) -> dict:
    wf = get_approval_workflow()
    items = wf.list_pending() if pending_only else wf.list_all()
    return {
        "items": [
            {
                "approval_id": r.approval_id,
                "execution_id": r.execution_id,
                "system_tier": r.system_tier,
                "requester": r.requester,
                "status": r.status,
                "approver": r.approver,
                "reason": r.reason,
                "created_at": r.created_at,
                "decided_at": r.decided_at,
            }
            for r in items
        ]
    }


@router.post("/{approval_id}/decide")
def decide(approval_id: str, body: DecisionRequest) -> dict:
    wf = get_approval_workflow()
    audit = get_audit_store()
    rbac = get_rbac()

    if not rbac.can(body.approver, "approval.grant"):
        audit.log(
            AuditAction.RBAC_DENIED,
            actor=body.approver,
            detail={"capability": "approval.grant"},
            outcome="denied",
        )
        raise HTTPException(status_code=403, detail="Approver lacks 'approval.grant'")

    existing = wf.get(approval_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    if not rbac.sod_check(existing.requester, body.approver):
        raise HTTPException(
            status_code=403,
            detail="SoD violation: requester cannot approve their own request",
        )

    decided = wf.decide(approval_id, body.approver, body.grant, body.reason)
    if decided is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    audit.log(
        AuditAction.APPROVAL_GRANTED if body.grant else AuditAction.APPROVAL_REJECTED,
        actor=body.approver,
        execution_id=decided.execution_id,
        detail={"approval_id": approval_id, "reason": body.reason},
    )

    result: dict = {"approval": asdict(decided)}
    # Auto-resume execution after grant, if requested
    if body.grant and body.resume:
        orch = Orchestrator(build_llm())
        record = orch.resume_after_approval(
            execution_id=decided.execution_id,
            approval_id=approval_id,
            release_transports=body.release_transports,
        )
        if record is not None:
            result["execution"] = {
                "execution_id": record.execution_id,
                "status": record.status.value,
                "error_summary": record.error_summary,
            }
    return result