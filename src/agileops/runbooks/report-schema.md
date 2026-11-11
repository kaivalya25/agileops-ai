---
{"id":"RB-REPORT-SCHEMA","title":"Reporting source schema mismatch","system":"reporting","incident_type":"schema_mismatch","document_type":"runbook","severity":"high","date":"2026-10-01","environment":"lab"}
---

# Reporting source schema mismatch

The refresh connector expects the CSV header `order_id,region,amount`. A feed that renames `amount` to `total` is rejected before loading and emits `SOURCE_SCHEMA_MISMATCH`. The last successful dashboard snapshot remains visible.

Compare the feed header with the approved source contract and check recent export deployments. Preserve the original file and correlation ID. Confirm that the fields still carry the intended currency and region semantics before changing the contract.

Restore the compatible export or coordinate a versioned schema change with the source owner. Validate the corrected file in the lab, rerun the refresh, and reconcile row counts and regional totals against the source before closing the incident.
