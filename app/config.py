"""Configuration loader for CVI_ERROR_R_AUTO.

Uses pydantic-settings to read a `.env` file plus process environment.
Central place for LLM provider settings, SAP connectivity toggles, and
security flags.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(DOTENV_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime ---
    host: str = "0.0.0.0"
    port: int = 8030
    log_level: str = "INFO"

    # --- LLM ---
    llm_provider: str = "mock"  # aicore-anthropic | anthropic | mock
    studio_llm_enabled: bool = True
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4000
    llm_timeout_seconds: int = 180

    # --- AI Core ---
    aicore_client_id: str = ""
    aicore_client_secret: str = ""
    aicore_auth_url: str = ""
    aicore_base_url: str = ""
    aicore_resource_group: str = "default"
    aicore_deployment_id: str = ""
    aicore_anthropic_version: str = "bedrock-2023-05-31"

    # --- Anthropic direct ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"

    # --- SAP ECC ---
    sap_ecc_host: str = ""
    sap_ecc_sysnr: str = "00"
    sap_ecc_client: str = "100"
    sap_ecc_user: str = ""
    sap_ecc_password: str = ""

    # --- SAP S/4HANA ---
    sap_s4_host: str = ""
    sap_s4_sysnr: str = "00"
    sap_s4_client: str = "100"
    sap_s4_user: str = ""
    sap_s4_password: str = ""

    # --- Integration ---
    sap_odata_base_url: str = ""
    sap_cloud_connector_location_id: str = ""

    # --- Feature toggles ---
    enable_real_rfc: bool = False
    enable_real_snote: bool = False
    enable_real_transport: bool = False
    enable_sap_gui_automation: bool = False

    # --- Security ---
    approval_required_for_prod: bool = True
    audit_log_enabled: bool = True
    rbac_enabled: bool = True

    # --- Storage ---
    data_dir: str = "data"

    # --- Derived helpers ---
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def data_path(self) -> Path:
        p = PROJECT_ROOT / self.data_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def jobs_path(self) -> Path:
        p = self.data_path / "jobs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def audit_path(self) -> Path:
        p = self.data_path / "audit"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def uploads_path(self) -> Path:
        p = self.data_path / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def aicore_ready(self) -> bool:
        return all(
            [
                self.aicore_client_id,
                self.aicore_client_secret,
                self.aicore_auth_url,
                self.aicore_base_url,
                self.aicore_deployment_id,
            ]
        )

    def anthropic_ready(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()