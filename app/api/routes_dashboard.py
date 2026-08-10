"""Dashboard endpoints — history, execution detail, error dashboard."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models.execution import ExecutionStatus
from ..storage.job_store import get_job_store


router = APIRouter(tags=["dashboard"])


@router.get("/executions")
def list_executions(limit: int = Query(100, ge=1, le=500)) -> dict:
    return {"items": get_job_store().summary(limit=limit)}


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str) -> dict:
    r = get_job_store().get(execution_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return r.model_dump(mode="json")


@router.get("/executions/{execution_id}/logs")
def get_execution_logs(execution_id: str) -> dict:
    r = get_job_store().get(execution_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"execution_id": execution_id, "logs": [l.model_dump() for l in r.logs]}


@router.get("/errors")
def error_dashboard(limit: int = Query(100, ge=1, le=500)) -> dict:
    store = get_job_store()
    failed = [
        r
        for r in store.list(limit=limit * 3)
        if r.status in (ExecutionStatus.FAILED, ExecutionStatus.ROLLED_BACK) or r.error_summary
    ][:limit]
    return {
        "items": [
            {
                "execution_id": r.execution_id,
                "system": r.system_type.value,
                "tier": r.system_tier.value,
                "status": r.status.value,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "error_summary": r.error_summary,
                "rollback_recommendation": r.rollback_recommendation,
                "failing_notes": [
                    v.note_number for v in r.validation if not v.valid or not v.can_implement
                ],
            }
            for r in failed
        ]
    }