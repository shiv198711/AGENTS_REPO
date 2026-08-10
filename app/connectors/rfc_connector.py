"""RFC connector — abstracts pyrfc.

By default the connector runs in *simulate* mode and produces plausible
response payloads for SAP Note handling, SNOTE actions, transport creation
and cockpit queries. When `ENABLE_REAL_RFC=true` the connector expects a
real `pyrfc.Connection` factory to be wired via `set_pyrfc_provider`.
"""
from __future__ import annotations

import random
import time
from typing import Any, Callable

from ..config import Settings, get_settings


_PYRFC_PROVIDER: Callable[..., Any] | None = None


def set_pyrfc_provider(provider: Callable[..., Any]) -> None:
    """Inject a real pyrfc.Connection factory at boot time."""
    global _PYRFC_PROVIDER
    _PYRFC_PROVIDER = provider


class RFCConnector:
    def __init__(
        self,
        system: str,
        host: str,
        client: str,
        user: str,
        password: str,
        sysnr: str = "00",
        real: bool = False,
    ) -> None:
        self.system = system
        self.host = host
        self.client = client
        self.user = user
        self.password = password
        self.sysnr = sysnr
        self.real = bool(real and _PYRFC_PROVIDER is not None)
        self._conn: Any = None

    # ------------------------------------------------------------------
    def open(self) -> None:
        if not self.real:
            return
        if _PYRFC_PROVIDER is None:
            return
        self._conn = _PYRFC_PROVIDER(
            ashost=self.host,
            sysnr=self.sysnr,
            client=self.client,
            user=self.user,
            passwd=self.password,
        )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None

    # ------------------------------------------------------------------
    def call(self, function_module: str, **kwargs: Any) -> dict[str, Any]:
        if self.real and self._conn is not None:
            return self._conn.call(function_module, **kwargs)
        return self._simulate(function_module, kwargs)

    # ------------------------------------------------------------------
    def _simulate(self, fm: str, params: dict[str, Any]) -> dict[str, Any]:
        # Deterministic-ish mocks for the FMs we care about.
        fm_up = fm.upper()
        time.sleep(0.02)  # tiny latency

        if fm_up == "SCWN_API_NOTE_EXISTS":
            note = params.get("IV_NUMBER", "")
            return {"EV_EXISTS": bool(note), "EV_TITLE": f"Note {note} (mock)"}

        if fm_up == "SCWN_API_NOTE_METADATA":
            note = params.get("IV_NUMBER", "")
            return {
                "ES_META": {
                    "NUMBER": note,
                    "TITLE": f"CVI/MDS correction note {note} (mock)",
                    "VERSION": "1",
                    "STATUS": "RELEASED",
                    "COMPONENT": "CA-MDG-BP",
                    "VALID_RELEASES": ["S4CORE 108", "SAP_APPL 606"],
                    "PREREQUISITES": [],
                    "CONFLICTS": [],
                    "KIND": "correction",
                    "MANUAL_ACTIVITIES": random.choice([False, False, True]),
                }
            }

        if fm_up == "SCWN_API_NOTE_IS_IMPLEMENTED":
            return {"EV_IMPLEMENTED": False}

        if fm_up == "SCWN_API_NOTE_DOWNLOAD":
            return {"EV_DOWNLOADED": True, "EV_SIZE_KB": 42}

        if fm_up == "SCWN_API_NOTE_IMPLEMENT":
            return {
                "EV_STATUS": "IMPLEMENTED",
                "EV_TRKORR": f"MOCKK9{random.randint(10000, 99999)}",
                "ET_LOGS": [
                    {"MSGTY": "S", "MESSAGE": "Prerequisites checked"},
                    {"MSGTY": "S", "MESSAGE": "Objects imported"},
                    {"MSGTY": "S", "MESSAGE": "Note activated"},
                ],
            }

        if fm_up == "TR_CREATE_REQUEST":
            return {
                "EV_TRKORR": f"MOCKK9{random.randint(10000, 99999)}",
                "EV_DESC": params.get("IV_TEXT", "CVI/MDS auto-created"),
            }

        if fm_up == "TR_RELEASE_REQUEST":
            return {"EV_STATUS": "RELEASED", "EV_TRKORR": params.get("IV_TRKORR", "")}

        if fm_up == "CVI_MAPPING_CHECK":
            return {
                "EV_STATUS": "OK",
                "ET_ISSUES": [],
            }

        if fm_up == "MDS_LOAD_CHECK":
            return {
                "EV_STATUS": "OK",
                "ET_PENDING": [],
            }

        # Fallback — echo params
        return {"EV_STATUS": "OK", "ET_ECHO": params, "_mock_fm": fm}

    # ------------------------------------------------------------------
    def __enter__(self) -> "RFCConnector":
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def build_rfc_connector(
    system: str,
    settings: Settings | None = None,
) -> RFCConnector:
    s = settings or get_settings()
    system_up = (system or "").upper()
    if system_up == "S4HANA":
        host, client, user, pw, sysnr = (
            s.sap_s4_host,
            s.sap_s4_client,
            s.sap_s4_user,
            s.sap_s4_password,
            s.sap_s4_sysnr,
        )
    else:
        host, client, user, pw, sysnr = (
            s.sap_ecc_host,
            s.sap_ecc_client,
            s.sap_ecc_user,
            s.sap_ecc_password,
            s.sap_ecc_sysnr,
        )
    return RFCConnector(
        system=system_up or "ECC",
        host=host or "mock.sap.local",
        client=client,
        user=user or "MOCK_USER",
        password=pw or "MOCK_PW",
        sysnr=sysnr or "00",
        real=s.enable_real_rfc,
    )