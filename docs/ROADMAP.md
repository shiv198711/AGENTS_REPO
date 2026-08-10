# Implementation Roadmap

| Phase | Duration | Deliverables |
|---|---|---|
| **Phase 0 — Scaffold** (this repo) | 1 sprint | FastAPI backend, Fiori SPA, mocked connectors, LLM providers, safe defaults |
| **Phase 1 — Real integration** | 2–3 sprints | Wire `pyrfc` behind `RFCConnector`, enable real SNOTE calls on DEV, real transport creation |
| **Phase 2 — BTP hardening** | 2 sprints | XSUAA / role-collections, destinations, Cloud Connector, HANA Cloud persistence, BTP Audit Log Service |
| **Phase 3 — S/4HANA specifics** | 2 sprints | Full MDS_LOAD_COCKPIT integration (initial load, replication, error reconciliation) |
| **Phase 4 — Production rollout** | 2 sprints | PROD approval workflow, SoD hardening, alerting via ANS, DR runbook |
| **Phase 5 — AI enhancements** | continuous | Retrieval over SAP Notes long-text, embeddings-based prereq graph, multi-step tool use |

## Backlog (indicative)

- Persistent execution store on HANA Cloud (drop file-based JSON).
- Approval workflow via SAP Build Process Automation.
- Support batch operations across multiple systems.
- Integration with SAP Solution Manager (ChaRM) for change control.
- Multi-tenant isolation on BTP with subaccount tenancy.
- Custom LLM guardrails (deny-list, PII filter).