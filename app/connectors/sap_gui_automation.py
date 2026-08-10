"""SAP GUI automation abstraction.

Represents SAP GUI Scripting for transactions with no API surface (SNOTE
older releases, CVI_COCKPIT dialog steps, MDS_LOAD_COCKPIT UI actions).
Mocked by default; a real implementation would use `win32com` on Windows
or a headless SAP GUI web-scripting runner.
"""
from __future__ import annotations

import time
from typing import Any

from ..config import Settings, get_settings


class SAPGuiAutomation:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.steps: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    def open_transaction(self, tcode: str) -> dict[str, Any]:
        return self._record("open_transaction", {"tcode": tcode})

    def field(self, name: str, value: str) -> dict[str, Any]:
        return self._record("set_field", {"name": name, "value": value})

    def press(self, button: str) -> dict[str, Any]:
        return self._record("press", {"button": button})

    def screenshot(self, label: str = "") -> dict[str, Any]:
        return self._record("screenshot", {"label": label})

    def close(self) -> dict[str, Any]:
        return self._record("close", {})

    # ------------------------------------------------------------------
    def run_snote(self, note_number: str) -> dict[str, Any]:
        """Convenience macro that describes SNOTE steps for a note."""
        self.open_transaction("SNOTE")
        self.field("NOTE_NUMBER", note_number)
        self.press("DOWNLOAD")
        self.press("IMPLEMENT")
        self.screenshot(f"snote_{note_number}")
        return {
            "note": note_number,
            "status": "SIMULATED_OK" if not self.enabled else "PENDING_REAL_IMPL",
            "steps": list(self.steps),
        }

    def run_cvi_cockpit(self) -> dict[str, Any]:
        self.open_transaction("CVI_COCKPIT")
        self.press("EXECUTE_CHECK_ALL")
        self.screenshot("cvi_cockpit_summary")
        return {"status": "SIMULATED_OK", "steps": list(self.steps)}

    def run_mds_load_cockpit(self) -> dict[str, Any]:
        self.open_transaction("MDS_LOAD_COCKPIT")
        self.press("EXECUTE_CHECK_ALL")
        self.screenshot("mds_cockpit_summary")
        return {"status": "SIMULATED_OK", "steps": list(self.steps)}

    # ------------------------------------------------------------------
    def _record(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        entry = {"action": action, "params": params, "ts": time.time()}
        self.steps.append(entry)
        return entry


def build_sap_gui_automation(settings: Settings | None = None) -> SAPGuiAutomation:
    s = settings or get_settings()
    return SAPGuiAutomation(enabled=s.enable_sap_gui_automation)