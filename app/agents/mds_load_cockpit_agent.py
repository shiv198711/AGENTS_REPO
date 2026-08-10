"""MDS_LOAD_COCKPIT (S/4HANA) post-implementation validation agent."""
from __future__ import annotations

from ..connectors.rfc_connector import RFCConnector
from ..connectors.sap_gui_automation import SAPGuiAutomation
from ..models.execution import CockpitCheckResult, ExecutionRecord
from .base import BaseAgent


class MDSLoadCockpitAgent(BaseAgent):
    name = "MDSLoadCockpit"

    def __init__(self, rfc: RFCConnector, gui: SAPGuiAutomation) -> None:
        self.rfc = rfc
        self.gui = gui

    def run(self, record: ExecutionRecord) -> CockpitCheckResult:
        self.log(record, "mds.start", "Running MDS_LOAD_COCKPIT checks")

        checks: dict[str, str] = {}

        init = self.rfc.call("MDS_LOAD_CHECK", IV_MODE="INITIAL_LOAD_READY")
        checks["initial_load_readiness"] = str(init.get("EV_STATUS") or "OK")

        repl = self.rfc.call("MDS_LOAD_CHECK", IV_MODE="REPLICATION_READY")
        checks["replication_readiness"] = str(repl.get("EV_STATUS") or "OK")

        cons = self.rfc.call("MDS_LOAD_CHECK", IV_MODE="DATA_CONSISTENCY")
        checks["data_consistency"] = str(cons.get("EV_STATUS") or "OK")

        bp = self.rfc.call("MDS_LOAD_CHECK", IV_MODE="BP_SYNC")
        checks["business_partner_sync"] = str(bp.get("EV_STATUS") or "OK")

        recon = self.rfc.call("MDS_LOAD_CHECK", IV_MODE="ERROR_RECON")
        checks["error_reconciliation"] = str(recon.get("EV_STATUS") or "OK")

        pending = self.rfc.call("MDS_LOAD_CHECK", IV_MODE="PENDING_LOADS")
        pending_list = pending.get("ET_PENDING") or []
        checks["pending_load_validation"] = "OK" if not pending_list else f"{len(pending_list)} pending"

        findings: list[str] = []
        for k, v in checks.items():
            if v.upper() not in ("OK", "GREEN"):
                findings.append(f"{k}: {v}")

        remediation: list[str] = []
        if findings:
            remediation += [
                "Re-run initial load for affected entity sets from MDS_LOAD_COCKPIT.",
                "Reconcile MDGERROR/MDGPROCESSMESSAGES; retry replication after correction.",
            ]

        if self.gui.enabled:
            self.gui.run_mds_load_cockpit()

        passed = not findings
        result = CockpitCheckResult(
            cockpit="MDS_LOAD_COCKPIT",
            passed=passed,
            checks=checks,
            findings=findings,
            remediation=remediation,
        )
        record.cockpit_result = result
        self.log(
            record,
            "mds.done",
            f"MDS_LOAD_COCKPIT passed={passed}",
            level="INFO" if passed else "WARN",
            detail={"findings": findings},
        )
        return result