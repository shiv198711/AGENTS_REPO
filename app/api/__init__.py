"""API routes package."""

from . import routes_health, routes_notes, routes_prompt, routes_dashboard, routes_transport, routes_approvals, routes_audit

__all__ = [
    "routes_health",
    "routes_notes",
    "routes_prompt",
    "routes_dashboard",
    "routes_transport",
    "routes_approvals",
    "routes_audit",
]