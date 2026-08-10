"""Transport request management agent.

Responsible for consolidating auto-created transports, optionally
releasing them (subject to system tier + RBAC + approval).
"""
from __future__ import annotations

from ..connectors.rfc_connector import RFCConnector
from ..models.execution import ExecutionRecord, SystemTier
from ..security.approval_workflow import ApprovalWorkflow
from ..security.rbac import RBAC
from .base import BaseAgent


class TransportManagerAgent(BaseAgent):
    name = "TransportManager"

    def __init__(
        self,
        rfc: RFCConnector,
        rbac: RBAC,
        approvals: ApprovalWorkflow,
    ) -> None:
        self.rfc = rfc
        self.rbac = rbac
        self.approvals = approvals

    # ------------------------------------------------------------------
    def _release_capability(self, tier: SystemTier) -> str:
        return {
            SystemTier.DEV: "transport.release.dev",
            SystemTier.QA: "transport.release.qa",
            SystemTier.PROD: "transport.release.prod",
        }[tier]

    def _is_prod(self, tier: SystemTier) -> bool:
        return tier == SystemTier.PROD

    # ------------------------------------------------------------------
    def release_transports(self, record: ExecutionRecord, force: bool = False) -> None:
        capability = self._release_capability(record.system_tier)
        if not self.rbac.can(record.requested_by, capability):
            self.log(
                record,
                "transport.release",
                f"User '{record.requested_by}' lacks '{capability}' — skipping release",
                level="WARN",
            )
            return

        # Approval gate for PROD
        if self._is_prod(record.system_tier) and self.approvals.is_required("PROD") and not force:
            self.log(
                record,
                "transport.release",
                "Production approval required — release deferred",
                level="WARN",
            )
            return

        for t in record.transports:
            if t.status == "released":
                continue
            resp = self.rfc.call("TR_RELEASE_REQUEST", IV_TRKORR=t.request_id)
            status = str(resp.get("EV_STATUS") or "").upper()
            if status == "RELEASED":
                t.status = "released"
                self.log(record, "transport.release", f"Released {t.request_id}")
            else:
                t.status = "failed"
                self.log(
                    record,
                    "transport.release",
                    f"Failed to release {t.request_id} (status={status})",
                    level="ERROR",
                )