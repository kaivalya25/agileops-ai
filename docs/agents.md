# Agent responsibilities

| Agent | Input | Tools and permissions | Output |
| --- | --- | --- | --- |
| Business Analyst | Reported incident | Read incident and business standards | Problem, requirements and acceptance criteria |
| Investigator | Incident and correlation ID | Read current logs, runbooks and incident history | Facts, hypothesis, recommended checks and evidence IDs |
| Project Manager | Approved ticket and dependency IDs | Inspect ticket state and sprint dates | Delivery risk, dependencies and escalation |
| Scrum Master | Approved delivery plan | Assign the ticket to the selected sprint | Sprint membership and planning summaries |
| Engineer | Typed BA and investigation handoff | Inspect the reporting query and apply the approved change in the lab worktree | Plan, diff and reconciliation test result |
| Security | Controlled worktree | Inspect the exact file scope and syntax before QA | Approved file set and static validation |
| QA | Controlled worktree and acceptance criteria | Verify exact source scope and run the reconciliation test | Independent pass or failure with test output |
| BI | Persisted ticket, sprint and event data | Read the portfolio or compile a restricted query plan | Verified metrics or a narrative grounded in returned rows |

The investigator uses structured diagnostic rules for the five known lab failures. Optional Ollama output must identify the code and log ID supported by current evidence. Ambiguous and conflicting evidence produce an abstention. The engineer supports the missing-column remediation and routes other cases to manual review.

The PM and Scrum stages coordinate dependencies and sprint selection. The sprint review endpoint reports completed work, remaining work, blockers, and retrospective metrics. When a required dependency remains open, the workflow retains its ticket and records the unresolved IDs.
