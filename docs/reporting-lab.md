# Reporting lab

Run the local ETL against its synthetic orders. Amounts are loaded as integer cents and aggregated by region. The report uses the most recent successful transaction.

```powershell
python -m agileops.lab run
python -m agileops.lab report
python -m agileops.lab run --scenario missing_column --incident-id "INC 26-0001"
python -m agileops.lab logs --incident-id "INC 26-0001"
```

The lab uses `tmp/reporting-lab.db` by default. Pass `--database` before the command to use a separate workspace. Pass `--source` to the run command to supply a CSV. The failure switches are `schema_mismatch`, `bad_sql`, `invalid_config`, `missing_column`, and `duplicate_data`. A failed run returns exit code 1 and stores diagnostics with an incident ID, correlation ID, event code, severity and UTC timestamp.

The synthetic runbooks, troubleshooting SOP and prior dashboard incident are in [the reporting knowledge base](../src/agileops/runbooks).
