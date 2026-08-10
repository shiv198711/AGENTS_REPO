"""CVI_COCKPIT (ECC) post-implementation validation agent."""
from __future__ import annotations

from ..connectors.rfc_connector import RFCConnector
from ..connectors.sap_gui_automation import SAPGuiAutomation
from ..models.execution import CockpitCheckResult, ExecutionRecord
from .base import BaseAgent


class CVICockpitAgent(BaseAgent):
    name = "CVICockpit"

    def __init__(self, rfc: RFCConnector, gui: SAPGuiAutomation) -> None:
        self.rfc = rfc
        self.gui = gui

    def run(self, record: ExecutionRecord) -> CockpitCheckResult:
        self.log(record, "cvi.start", "Running CVI_COCKPIT checks")
        checks: dict[str, str] = {}

        # Business Partner sync
        bp = self.rfc.call("CVI_MAPPING_CHECK", IV_TARGET="BP")
        checks["business_partner_sync"] = str(bp.get("EV_STATUS") or "OK")

        # Customer sync
        cust = self.rfc.call("CVI_MAPPING_CHECK", IV_TARGET="CUSTOMER")
        checks["customer_sync"] = str(cust.get("EV_STATUS") or "OK")

        # Vendor sync
        vend = self.rfc.call("CVI_MAPPING_CHECK", IV_TARGET="VENDOR")
        checks["vendor_sync"] = str(vend.get("EV_STATUS") or "OK")

        # Data consistency
        cons = self.rfc.call("CVI_MAPPING_CHECK", IV_TARGET="CONSISTENCY")
        checks["data_consistency"] = str(cons.get("EV_STATUS") or "OK")

        # Mapping validation
        map_ = self.rfc.call("CVI_MAPPING_CHECK", IV_TARGET="MAPPING")
        checks["mapping_validation"] = str(map_.get("EV_STATUS") or "OK")

        # Error reconciliation
        recon = self.rfc.call("CVI_MAPPING_CHECK", IV_TARGET="RECONCILIATION")
        checks["error_reconciliation"] = str(recon.get("EV_STATUS") or "OK")

        findings: list[str] = []
        for k, v in checks.items():
            if v.upper() not in ("OK", "GREEN"):
                findings.append(f"{k}: {v}")

        remediation: list[str] = []
        if findings:
            remediation.append(
                "Re-run CVI_COCKPIT mapping validation after correcting flagged entities."
            )
            remediation.append(
                "Check MDS_CUST_MAP / MDS_VEND_MAP for unresolved mapping gaps."
            )

        if self.gui.enabled:
            self.gui.run_cvi_cockpit()

        passed = not findings
        result = CockpitCheckResult(
            cockpit="CVI_COCKPIT",
            passed=passed,
            checks=checks,
            findings=findings,
            remediation=remediation,
        )
        record.cockpit_result = result
        self.log(
            record,
            "cvi.done",
            f"CVI_COCKPIT passed={passed}",
            level="INFO" if passed else "WARN",
            detail={"findings": findings},
        )
        return result