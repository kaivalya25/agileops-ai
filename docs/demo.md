# Demo a dashboard incident

The demo seeds a sales reporting incident, runs a failing refresh, then uses its correlation ID for the investigation. It creates a linked ticket, assigns a sprint, proposes a patch in a controlled Git worktree, runs independent QA, and runs the approved query against the reporting lab before closing the ticket.

## Submit an incident in the browser

```powershell
python -m pip install -e ".[lab]"
python -m agileops.local_lab --open-browser
```

The launcher opens `http://127.0.0.1:8000/` with its local operator token ready for the tab. If you open the URL manually, paste the token from the file shown by the launcher. The default workspace is `tmp/local-lab`.

1. Replace the sample description, reporter, affected system, and impact with your own input or submit the sample. Keep **Missing report column** selected for the automated repair.
2. Click **Start investigation**. Review the evidence and click **Approve priority and scope**.
3. Review the patch plan and click **Approve remediation**. AgileOps writes the repair in a controlled worktree and runs its tests and independent QA.
4. Review QA and click **Approve release**. The lab executes the reviewed query, records the recovery correlation ID, and shows the restored regional totals. Open the delivery dashboard to see the completed ticket.

The other lab failures run through diagnosis and manual review. The default investigation uses the packaged runbooks and diagnostic rules. To use Ollama, configure the model as described in the [README](../README.md#local-model-and-knowledge-search) and select the Ollama option on the form.

For an API client, send the same input to `POST /lab/incidents` with the `X-AgileOps-Approval-Token` header. The response includes the incident, the simulated refresh failure, and the workflow. Use its `workflow_id` to send the three approvals documented in the [API guide](api.md).

## Scripted demo

```powershell
python -m pip install -e ".[dev,ai]"
python -m agileops.demo --workspace tmp/demo --approve-lab
```

The `--approve-lab` flag records approvals from a simulated operator for this fixture. To exercise real approval prompts, omit the flag and use the API. Each approval request carries the pending gate, an actor and a reason. The demo reports the database and workflow paths and returns the audit history and restored report as JSON.

Point the application at the same workspace.

```powershell
$env:AGILEOPS_DB_PATH = "tmp/demo/agileops.db"
$env:AGILEOPS_LAB_DB = "tmp/demo/reporting.db"
$env:AGILEOPS_WORKFLOW_DIR = "tmp/demo/workflows"
$env:AGILEOPS_APPROVAL_TOKEN = [guid]::NewGuid().ToString("N")
python -m uvicorn agileops.main:app
```

Open `/workflows/{workflow_id}/review` to inspect the incident intake, evidence, patch, QA result and approvals. Open `/dashboard` for the sprint, ticket aging and throughput view.

![Completed incident review with evidence, approvals, patch, and QA](demo/incident-review.png)

![Delivery dashboard after the completed incident](demo/delivery-dashboard.png)
