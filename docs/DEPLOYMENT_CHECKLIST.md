# Production Deployment Checklist

## Pre-Deployment

- [ ] `.env` values populated for AI Core, SAP ECC, SAP S/4HANA
- [ ] `AICORE_*` credentials verified via `/health`
- [ ] `ENABLE_REAL_RFC` still `false` for first deployment
- [ ] `APPROVAL_REQUIRED_FOR_PROD=true`
- [ ] `RBAC_ENABLED=true`
- [ ] XSUAA + destinations configured on BTP subaccount
- [ ] Cloud Connector location ID reachable
- [ ] SAP destinations (`sap-ecc`, `sap-s4hana`) pass `ping`

## Build & Deploy (Cloud Foundry)

```bash
cf login -a https://api.cf.<region>.hana.ondemand.com
cf create-service xsuaa application cvi-xsuaa
cf create-service destination lite cvi-dest
cf create-service connectivity lite cvi-conn
cf create-service aicore standard cvi-aicore

cf push -f manifest.yml
```

## Post-Deployment Smoke Tests

- [ ] `curl https://<app>.cfapps.<region>.hana.ondemand.com/health`
  returns `llm_provider_active` != `mock`.
- [ ] Fiori dashboard loads at the root URL.
- [ ] Submit a validation-only request → returns validation result.
- [ ] Submit a DEV analyze+implement with mock notes → completes.
- [ ] Submit a PROD analyze+implement → status `AWAITING_APPROVAL`.
- [ ] Approver grants → orchestrator resumes and completes.
- [ ] Transports appear on the Transports tab.
- [ ] Audit log contains the full trail.

## Rollback

- Route traffic to previous version via `cf routes` mapping.
- Cancel outstanding approvals; mark `AWAITING_APPROVAL` runs failed.
- If real transports were released, coordinate STMS reversal.

## Operational Runbook

- Logs: `cf logs cvi-error-r-auto --recent`.
- Metrics: BTP Application Logging Service or Kyma Prometheus.
- Alerts: BTP Alert Notification service on `IMPLEMENTATION_FAIL`.
- On-call playbook: `docs/WORKFLOW.md` error-handling matrix.