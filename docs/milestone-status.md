# Milestone verification

| Days | Delivered | Verification |
| --- | --- | --- |
| 1–10 | Domain model, API, SQLite persistence, event history, incident links, sprints and isolated repository fixtures | Unit and integration regression suite |
| 11–14 | Reporting lab, five failure switches, scoped diagnostics, runbooks, SOP and historical incident | All failure cases preserve the prior report |
| 15–22 | Ingestion, embeddings, persisted FAISS, metadata filters, BM25 fusion, reranking and retrieval evaluation | Built the real index and measured six labeled questions |
| 23–29 | Typed Ollama calls, investigator tools, evidence checks, abstention and known-cause evaluation | Live Ollama smoke test and 60 synthetic cases |
| 30–35 | Business analysis, RAG standards, typed handoffs, LangGraph and operator approvals | Checkpoint and approval integration tests |
| 36–45 | Controlled code search, worktree patch, regression test, independent QA, static review, permission limits and injection tests | Verified diff, QA output, dependency audit and adversarial regression tests |
| 46–54 | Sprint coordination, dependencies, analytical views, lifecycle metrics, restricted SQL and dashboard | Repository and workflow tests, query guards and a rendered dashboard |
| 55–59 | Full lab workflow, restart recovery, immutable audit and timing records | Completed a reporting incident and resumed pending approvals from SQLite |
| 60–66 | Labeled dataset and four-mode reliability benchmark | [Measured benchmark](evaluation.md) and case-level output |
| 67–69 | Dockerfile, Compose stack and GitHub Actions pipeline | Compose configuration passed validation. Container startup is checked by the Linux CI job. |
| 70–77 | Lint cleanup, environment-based settings, API, architecture, agent, security and evaluation documentation, and portfolio README | Lint, dependency checks, OpenAPI and documentation review |
| 78–82 | Reproducible demo, screenshots, resume bullets and interview notes | [Demo](demo.md) and [portfolio notes](interview.md) |
| 83 | Final regression suite | 43 tests passed, including FastAPI, SQLite, FAISS, LangGraph and security regressions |
| 84 | Release candidate | Version `1.0.0rc1` and a portfolio review of instructions, links and assets |
| 85 | Final portfolio release | Main-branch review and approval |
