---
{"id":"RB-DUPLICATE-ORDERS","title":"Duplicate order IDs in the reporting feed","system":"reporting","incident_type":"duplicate_data","document_type":"runbook","severity":"medium","date":"2026-10-05","environment":"lab"}
---

# Duplicate order IDs

`DUPLICATE_ORDER_ID` is raised by the `reporting_orders.order_id` primary key. Replayed batches and duplicate source records can trigger it. Compare duplicate rows and their batch provenance before deciding whether to retry. Do not silently discard rows with different amounts or regions.

Quarantine the invalid export. Ask the source owner to correct or reconcile the duplicate keys and refresh with the corrected batch. Validate that the source count and per-region totals match the loaded report.
