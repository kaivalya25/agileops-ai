# API guide

The running application publishes OpenAPI at `/openapi.json` and interactive requests at `/docs`. JSON request values use the enum forms documented there. Ticket responses use uppercase enum names.

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Application readiness |
| `POST /tickets`, `GET /tickets`, `GET /tickets/{id}` | Create, list and retrieve tickets |
| `PATCH /tickets/{id}/status`, `GET /tickets/{id}/events` | Transition and inspect append-only history |
| `PATCH /tickets/{id}/assignment` | Set or clear the assignee |
| `GET /tickets/backlog`, `GET/PATCH /tickets/{id}/sprint` | Inspect backlog or change sprint membership |
| `POST /incidents`, `GET /incidents`, `GET /incidents/{id}` | Create and inspect incidents |
| `GET/POST /incidents/{id}/tickets` | Create or list linked tickets |
| `GET /incidents/{id}/investigation` | Investigate the latest or specified correlation ID |
| `GET/POST /sprints`, `GET /sprints/{id}`, `GET /sprints/{id}/tickets` | Plan and inspect sprints |
| `GET /sprints/{id}/review` | Stand-up, blockers and retrospective facts |
| `POST /knowledge/ask` | Retrieve evidence and return validated excerpts |
| `POST /workflows`, `GET /workflows/{id}` | Start or inspect persistent automation |
| `POST /workflows/{id}/approve`, `POST /workflows/{id}/retry` | Approve a pending gate or resume a failed checkpoint |
| `GET /workflows/{id}/audit` | Inspect append-only workflow history |
| `PATCH /tickets/{id}/blocked` | Record a blocked or unblocked interval |
| `GET /tickets/{id}/metrics`, `GET /tickets/metrics/throughput` | Lifecycle and UTC date range metrics |
| `GET /bi/portfolio`, `POST /bi/query`, `POST /bi/ask` | Portfolio snapshot, typed SQL plan or natural language query |

Ticket transitions use requests such as the following.

```json
{"status":"investigating","actor":"On-call engineer","reason":"Confirmed the refresh failure."}
```

Set a sprint membership with `{"sprint_id":"SPRINT-001"}` or pass `null` to return an open ticket to the backlog. Set an assignment with `{"assigned_to":"Reporting operations"}`. Incident IDs have a space that must be encoded as `%20` in a URL.

Start a workflow using `{"incident_id":"INC 26-0001","priority":"high"}`. Send the configured `X-AgileOps-Approval-Token` header when approving or retrying. Submit the gate shown in `pending_approval`.

```json
{"gate":"remediation","approved":true,"actor":"Lab operator","reason":"Reviewed the SQL plan."}
```

See the [demo instructions](demo.md) for a reproducible incident and its review screens.
