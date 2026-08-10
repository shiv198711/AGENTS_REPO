"""SNOTE execution agent.

Given validated notes, orchestrates the SNOTE workflow via the RFC
connector (and, when required, SAP GUI automation):

  * Connect (already established by connector)
  * Download each note
  * Implement prerequisites first
  * Implement target notes
  * Capture logs
"""
from __future__ import annotations

from ..connectors.rfc_connector import RFCConnector
from ..connectors.sap_gui_automation import SAPGuiAutomation
from ..models.execution import ExecutionRecord, TransportInfo
from .base import BaseAgent


class SNoteExecutorAgent(BaseAgent):
    name = "SNoteExecutor"

    def __init__(self, rfc: RFCConnector, gui: SAPGuiAutomation) -> None:
        self.rfc = rfc
        self.gui = gui

    # ------------------------------------------------------------------
    def _implement_note(
        self, record: ExecutionRecord, note_number: str
    ) -> TransportInfo | None:
        self.log(record, "snote.download", f"Downloading note {note_number}")
        self.rfc.call("SCWN_API_NOTE_DOWNLOAD", IV_NUMBER=note_number)

        self.log(record, "snote.implement", f"Implementing note {note_number}")
        result = self.rfc.call("SCWN_API_NOTE_IMPLEMENT", IV_NUMBER=note_number)
        # Optional GUI trace
        if self.gui.enabled:
            self.gui.run_snote(note_number)

        status = str(result.get("EV_STATUS") or "").upper()
        trkorr = str(result.get("EV_TRKORR") or "")
        logs = result.get("ET_LOGS") or []
        for entry in logs:
            self.log(
                record,
                "snote.log",
                str(entry.get("MESSAGE") or ""),
                level="INFO" if entry.get("MSGTY") in ("S", "I") else "WARN",
            )
        if status != "IMPLEMENTED":
            self.log(
                record,
                "snote.implement",
                f"Unexpected status for note {note_number}: {status}",
                level="ERROR",
            )
            return None

        if trkorr:
            return TransportInfo(
                request_id=trkorr,
                description=f"Auto-created for SAP Note {note_number}",
                owner=record.requested_by,
                status="created",
                tasks=[f"Note {note_number}"],
            )
        return None

    # ------------------------------------------------------------------
    def run(self, record: ExecutionRecord) -> None:
        # Ordering: prereqs first (per validation), then the note itself.
        seen: set[str] = set()

        def _implement_and_track(nn: str) -> None:
            if nn in seen:
                return
            transport = self._implement_note(record, nn)
            if transport:
                record.transports.append(transport)
            seen.add(nn)

        for validation in record.validation:
            if not validation.can_implement:
                self.log(
                    record,
                    "snote.skip",
                    f"Skipping note {validation.note_number}: not implementable",
                    level="WARN",
                    detail={"errors": validation.errors},
                )
                continue
            for prereq in validation.prerequisites_ordered:
                _implement_and_track(prereq)
            _implement_and_track(validation.note_number)