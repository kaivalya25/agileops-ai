# AgileOps AI

AgileOps AI is a local incident response lab. Its interactive demo takes a stale sales dashboard from incident intake through diagnosis, a controlled SQL repair, independent QA, operator approval, and reporting recovery.

## Major milestones

- **Incident and delivery management.** FastAPI endpoints manage incidents, linked tickets, sprints, and the backlog. SQLite stores workflow data and an append-only ticket history.
- **Reporting lab and browser intake.** Submit an incident from the browser and reproduce one of five ETL failures. The lab links diagnostic logs to the incident and preserves the last successful report if a refresh fails.
- **Evidence-backed investigation.** The investigator checks incident logs against reporting runbooks and prior cases. Optional local AI uses Ollama, FAISS, BM25 search, metadata filters, and reranking.
- **Approval-gated repair and recovery.** LangGraph saves progress between approvals. The missing-column demo patches an isolated Git worktree, runs independent QA, and executes the approved query before closing the ticket.
- **Delivery reporting.** The dashboard shows sprint progress, ticket aging, throughput, and cycle time. The analytics API supports restricted, read-only queries.
- **Verification.** The regression suite covers intake, persistence, approval recovery, reporting recovery, and security controls. The investigator classified or abstained correctly on all 60 synthetic cases in the benchmark.

## Try the demo

Install Python and Git, then run these commands from the repository root.

```sh
python -m pip install -e ".[lab]"
python -m agileops.local_lab --open-browser
```

The launcher opens the incident form at [localhost:8000](http://127.0.0.1:8000/). Submit the sample or enter your own incident details. Choose **Missing report column** to exercise all three approvals. The last approval runs the repaired SQL and shows the restored totals.

![Completed incident review with the diagnosis, approvals, QA result, and recovered report](docs/demo/incident-review.png)

See the [demo walkthrough](docs/demo.md) for browser, API, and scripted options.

## Local model and knowledge search

The browser lab uses built-in diagnostics by default. To enable Ollama, install the AI extra, start Ollama, and build the knowledge index.

```sh
python -m pip install -e ".[ai]"
ollama pull qwen2.5:0.5b
python -m agileops.knowledge build
```

Set `AGILEOPS_OLLAMA_MODEL=qwen2.5:0.5b` and `AGILEOPS_KNOWLEDGE_DB=tmp/knowledge.db` before launching the lab. Select the Ollama option on the incident form. For the container setup, configure the operator token from `.env.example` and run `docker compose up --build`.

[Architecture](docs/architecture.md) · [API guide](docs/api.md) · [Agents](docs/agents.md) · [Security](docs/security.md) · [Evaluation results](docs/evaluation.md)
