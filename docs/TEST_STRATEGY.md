# Test Strategy

## Layers

| Layer | Approach | Tools |
|---|---|---|
| Unit | Pydantic model validation, RBAC matrix, note parsing | `pytest`, `pytest-cov` |
| Integration | REST endpoints against MockLLM + simulated RFC | `httpx`, FastAPI TestClient |
| Contract | OData EDMX schema compatibility for `samples/odata/*.edmx` | `xmllint`, custom checks |
| E2E (simulation) | Full orchestrator run in mock mode | Playwright / Postman |
| E2E (real) | On isolated DEV system with `ENABLE_REAL_RFC=true` | Manual + scripted smoke tests |
| Security | RBAC deny paths, SoD violation, approval bypass attempts | Targeted `pytest` cases |
| Performance | Concurrent orchestrator invocations | `locust` or `wrk` |
| Regression | Snapshot the mock report `.md` output | golden files |

## Sample Test Cases

1. `POST /notes/validate` with an obsolete note ⇒ `valid=false`, error contains "obsolete".
2. `POST /notes/implement` with tier=PROD, unknown approver ⇒ status `AWAITING_APPROVAL`.
3. Approve using the same user as requester ⇒ HTTP 403 (SoD).
4. RBAC user `demo.viewer` calling `/notes/implement` ⇒ FAILED with RBAC_DENIED audit.
5. Full orchestration for ECC ⇒ cockpit `CVI_COCKPIT`, S4HANA ⇒ `MDS_LOAD_COCKPIT`.
6. Audit log tail contains `IMPLEMENTATION_COMPLETE` after happy path.

## Non-Regression on LLM

- All prompts must include the CVI/MDS system prompt.
- Fallback to MockLLM must produce valid Markdown sections.
- No prompt/response is written verbatim to audit; only counts.