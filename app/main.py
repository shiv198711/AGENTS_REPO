"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api import (
    routes_approvals,
    routes_audit,
    routes_dashboard,
    routes_health,
    routes_notes,
    routes_prompt,
    routes_transport,
)
from .config import get_settings


settings = get_settings()

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


app = FastAPI(
    title="CVI_ERROR_R_AUTO",
    description=(
        "SAP BTP AI Agent for CVI (ECC CVI_COCKPIT) and MDS (S/4HANA "
        "MDS_LOAD_COCKPIT) SAP Note validation, analysis and automated "
        "implementation. Includes SNOTE orchestration, transport handling, "
        "RBAC, approvals and audit logging."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API routers ----------------------------------------------------------
app.include_router(routes_health.router)
app.include_router(routes_notes.router)
app.include_router(routes_prompt.router)
app.include_router(routes_dashboard.router)
app.include_router(routes_transport.router)
app.include_router(routes_approvals.router)
app.include_router(routes_audit.router)


# --- Static UI ------------------------------------------------------------
_UI_DIR = Path(__file__).resolve().parent.parent / "ui" / "webapp"
if _UI_DIR.exists():
    # Mount CSS/JS
    if (_UI_DIR / "css").exists():
        app.mount("/css", StaticFiles(directory=_UI_DIR / "css"), name="css")
    # Root path serves index.html
    @app.get("/", include_in_schema=False)
    def _root() -> FileResponse:
        return FileResponse(_UI_DIR / "index.html")

    @app.get("/app.js", include_in_schema=False)
    def _app_js() -> FileResponse:
        return FileResponse(_UI_DIR / "app.js", media_type="application/javascript")
else:
    @app.get("/", include_in_schema=False)
    def _root_no_ui() -> RedirectResponse:
        return RedirectResponse(url="/docs")