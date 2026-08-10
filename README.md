# CVI_ERROR_R_AUTO

**SAP BTP AI Agent — Customer Vendor Integration (CVI) &amp; Master Data Synchronization (MDS) SAP Note Automation**

A production-ready, single-page SAP BTP AI Agent that validates, analyses
and orchestrates SAP Note implementations for CVI (ECC `CVI_COCKPIT`)
and MDS (S/4HANA `MDS_LOAD_COCKPIT`) scenarios. Runs the SNOTE
workflow, handles transports, executes post-implementation cockpit
checks and enforces RBAC + approval + audit — all with a Fiori-style
dashboard whose main action is:

> **"Analyze &amp; Implement SAP Notes"**

## ✨ Highlights

- **One-click orchestration** — validate + AI analyse + SNOTE implement
  + auto-create transports + post-implementation cockpit checks.
- **AI Analysis** — Anthropic Claude on **SAP AI Core (Generative AI Hub)**
  with automatic fallback to direct Anthropic API or offline **MockLLM**.
- **System-aware routing** — ECC ➜ `CVI_COCKPIT`, S/4HANA ➜ `MDS_LOAD_COCKPIT`.
- **RBAC + SoD** — capability-based access control, requester ≠ approver.
- **Approval workflow** — PROD changes gated behind a decision step.
- **Audit trail** — append-only JSONL log of every action.
- **Safe by default** — all SAP backend interactions are mocked;
  feature flags enable real RFC / SNOTE / transport calls when ready.
- **BTP-ready** — `manifest.yml`, `Procfile`, `runtime.txt`, `.cfignore`.

## 🏗️ Stack

- **Backend:** Python 3.11 + FastAPI + Uvicorn
- **Frontend:** SAP Fiori-style single-page HTML + vanilla JS + CSS
- **LLM (primary):** Anthropic Claude on **SAP AI Core** via OAuth2
- **LLM (secondary):** Direct Anthropic API
- **LLM (fallback):** Offline **MockLLM**
- **Connectors:** RFC / OData / SAP GUI Scripting / Cloud Connector — abstracted
- **Storage:** File-based job + audit stores (upgradeable to HANA Cloud)

## 🚀 Quick start

```bash
cd CVI_ERROR_R_AUTO
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill AICORE_* to enable Claude on AI Core
python run.py             # http://localhost:8030
```

Open http://localhost:8030 and click **"Analyze &amp; Implement SAP Notes"**.
With no AI Core credentials the agent uses **MockLLM** — everything still
works end-to-end.

### 🔐 Using SAP AI Core credentials

The repo ships two env files:

- **`.env.example`** — public template with empty values (committed).
- **`.env`** — real credentials for local dev (git-ignored, **never commit**).

To enable Claude on **SAP AI Core**, populate `.env` with the six
`AICORE_*` variables (they map 1:1 to the AI Core service key) plus:

```bash
LLM_PROVIDER=aicore-anthropic
STUDIO_LLM_ENABLED=true
AICORE_RESOURCE_GROUP=<your-resource-group>
AICORE_DEPLOYMENT_ID=<claude-deployment-id>
AICORE_ANTHROPIC_VERSION=bedrock-2023-05-31
```

Verify with a quick smoke test after starting `python run.py`:

```bash
curl -s http://localhost:8030/health | jq \
  '{provider: .llm_provider_active, streaming: .supports_streaming, probe_ms: .llm_probe_latency_ms}'

curl -s -X POST http://localhost:8030/prompt \
  -H "content-type: application/json" \
  -d '{"prompt":"In one sentence, what is CVI in SAP?","requested_by":"smoke"}' \
  | jq '{provider, model, latency_ms}'
```

`provider` should read `aicore-anthropic` (not `mock`) and `latency_ms`
should be > 0. If it says `mock`, check `/health.fallback_reason` and
`/health.llm_init_error` for the root cause.

## 📁 Layout

```
CVI_ERROR_R_AUTO/
├── app/
│   ├── main.py                        # FastAPI wiring + static UI
│   ├── config.py                      # pydantic-settings
│   ├── llm/                           # AI Core / Anthropic / Mock + factory
│   ├── models/                        # Pydantic domain models
│   ├── storage/                       # Job + audit stores
│   ├── connectors/                    # RFC / OData / SAP GUI / Cloud Connector
│   ├── security/                      # RBAC / approvals / credentials
│   ├── agents/                        # Validator, Analyzer, SNOTE, Cockpits, Orchestrator
│   ├── exporters/                     # Markdown / JSON / DOCX report exporter
│   └── api/                           # REST routes
├── ui/webapp/                         # index.html + app.js + css/style.css
├── samples/                           # ABAP · RAP · OData · UI5 fragments
├── docs/                              # Architecture, workflow, security, roadmap, tests, deploy
├── run.py                             # Uvicorn entrypoint (port 8030)
├── manifest.yml Procfile runtime.txt  # BTP Cloud Foundry deploy
├── requirements.txt .env.example .gitignore .cfignore
└── README.md
```

## 🔌 REST API

| Method | Endpoint | Purpose |
|---|---|---|
| GET  | `/health` | LLM + credentials + Cloud Connector diagnostics |
| POST | `/notes/upload` (multipart) | Upload SAP Note files, extract note numbers |
| POST | `/notes/validate` | Run pre-implementation validation only |
| POST | `/notes/analyze` | Run LLM-based analysis only |
| POST | `/notes/implement` | Full orchestration (blocking) |
| POST | `/notes/implement/stream` | Full orchestration (SSE) |
| GET  | `/notes/{id}/report?fmt=md\|json\|docx` | Download report |
| POST | `/prompt` | Free-form AI prompt |
| GET  | `/executions` | Execution history |
| GET  | `/executions/{id}` | Full execution record |
| GET  | `/executions/{id}/logs` | Log tail |
| GET  | `/errors` | Error dashboard |
| GET  | `/transports` | Transport list |
| GET  | `/approvals` | Pending / all approvals |
| POST | `/approvals/{id}/decide` | Grant / reject + optional resume |
| GET  | `/audit` | Audit log tail |

## 🧠 LLM configuration

```env
LLM_PROVIDER=aicore-anthropic        # primary
STUDIO_LLM_ENABLED=true              # false → MockLLM

AICORE_CLIENT_ID=
AICORE_CLIENT_SECRET=
AICORE_AUTH_URL=
AICORE_BASE_URL=
AICORE_RESOURCE_GROUP=default
AICORE_DEPLOYMENT_ID=
AICORE_ANTHROPIC_VERSION=bedrock-2023-05-31

LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4000
LLM_TIMEOUT_SECONDS=180
```

Fallback chain: **AI Core Anthropic → Direct Anthropic → MockLLM**.

## 🔐 Security

- **RBAC** — capability matrix defined in `app/security/rbac.py`.
- **SoD** — requester ≠ approver enforced in `/approvals/{id}/decide`.
- **Approval workflow** — PROD runs pause with `AWAITING_APPROVAL`.
- **Audit log** — append-only JSONL under `data/audit/audit.log`.
- **Credential masking** — `/health` returns masked previews only.

See `docs/SECURITY.md` for the full architecture.

## 🛡️ Safety Policy

- No live SAP calls unless the relevant `ENABLE_REAL_*` feature flag is `true`.
- No SAP note is claimed as "implemented" unless real logs are captured.
- All simulated responses are clearly labelled `(mock)` in the report.

## 📖 Documentation

- `docs/ARCHITECTURE.md` — Solution + BTP component architecture
- `docs/WORKFLOW.md`     — End-to-end orchestrator flow + error matrix
- `docs/SECURITY.md`     — RBAC, SoD, approval, audit, BTP hardening
- `docs/ROADMAP.md`      — Phased implementation roadmap
- `docs/TEST_STRATEGY.md`— Layers, sample cases, LLM regression
- `docs/DEPLOYMENT_CHECKLIST.md` — Pre/post-deploy + rollback

## 🧪 Sample artifacts

- `samples/abap/zcl_cvi_note_handler.abap` — ABAP handler class
- `samples/rap/z_i_cvi_execution.cds` — RAP CDS root view (template)
- `samples/odata/z_api_cvi_execution_v1.edmx` — OData V4 service metadata
- `samples/ui5/Dashboard.controller.js` — SAPUI5 controller fragment

## 📜 License

Internal use.