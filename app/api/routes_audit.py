"""Audit log endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..storage.audit_store import get_audit_store


router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(limit: int = Query(200, ge=1, le=1000)) -> dict:
    return {"items": [e.model_dump() for e in get_audit_store().tail(limit=limit)]}