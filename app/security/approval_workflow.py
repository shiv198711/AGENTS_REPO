"""In-memory approval workflow for production changes."""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ApprovalRequest:
    approval_id: str
    execution_id: str
    system_tier: str
    requester: str
    reason: str = ""
    status: str = "PENDING"  # PENDING | GRANTED | REJECTED
    approver: str = ""
    decided_at: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ApprovalWorkflow:
    def __init__(self, required_for_prod: bool = True) -> None:
        self.required_for_prod = required_for_prod
        self._requests: dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()

    def is_required(self, system_tier: str) -> bool:
        return (system_tier or "").upper() == "PROD" and self.required_for_prod

    def create(
        self, execution_id: str, system_tier: str, requester: str, reason: str = ""
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            approval_id=uuid.uuid4().hex[:10],
            execution_id=execution_id,
            system_tier=system_tier.upper(),
            requester=requester,
            reason=reason,
        )
        with self._lock:
            self._requests[req.approval_id] = req
        return req

    def get(self, approval_id: str) -> ApprovalRequest | None:
        return self._requests.get(approval_id)

    def decide(
        self, approval_id: str, approver: str, grant: bool, reason: str = ""
    ) -> ApprovalRequest | None:
        with self._lock:
            req = self._requests.get(approval_id)
            if req is None:
                return None
            req.status = "GRANTED" if grant else "REJECTED"
            req.approver = approver
            req.decided_at = datetime.now(timezone.utc).isoformat()
            if reason:
                req.reason = f"{req.reason}\ndecision: {reason}".strip()
            return req

    def list_pending(self) -> list[ApprovalRequest]:
        return [r for r in self._requests.values() if r.status == "PENDING"]

    def list_all(self) -> list[ApprovalRequest]:
        return sorted(self._requests.values(), key=lambda r: r.created_at, reverse=True)


_wf: ApprovalWorkflow | None = None


def get_approval_workflow() -> ApprovalWorkflow:
    global _wf
    if _wf is None:
        from ..config import get_settings

        s = get_settings()
        _wf = ApprovalWorkflow(required_for_prod=s.approval_required_for_prod)
    return _wf