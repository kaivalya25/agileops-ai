---
{"id":"HIST-REPORT-0001","title":"Historical incident — stale sales dashboard after column rename","system":"reporting","incident_type":"missing_column","document_type":"historical_incident","severity":"high","date":"2026-10-12","environment":"lab"}
---

# Historical incident

The regional sales dashboard showed yesterday's totals. The failed refresh recorded `REPORT_COLUMN_MISSING` with `no such column: gross_cents`. The application query had been updated ahead of the reporting database schema. Investigation confirmed that `reporting_orders` still exposed `amount_cents`. Restoring the compatible query and rerunning the fixture reconciled all three source orders and restored the dashboard.

The release checklist now verifies the reporting schema and refresh query together. This historical incident is a comparison case. Confirm the current logs before using the same remediation.
