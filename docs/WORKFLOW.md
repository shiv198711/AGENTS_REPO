# End-to-End Workflow

```
User clicks "Analyze & Implement SAP Notes"
        │
        ▼
+-----------------------+
| POST /notes/implement  |
|  or /implement/stream  |
+-----------+-----------+
            │
            ▼
   Orchestrator.run(ImplementationRequest)
            │
            ▼
   RBAC check ── denied ─► FAILED (audit RBAC_DENIED)
            │
            ▼
   VALIDATING
   • Note existence
   • Release/component applicability
   • Already implemented / obsolete
   • Prerequisites & conflicts
   • Transport availability
   • Auth check
            │
            ▼
   ANALYZING (LLM)
   • Executive summary
   • Business + Technical impact
   • Implementation sequence
   • Predicted conflicts
            │
            ▼
   PROD tier?
      │
      ├── yes ─► AWAITING_APPROVAL (approval workflow)
      │                    │
      │                    ▼
      │              Approver decides
      │                    │
      │                    ▼
      │              resume_after_approval()
      │
      ▼
   IMPLEMENTING
   • SNOTE download
   • Prerequisites first
   • Target notes
   • Capture logs
   • Auto-create transports
            │
            ▼
   (Optional) Transport release
   • RBAC check (transport.release.<tier>)
   • SoD check (requester != approver)
            │
            ▼
   POST_CHECK
   • CVI_COCKPIT (ECC) or MDS_LOAD_COCKPIT (S/4HANA)
            │
            ▼
   COMPLETED / FAILED / ROLLED_BACK
   • Audit trail flushed
   • Execution record persisted
   • Rollback recommendation on failure
```

## Error Handling & Rollback

| Error type | Handling |
|---|---|
| Invalid SAP Note | Skip note, record error, continue with others |
| Missing dependency | Halt implementation, recommend prereq installation |
| Authorization failure | RBAC audit entry, return `FAILED` |
| RFC failure | Wrap into `error_summary`, rollback recommendation |
| SAP GUI failure | Fall back to RFC-only mode where possible |
| Transport creation fail | Retry, then abort with rollback plan |
| Lock entries | Recommend SM12 cleanup, retry |
| Partial implementation | Persist state; recommend STMS rollback |
| Network interruption | Idempotent retry (validation stage) |