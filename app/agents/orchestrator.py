"""End-to-end orchestrator for the CVI/MDS SAP Note automation."""
from __future__ import annotations

from datetime import datetime, timezone

from ..connectors.cloud_connector import build_cloud_connector
from ..connectors.rfc_connector import build_rfc_connector
from ..connectors.sap_gui_automation import build_sap_gui_automation
from ..llm.base import LLMClient
from ..models.audit import AuditAction
from ..models.execution import (
    ExecutionRecord,
    ExecutionStatus,
    ImplementationRequest,
    SystemTier,
    SystemType,
)
from ..security.approval_workflow import get_approval_workflow
from ..security.rbac import get_rbac
from ..storage.audit_store import get_audit_store
from ..storage.job_store import get_job_store
from .base import BaseAgent
from .cvi_cockpit_agent import CVICockpitAgent
from .mds_load_cockpit_agent import MDSLoadCockpitAgent
from .note_analyzer import NoteAnalyzerAgent
from .note_validator import NoteValidatorAgent
from .snote_executor import SNoteExecutorAgent
from .transport_manager import TransportManagerAgent


class Orchestrator(BaseAgent):
    name = "Orchestrator"

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm
        self.rbac = get_rbac()
        self.approvals = get_approval_workflow()
        self.jobs = get_job_store()
        self.audit = get_audit_store()

    # ------------------------------------------------------------------
    def _implement_capability(self, tier: SystemTier) -> str:
        return {
            SystemTier.DEV: "note.implement.dev",
            SystemTier.QA: "note.implement.qa",
            SystemTier.PROD: "note.implement.prod",
        }[tier]

    def _finish(self, record: ExecutionRecord, status: ExecutionStatus) -> ExecutionRecord:
        record.status = status
        record.finished_at = datetime.now(timezone.utc).isoformat()
        self.jobs.save(record)
        return record

    # ------------------------------------------------------------------
    def new_record(self, request: ImplementationRequest) -> ExecutionRecord:
        return ExecutionRecord(
            execution_id=self.jobs.new_id(),
            system_type=request.system_type,
            system_tier=request.system_tier,
            requested_by=request.requested_by,
            notes=list(request.notes),
            user_prompt=request.user_prompt or "",
        )

    # ------------------------------------------------------------------
    def run(
        self,
        request: ImplementationRequest,
        release_transports: bool = False,
    ) -> ExecutionRecord:
        record = self.new_record(request)
        self.audit.log(
            AuditAction.IMPLEMENTATION_START,
            actor=record.requested_by,
            execution_id=record.execution_id,
            system=record.system_type.value,
            detail={"notes": [n.note_number for n in record.notes]},
        )

        # RBAC gate up-front
        capability = self._implement_capability(record.system_tier)
        if not self.rbac.can(record.requested_by, capability):
            record.error_summary = f"RBAC denied: '{capability}' for '{record.requested_by}'"
            self.audit.log(
                AuditAction.RBAC_DENIED,
                actor=record.requested_by,
                execution_id=record.execution_id,
                system=record.system_type.value,
                outcome="denied",
                detail={"capability": capability},
            )
            self.log(record, "rbac", record.error_summary, level="ERROR")
            return self._finish(record, ExecutionStatus.FAILED)

        # Build connectors
        rfc = build_rfc_connector(record.system_type.value)
        gui = build_sap_gui_automation()
        cc = build_cloud_connector()
        self.log(
            record,
            "connectors",
            "Connectors ready",
            detail={
                "rfc": {"system": rfc.system, "host": rfc.host, "real": rfc.real},
                "sap_gui_enabled": gui.enabled,
                "cloud_connector": cc.health(),
            },
        )

        try:
            with rfc:
                # 1. Validation
                record.status = ExecutionStatus.VALIDATING
                self.jobs.save(record)
                NoteValidatorAgent(rfc, self.rbac).run(record)
                self.audit.log(
                    AuditAction.NOTE_VALIDATE,
                    actor=record.requested_by,
                    execution_id=record.execution_id,
                    system=record.system_type.value,
                )

                # Short-circuit if none can be implemented
                if not any(v.can_implement for v in record.validation):
                    record.error_summary = "No notes are implementable after validation"
                    record.rollback_recommendation = (
                        "Review validation errors, correct prerequisites, resubmit."
                    )
                    return self._finish(record, ExecutionStatus.FAILED)

                # 2. Analysis
                record.status = ExecutionStatus.ANALYZING
                self.jobs.save(record)
                NoteAnalyzerAgent(self.llm).run(record)
                self.audit.log(
                    AuditAction.NOTE_ANALYZE,
                    actor=record.requested_by,
                    execution_id=record.execution_id,
                    system=record.system_type.value,
                )

                # 3. Approval gate for PROD
                if (
                    record.system_tier == SystemTier.PROD
                    and self.approvals.is_required("PROD")
                    and record.notes
                    and not record.notes[0].note_number.startswith("__AUTO__")
                ):
                    # Only auto-request approval — API caller must decide+resume separately
                    approval = self.approvals.create(
                        execution_id=record.execution_id,
                        system_tier="PROD",
                        requester=record.requested_by,
                        reason="Production SAP Note implementation",
                    )
                    self.audit.log(
                        AuditAction.APPROVAL_REQUESTED,
                        actor=record.requested_by,
                        execution_id=record.execution_id,
                        system=record.system_type.value,
                        detail={"approval_id": approval.approval_id},
                    )
                    self.log(
                        record,
                        "approval",
                        f"Approval required (id={approval.approval_id}) — pausing",
                        level="WARN",
                    )
                    return self._finish(record, ExecutionStatus.AWAITING_APPROVAL)

                # 4. Implementation
                record.status = ExecutionStatus.IMPLEMENTING
                self.jobs.save(record)
                SNoteExecutorAgent(rfc, gui).run(record)
                for t in record.transports:
                    self.audit.log(
                        AuditAction.TRANSPORT_CREATE,
                        actor=record.requested_by,
                        execution_id=record.execution_id,
                        system=record.system_type.value,
                        detail={"trkorr": t.request_id},
                    )

                # 5. Optional transport release
                if release_transports:
                    tm = TransportManagerAgent(rfc, self.rbac, self.approvals)
                    tm.release_transports(record)
                    for t in record.transports:
                        if t.status == "released":
                            self.audit.log(
                                AuditAction.TRANSPORT_RELEASE,
                                actor=record.requested_by,
                                execution_id=record.execution_id,
                                system=record.system_type.value,
                                detail={"trkorr": t.request_id},
                            )

                # 6. Post-implementation cockpit
                record.status = ExecutionStatus.POST_CHECK
                self.jobs.save(record)
                if record.system_type == SystemType.S4HANA:
                    MDSLoadCockpitAgent(rfc, gui).run(record)
                else:
                    CVICockpitAgent(rfc, gui).run(record)

            # 7. Wrap up
            self.audit.log(
                AuditAction.IMPLEMENTATION_COMPLETE,
                actor=record.requested_by,
                execution_id=record.execution_id,
                system=record.system_type.value,
            )
            return self._finish(record, ExecutionStatus.COMPLETED)

        except Exception as exc:  # noqa: BLE001
            record.error_summary = f"{type(exc).__name__}: {exc}"
            record.rollback_recommendation = (
                "Roll back transports created in this run via STMS; "
                "investigate root cause in application log before retry."
            )
            self.log(record, "error", record.error_summary, level="ERROR")
            self.audit.log(
                AuditAction.IMPLEMENTATION_FAIL,
                actor=record.requested_by,
                execution_id=record.execution_id,
                system=record.system_type.value,
                outcome="error",
                detail={"error": record.error_summary},
            )
            self.audit.log(
                AuditAction.ROLLBACK_RECOMMENDED,
                actor=record.requested_by,
                execution_id=record.execution_id,
                system=record.system_type.value,
                detail={"recommendation": record.rollback_recommendation},
            )
            return self._finish(record, ExecutionStatus.FAILED)

    # ------------------------------------------------------------------
    def resume_after_approval(
        self,
        execution_id: str,
        approval_id: str,
        release_transports: bool = False,
    ) -> ExecutionRecord | None:
        approval = self.approvals.get(approval_id)
        record = self.jobs.get(execution_id)
        if approval is None or record is None:
            return None
        if approval.status != "GRANTED":
            self.log(
                record,
                "approval",
                f"Approval {approval_id} not granted (status={approval.status})",
                level="WARN",
            )
            return record
        # Re-run implementation phase only
        rfc = build_rfc_connector(record.system_type.value)
        gui = build_sap_gui_automation()
        try:
            with rfc:
                record.status = ExecutionStatus.IMPLEMENTING
                self.jobs.save(record)
                SNoteExecutorAgent(rfc, gui).run(record)
                for t in record.transports:
                    self.audit.log(
                        AuditAction.TRANSPORT_CREATE,
                        actor=record.requested_by,
                        execution_id=record.execution_id,
                        system=record.system_type.value,
                        detail={"trkorr": t.request_id},
                    )
                if release_transports:
                    TransportManagerAgent(rfc, self.rbac, self.approvals).release_transports(
                        record, force=True
                    )
                    for t in record.transports:
                        if t.status == "released":
                            self.audit.log(
                                AuditAction.TRANSPORT_RELEASE,
                                actor=record.requested_by,
                                execution_id=record.execution_id,
                                system=record.system_type.value,
                                detail={"trkorr": t.request_id},
                            )
                record.status = ExecutionStatus.POST_CHECK
                if record.system_type == SystemType.S4HANA:
                    MDSLoadCockpitAgent(rfc, gui).run(record)
                else:
                    CVICockpitAgent(rfc, gui).run(record)
            self.audit.log(
                AuditAction.IMPLEMENTATION_COMPLETE,
                actor=record.requested_by,
                execution_id=record.execution_id,
                system=record.system_type.value,
            )
            return self._finish(record, ExecutionStatus.COMPLETED)
        except Exception as exc:  # noqa: BLE001
            record.error_summary = f"{type(exc).__name__}: {exc}"
            record.rollback_recommendation = (
                "Roll back transports created in this run via STMS; "
                "investigate root cause in application log before retry."
            )
            self.log(record, "error", record.error_summary, level="ERROR")
            self.audit.log(
                AuditAction.IMPLEMENTATION_FAIL,
                actor=record.requested_by,
                execution_id=record.execution_id,
                system=record.system_type.value,
                outcome="error",
                detail={"error": record.error_summary},
            )
            return self._finish(record, ExecutionStatus.FAILED)
