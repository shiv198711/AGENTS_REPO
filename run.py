"""Entry point for CVI_ERROR_R_AUTO.

Starts the FastAPI application via Uvicorn. Host and port come from
environment variables (loaded by `app.config.Settings`) so the same
entry point works locally and on SAP BTP Cloud Foundry.
"""
from __future__ import annotations

import os

import uvicorn

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    port = int(os.environ.get("PORT", settings.port))
    host = os.environ.get("HOST", settings.host)
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()