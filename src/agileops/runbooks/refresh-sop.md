---
{"id":"SOP-REPORT-REFRESH","title":"Reporting refresh investigation and validation SOP","system":"reporting","incident_type":"refresh","document_type":"sop","severity":"medium","date":"2026-10-13","environment":"lab"}
---

# Reporting refresh investigation and validation

Record the affected report, time, environment and business impact. Locate the refresh correlation ID using incident-scoped diagnostics. Compare the last successful run with the failed run and preserve the observed error code.

Validate the source header and primary keys, connector access, loaded SQLite schema and reporting query in that order. Confirm any hypothesis against current evidence. After an approved correction, run the report on a known fixture, reconcile the regional order counts and totals, and document the result.
