# CVI_ERROR_R_AUTO — Solution Architecture

## 1. Executive Summary

CVI_ERROR_R_AUTO is a production-ready SAP BTP AI Agent that automates
the validation, analysis and orchestrated implementation of SAP Notes
for **Customer Vendor Integration (CVI)** in SAP ECC and **Master Data
Synchronization (MDS)** in SAP S/4HANA. It exposes a single-page Fiori
dashboard whose primary action — **"Analyze &amp; Implement SAP Notes"** —
runs the full agent workflow: pre-validation, LLM-driven impact
analysis, SNOTE orchestration, transport handling, post-implementation
cockpit checks (CVI_COCKPIT for ECC, MDS_LOAD_COCKPIT for S/4HANA),
audit logging and rollback recommendations.

## 2. High-Level Component Diagram

```
                +--------------------- SAP BTP ---------------------+
                |                                                    |
User -> Fiori   |  +----------------+     +-----------------------+  |
Browser <---->  |  | Dashboard SPA  |<--->| CVI/MDS AI Agent      |  |
                |  | (index.html)   |     | (FastAPI, Python)     |  |
                |  +----------------+     |                       |  |
                |                         |  Orchestrator         |  |
                |                         |  Note Validator       |  |
                |                         |  Note Analyzer  (LLM) |  |
                |                         |  SNOTE Executor       |  |
                |                         |  CVI/MDS Cockpit      |  |
                |                         |  Transport Manager    |  |
                |                         |  RBAC / Approvals     |  |
                |                         |  Audit Log            |  |
                |                         +-----------+-----------+  |
                |                                     |              |
                |         +----------------+          |              |
                |         | SAP AI Core    |<---------+ LLM (Claude) |
                |         | GenAI Hub      |          |              |
                |         +----------------+          |              |
                +---------------------------|---------|--------------+
                                            |         |
              +-----------------------------+---------+-------------------+
              |                    SAP Cloud Connector                    |
              +-----------------+-----------+--------+---------+----------+
                                |                    |         |
                         +------v------+     +-------v----+ +--v------------+
                         | SAP ECC     |     | SAP S/4HANA| | SAP GUI       |
                         | (RFC)       |     | (OData/RFC)| | Scripting     |
                         | CVI_COCKPIT |     | MDS_LOAD_  | | (fallback)    |
                         | SNOTE       |     |  COCKPIT   | |               |
                         +-------------+     +------------+ +---------------+
```

## 3. Runtime Components

| Component | Purpose |
|---|---|
| Dashboard SPA | Fiori-style single-page UI (`ui/webapp`) |
| FastAPI backend | Central agent runtime + REST + SSE |
| Orchestrator | End-to-end workflow controller |
| Note Validator | Existence / applicability / prereq / conflict checks |
| Note Analyzer | LLM-based impact & sequencing analysis |
| SNOTE Executor | Note download + implement via RFC/GUI |
| CVI / MDS Cockpit Agents | Post-implementation validation |
| Transport Manager | Auto-created transports, release with SoD |
| RBAC | Capability-based access control |
| Approval Workflow | Production change gate |
| Audit Store | Append-only JSONL audit trail |
| Job Store | Durable execution record store |
| Connectors | RFC / OData / SAP GUI Scripting / Cloud Connector |
| LLM Providers | AI Core Anthropic → Direct Anthropic → Mock |

## 4. Deployment (SAP BTP CF)

- Buildpack: `python_buildpack`
- Runtime: Python 3.11
- Manifest: `manifest.yml` binds `xsuaa`, `destination`, `connectivity`
- Approuter: fronts the app; XSUAA JWT propagated to backend
- Destinations: point to ECC / S/4HANA systems via Cloud Connector

## 5. Data Flow (Happy Path)

1. User selects System + Notes and clicks **Analyze &amp; Implement**.
2. UI POST `/notes/implement/stream` → backend orchestrator.
3. Orchestrator runs RBAC → Validator → Analyzer (LLM).
4. If PROD, an approval request is created and the run pauses.
5. On DEV/QA (or after approval) → SNOTE download + implement per note.
6. Transports auto-created and captured on the execution record.
7. Post-implementation cockpit executed (CVI_COCKPIT / MDS_LOAD_COCKPIT).
8. Execution record persisted; audit entries emitted.
9. UI streams progress via SSE and shows summary + download links.

## 6. Non-Functional Attributes

- **Auditability** — every state change written to `data/audit/audit.log`.
- **Safety** — no live SAP calls unless explicit feature flags on.
- **Extensibility** — LLM and connectors are protocol-driven.
- **Observability** — `/health` exposes provider status, credentials
  (masked), Cloud Connector info and feature flags.