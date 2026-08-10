"""Credential vault abstraction.

Reads SAP backend credentials from `Settings` (which loads them from
environment / `.env`). Values are exposed as masked previews; the raw
password is only accessible through `get_secret()` behind an explicit
call so log statements never accidentally leak it.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Settings, get_settings


@dataclass
class SAPCredential:
    system: str
    host: str
    client: str
    user: str
    password_len: int

    def masked(self) -> dict[str, str]:
        return {
            "system": self.system,
            "host": self.host or "(unset)",
            "client": self.client or "(unset)",
            "user": self.user or "(unset)",
            "password": "*" * self.password_len if self.password_len else "(unset)",
        }


class CredentialVault:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ecc(self) -> SAPCredential:
        s = self.settings
        return SAPCredential(
            system="ECC",
            host=s.sap_ecc_host,
            client=s.sap_ecc_client,
            user=s.sap_ecc_user,
            password_len=len(s.sap_ecc_password or ""),
        )

    def s4hana(self) -> SAPCredential:
        s = self.settings
        return SAPCredential(
            system="S4HANA",
            host=s.sap_s4_host,
            client=s.sap_s4_client,
            user=s.sap_s4_user,
            password_len=len(s.sap_s4_password or ""),
        )

    def get_secret(self, system: str) -> str:
        s = self.settings
        return s.sap_s4_password if system.upper() == "S4HANA" else s.sap_ecc_password


_vault: CredentialVault | None = None


def get_credential_vault(settings: Settings | None = None) -> CredentialVault:
    global _vault
    if _vault is None:
        _vault = CredentialVault(settings or get_settings())
    return _vault