# Security Architecture

## Principles
- **Least privilege** — capability-based RBAC gates every sensitive action.
- **Segregation of duties** — requester ≠ approver, enforced in the API.
- **Immutable audit** — every action recorded in `data/audit/audit.log`.
- **Secure credential storage** — passwords never logged, only masked.
- **TLS everywhere** — BTP-provided HTTPS ingress; RFC over SNC where used.
- **Change tracking** — every execution record persisted; transports linked.

## Capability Matrix (excerpt)

| Capability | Roles |
|---|---|
| `note.upload` / `note.validate` / `note.analyze` | Developer, Operator, Admin |
| `note.implement.dev` | Developer, Operator, Admin |
| `note.implement.qa` | Operator, Admin |
| `note.implement.prod` | Operator, Admin (+ approval) |
| `transport.release.dev` | Developer, Operator, Admin |
| `transport.release.qa` | Operator, Admin |
| `transport.release.prod` | Operator, Admin (+ approval) |
| `approval.grant` | Approver, Admin |
| `audit.view` | Approver, Operator, Admin |

## Approval Workflow (PROD)
1. Orchestrator detects `system_tier == PROD` and pauses with
   `AWAITING_APPROVAL`.
2. Approval record is created; audit event `APPROVAL_REQUESTED`.
3. Approver calls `POST /approvals/{id}/decide`.
4. SoD check enforced: approver may not equal requester.
5. On grant → orchestrator `resume_after_approval()` completes the run.
6. Every decision is auditable.

## BTP-Native Enhancements (recommended for production)
- Replace in-memory RBAC with **XSUAA** JWT scopes + role-collections.
- Replace in-memory audit with **BTP Audit Log Service** (or ANS).
- Replace filesystem job store with **HANA Cloud** or **PostgreSQL**.
- Route SAP backends through **Cloud Connector** + destinations.
- Encrypt at rest with the BTP-provided storage (e.g., HANA encryption).