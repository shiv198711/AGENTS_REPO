"""Simple role-based access control with segregation-of-duties checks.

Ships with an in-memory user directory for demo purposes.  A production
deployment should replace this with SAP BTP XSUAA / IAS integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    VIEWER = "VIEWER"
    DEVELOPER = "DEVELOPER"
    APPROVER = "APPROVER"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"


@dataclass
class User:
    name: str
    roles: set[Role] = field(default_factory=set)

    def has(self, role: Role) -> bool:
        return role in self.roles or Role.ADMIN in self.roles


# Capability matrix ---------------------------------------------------------
_CAPABILITY_MATRIX: dict[str, set[Role]] = {
    "note.view": {Role.VIEWER, Role.DEVELOPER, Role.OPERATOR, Role.APPROVER, Role.ADMIN},
    "note.upload": {Role.DEVELOPER, Role.OPERATOR, Role.ADMIN},
    "note.validate": {Role.DEVELOPER, Role.OPERATOR, Role.ADMIN},
    "note.analyze": {Role.DEVELOPER, Role.OPERATOR, Role.ADMIN},
    "note.implement.dev": {Role.DEVELOPER, Role.OPERATOR, Role.ADMIN},
    "note.implement.qa": {Role.OPERATOR, Role.ADMIN},
    "note.implement.prod": {Role.OPERATOR, Role.ADMIN},
    "transport.create": {Role.DEVELOPER, Role.OPERATOR, Role.ADMIN},
    "transport.release.dev": {Role.DEVELOPER, Role.OPERATOR, Role.ADMIN},
    "transport.release.qa": {Role.OPERATOR, Role.ADMIN},
    "transport.release.prod": {Role.OPERATOR, Role.ADMIN},
    "approval.grant": {Role.APPROVER, Role.ADMIN},
    "audit.view": {Role.APPROVER, Role.OPERATOR, Role.ADMIN},
    "prompt.submit": {Role.VIEWER, Role.DEVELOPER, Role.OPERATOR, Role.APPROVER, Role.ADMIN},
}


class RBAC:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.users: dict[str, User] = {
            "demo.viewer": User("demo.viewer", {Role.VIEWER}),
            "demo.developer": User("demo.developer", {Role.DEVELOPER}),
            "demo.operator": User("demo.operator", {Role.OPERATOR}),
            "demo.approver": User("demo.approver", {Role.APPROVER}),
            "demo.admin": User("demo.admin", {Role.ADMIN}),
            "anonymous": User("anonymous", {Role.VIEWER}),
        }

    # ------------------------------------------------------------------
    def get_user(self, name: str) -> User:
        return self.users.get(name) or User(name=name, roles={Role.VIEWER})

    def can(self, user_name: str, capability: str) -> bool:
        if not self.enabled:
            return True
        allowed = _CAPABILITY_MATRIX.get(capability)
        if not allowed:
            return False
        user = self.get_user(user_name)
        return bool(user.roles & allowed) or Role.ADMIN in user.roles

    def require(self, user_name: str, capability: str) -> None:
        if not self.can(user_name, capability):
            raise PermissionError(
                f"RBAC denied: user='{user_name}' capability='{capability}'"
            )

    def sod_check(self, requester: str, approver: str) -> bool:
        """Segregation of duties: requester must not equal approver."""
        return requester.strip().lower() != approver.strip().lower()


_rbac: RBAC | None = None


def get_rbac(enabled: bool | None = None) -> RBAC:
    global _rbac
    if _rbac is None:
        from ..config import get_settings

        settings = get_settings()
        _rbac = RBAC(enabled=settings.rbac_enabled if enabled is None else enabled)
    return _rbac