"""Health + provider diagnostics endpoint."""
from __future__ import annotations

import time

from fastapi import APIRouter

from ..config import get_settings
from ..connectors.cloud_connector import build_cloud_connector
from ..llm.factory import build_llm, last_build_info
from ..security.credentials import get_credential_vault


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    llm = build_llm()
    info = last_build_info()
    vault = get_credential_vault(settings)
    cc = build_cloud_connector(settings)

    # Per-provider health probe when the client exposes health()/ping().
    llm_health: dict = {}
    probe_latency_ms = 0
    try:
        probe = getattr(llm, "health", None) or getattr(llm, "ping", None)
        if callable(probe):
            t0 = time.time()
            result = probe()
            probe_latency_ms = int((time.time() - t0) * 1000)
            if isinstance(result, dict):
                llm_health = result
    except Exception as exc:  # noqa: BLE001
        llm_health = {"probe_error": str(exc)}

    return {
        "app": "CVI_ERROR_R_AUTO",
        "version": "1.0.0",
        "status": "ok",
        "llm_provider_active": llm.provider_name,
        "attempted_provider": info.get("attempted_provider", ""),
        "supports_streaming": llm.supports_streaming,
        "fallback_reason": info.get("fallback_reason", ""),
        "llm_init_error": info.get("init_error", ""),
        "llm_health": llm_health,
        "llm_probe_latency_ms": probe_latency_ms,
        "aicore_ready": settings.aicore_ready(),
        "aicore_env_view": {
            "AICORE_CLIENT_ID": _mask(settings.aicore_client_id),
            "AICORE_AUTH_URL": settings.aicore_auth_url,
            "AICORE_BASE_URL": settings.aicore_base_url,
            "AICORE_RESOURCE_GROUP": settings.aicore_resource_group,
            "AICORE_DEPLOYMENT_ID": settings.aicore_deployment_id,
            "AICORE_ANTHROPIC_VERSION": settings.aicore_anthropic_version,
        },
        "anthropic_ready": settings.anthropic_ready(),
        "credentials": {
            "ecc": vault.ecc().masked(),
            "s4hana": vault.s4hana().masked(),
        },
        "cloud_connector": cc.health(),
        "feature_flags": {
            "enable_real_rfc": settings.enable_real_rfc,
            "enable_real_snote": settings.enable_real_snote,
            "enable_real_transport": settings.enable_real_transport,
            "enable_sap_gui_automation": settings.enable_sap_gui_automation,
            "approval_required_for_prod": settings.approval_required_for_prod,
            "audit_log_enabled": settings.audit_log_enabled,
            "rbac_enabled": settings.rbac_enabled,
        },
    }


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}…{value[-4:]}"