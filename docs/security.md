# Security model

AgileOps is a local lab. The Compose API binds to loopback, Ollama remains on the internal network, and the containers run the API as a non-root user. Configure the operator approval token using the environment. The approval API checks the token and pending gate before continuing. Actor names are operator-supplied labels in this demo.

| Control | Enforcement |
| --- | --- |
| Tool permissions | Explicit per-agent tool allowlists. Model output cannot call a tool directly. |
| Prompt injection | Treat incident, log, source and retrieved text as data. Constrain model output with typed schemas, validate diagnostic codes and citation IDs, and reject fabricated or suspicious excerpts. |
| Approval boundaries | Persistent gates for priority and scope, remediation, and lab release. Independent QA must pass before the final gate. |
| Controlled code | A dedicated synthetic Git repository, a workflow-scoped worktree, an exact edit to one known query, and independent checks before isolated Python execution. |
| Execution limits | Bounded graph steps, tool calls and engineering attempts, and subprocess and model request timeouts. |
| SQL guardrails | One approved analytical view per query, whitelisted projection and filter columns, parameterized values, row limits and query-only SQLite mode. |
| Audit | Append-only ticket and workflow history. Record approval, denied tool call, transition, tool result, model timing and available token counts. |

Keep model and knowledge caches in the workspace data directory. Build FAISS indexes from trusted local files and load snapshots from that workspace. Review application dependency reports and retest after dependency upgrades. The synthetic evaluation covers known attacks and controlled files. The lab does not have production deployment credentials or arbitrary code execution tools.
