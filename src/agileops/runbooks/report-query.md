---
{"id":"RB-REPORT-SQL","title":"Repair a reporting SQL syntax error","system":"reporting","incident_type":"bad_sql","document_type":"runbook","severity":"high","date":"2026-10-02","environment":"lab"}
---

# Repair a reporting SQL syntax error

`SQL_SYNTAX_ERROR` after extraction indicates the reporting query failed to parse. Read the error detail and compare the query with the last successful version. A trailing WHERE after GROUP BY is invalid. The reporting query aggregates integer `amount_cents` by region.

Use the exact SQLite dialect in a disposable database. Fix the clause ordering, run the query on the lab fixture, and verify the aggregate totals before proposing the patch. The failed transaction should leave the prior report intact.
