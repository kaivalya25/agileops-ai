---
{"id":"RB-SOURCE-AUTH","title":"Reporting connector authentication and configuration","system":"reporting","incident_type":"invalid_config","document_type":"runbook","severity":"high","date":"2026-10-03","environment":"lab"}
---

# Reporting connector authentication and configuration

`SOURCE_AUTH_FAILED` is a rejected connector credential or configuration. Confirm the deployment points to the correct environment and that the configured credential reference is current. Review the last secret rotation or configuration change with the owner. Preserve the correlation ID and error code in the incident.

Obtain approval for a credential update, restore the correct reference, and verify a refresh with the expected service identity. Record the reference or rotation timestamp only. Never paste the credential itself into logs or incident notes.
