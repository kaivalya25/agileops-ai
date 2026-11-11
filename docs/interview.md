# Portfolio and interview notes

## Resume bullets

- Built an incident-to-delivery automation platform with a reporting ETL lab, SQLite audit events, and persistent LangGraph checkpoints for three operator approvals.
- Evaluated an evidence-grounded investigator on 60 labeled synthetic incidents across five failure classes, including ambiguity, conflicting signals and prompt injection, with 60 correct diagnosis or abstention outcomes in the controlled benchmark.
- Implemented local sentence-transformer embeddings, persisted FAISS retrieval, BM25 fusion and cross-encoder reranking, with measured retrieval metrics and a comparison against raw local model responses.

## Questions to prepare for

| Question | Discussion |
| --- | --- |
| Why append events and keep a ticket snapshot? | The snapshot supports simple operational queries. An atomic event records the transition history and supports metrics. SQLite triggers protect existing event rows. |
| Why use an evidence-bound investigator? | Retrieval gives the model reference material. Current incident logs determine whether a diagnosis is supportable. A known error code and a matching evidence ID are checked before using the conclusion. |
| What did reranking improve? | Compare measured Recall@3, Precision@3 and MRR. Inspect the specific missed or lower-ranked runbooks. A higher ranking score does not prove the LLM made a correct diagnosis. |
| How does a workflow recover after restart? | A workflow ID selects a SQLite checkpoint. An operator approves the pending gate, and the graph resumes. Git edits are confined to a workflow worktree and the approved patch can be reapplied. |
| How do tool permissions differ from prompt instructions? | The Python broker enforces the role-to-tool mapping and call limits. Model output uses typed schemas and cannot execute commands. Engineering subprocesses receive fixed commands and a reduced environment. |
| What failed in the synthetic benchmark? | Review wrong diagnoses, unsupported citations and abstentions in the evaluation report. The corpus is deliberately small and the rules cover known synthetic faults, so scores do not generalize to arbitrary production incidents. |
| What is required before production use? | Tie approvals to authenticated users and policy, use a real process sandbox and authorization model, and evaluate on independent incident data before expanding tool permissions. |
