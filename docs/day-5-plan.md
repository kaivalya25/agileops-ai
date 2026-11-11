# Day 4 audit and Day 5 plan

The repository and branch history contained no Day 4 checklist. The milestones below come from the working tree and the project README.

| Day | State before implementation |
| --- | --- |
| 1 | Repository, project scope, planned agent roles, and human approval boundaries established. |
| 2 | Ticket and incident domain models, incident-to-ticket conversion, and the ticket status workflow implemented. |
| 3 | Pydantic request models and Python packaging in place. The four existing tests passed. |
| 4 | FastAPI dependencies and service/repository scaffolding were present. The ticket router was empty, there was no ASGI app, and the service could not import or call the repository. There were no API tests. |

The service imported an unrelated HTTP client and called repository methods that did not exist. The dictionary repository lost tickets on restart and exposed mutable ticket references. A process-local counter could restart or allocate the same public ID in different workers. Ticket state had no audit history. Domain and schema imports printed example data.

## Implementation sequence

1. Finish Day 4 by wiring FastAPI and the ticket service. Add health, create, list, and lookup endpoints, with validation and missing-ticket responses. Preserve the existing request fields, `TASK-001` ID format, and serialized ticket fields and enum names.
2. Define a ticket repository interface and inject it into the service. Implement it with file-backed SQLite through Python's standard library. Keep the public ticket number in the database and allocate it in the same transaction as creation.
3. Add ordered, versioned schema migrations for the ticket snapshot, number sequence, and event history. Apply pending migrations transactionally on application startup and record the applied version. Make the database file configurable.
4. Append a creation event and an event for each accepted status transition. Store the previous and new statuses and a UTC timestamp. Keep `Ticket.change_status()` as the workflow authority. Persist the snapshot and event together, and expose status changes and ordered history through ticket subroutes.
5. Verify the API contract, the existing workflow, persistence across app restarts, migration repeatability, rollback when event writes fail, and concurrent creation and transitions using temporary databases.
