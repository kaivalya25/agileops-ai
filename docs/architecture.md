# Architecture

```mermaid
flowchart LR
    User --> API[FastAPI]
    API --> DB[(AgileOps SQLite)]
    API --> Workflow[LangGraph]
    API --> BI[Portfolio and restricted SQL]
    BI --> DB
    BI --> Dashboard[Dashboard]
    Workflow --> Audit[(Checkpoint and audit databases)]
    Workflow --> Lab[(Reporting lab and diagnostics)]
    Workflow --> RAG[Knowledge search]
    Workflow --> Worktree[Controlled Git worktree]
    RAG --> Index[(FAISS snapshot in SQLite)]
    RAG --> LLM[Local Ollama]
```

The ticket, incident and sprint APIs use repositories over the application database. Ticket transitions update the snapshot and append a UTC audit event in one transaction. Incident and sprint memberships use foreign keys. An unplanned open ticket appears in the backlog.

The reporting lab uses a separate database. It loads a fixture CSV into staging rows, aggregates totals and records diagnostic events. A failed refresh rolls back its data changes and keeps the prior report. The workflow uses the incident and correlation IDs to retrieve the relevant run.

## Retrieval

```mermaid
flowchart LR
    Markdown --> Metadata[Validate metadata and stable IDs]
    Metadata --> Chunks[Overlapping text chunks]
    Chunks --> Encoder[SentenceTransformer]
    Encoder --> FAISS[Normalized FAISS inner product index]
    Question --> Semantic[Semantic search]
    FAISS --> Semantic
    Question --> BM25
    Chunks --> BM25
    Semantic --> Fusion[Metadata-filtered reciprocal rank fusion]
    BM25 --> Fusion
    Fusion --> Rerank[Optional cross-encoder]
    Rerank --> Model[Typed citation selection]
    Model --> Evidence[Verbatim citation validation]
```

The index and chunk metadata are replaced in one SQLite transaction. A query can filter by system, incident type, document type, severity, date range and environment. Keyword, semantic and hybrid modes are available. The investigator can use the packaged runbooks with keyword search if a vector index has not been built.

## Workflow

```mermaid
flowchart TD
    Intake --> BA[Business Analyst]
    BA --> Investigator
    Investigator --> Scope[Human approves priority and scope]
    Investigator --> Abstain[Insufficient evidence]
    Scope --> PM[PM and Scrum planning]
    PM --> Plan[Engineer inspects source]
    Plan --> Remediation[Human approves remediation]
    Remediation --> Patch[Engineer patches isolated worktree]
    Patch --> QA[Independent QA]
    QA -->|Retry within budget| Patch
    QA -->|Pass| Release[Human approves lab release]
    Release --> BI[Verified BI report]
```

Checkpoints are keyed by workflow ID in a dedicated SQLite file. An approval must match the pending gate. Dependencies can hold scheduling in the backlog. The automated patch covers the simulated missing-column case. Other supported diagnoses produce evidence and recommendations for manual review.

## Storage

| Database | Tables and views |
| --- | --- |
| Application | `tickets`, `incidents`, `sprints`, `ticket_events`, `ticket_block_events`, analytical views |
| Reporting lab | `reporting_orders`, `reporting_summary`, `reporting_diagnostics` |
| Knowledge | One versioned snapshot of FAISS bytes, embedding model name and source chunks |
| Workflow | LangGraph checkpoints, immutable workflow audit, coordination database |

The API, approval, and storage details are in the [API guide](api.md) and [security notes](security.md).
