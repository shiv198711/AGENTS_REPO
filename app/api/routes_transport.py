"""Transport information endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..storage.job_store import get_job_store


router = APIRouter(prefix="/transports", tags=["transport"])


@router.get("")
def list_transports() -> dict:
    items: list[dict] = []
    for r in get_job_store().list(limit=500):
        for t in r.transports:
            items.append(
                {
                    "trkorr": t.request_id,
                    "description": t.description,
                    "owner": t.owner,
                    "status": t.status,
                    "tasks": t.tasks,
                    "execution_id": r.execution_id,
                    "system_type": r.system_type.value,
                    "system_tier": r.system_tier.value,
                }
            )
    return {"items": items}