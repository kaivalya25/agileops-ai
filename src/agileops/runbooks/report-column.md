---
{"id":"RB-REPORT-COLUMN","title":"Missing reporting database column after a schema change","system":"reporting","incident_type":"missing_column","document_type":"runbook","severity":"high","date":"2026-10-04","environment":"lab"}
---

# Missing reporting database column

`REPORT_COLUMN_MISSING` means a report query references a column absent from the loaded database schema. For a failure on `gross_cents`, compare the query with `PRAGMA table_info(reporting_orders)`. The current schema has `amount_cents`.

Check whether the corresponding migration was deployed and whether the query is running against the expected database. Restore the compatible query or deploy the approved migration, then compare the new report with a known-good snapshot. A successful SQL parse alone does not verify that the data agrees.
