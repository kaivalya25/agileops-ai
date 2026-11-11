# AgileOps AI roadmap

Day 10 persistence testing was implemented alongside Day 9 sprint planning. The full suite passed 26 tests, including isolated SQLite fixtures, repository integration, and transactional rollback. See [test fixtures](../tests/conftest.py) and [sprint planning tests](../tests/test_sprint_planning.py).

See [milestone verification](milestone-status.md) for implementation and test evidence.

| Day | Milestone | What should be completed |
| --- | --- | --- |
| 10 | Persistence testing | Database fixtures, isolated test database, repository integration tests, transactional test cleanup |
| 11 | Simulated IT environment | Create a small reporting/ETL application that AgileOps will investigate and maintain |
| 12 | Seed failure scenarios | Introduce controlled failures: schema mismatch, bad SQL, invalid credentials/config, missing column, duplicate data |
| 13 | Application logging | Structured application logs, correlation IDs, incident-specific logs, diagnostic records |
| 14 | Runbook knowledge base | Create realistic troubleshooting guides, SOPs, technical documentation, historical incidents |
| 15 | RAG ingestion pipeline | Load documents, clean text, chunk content, metadata tagging, document IDs |
| 16 | Embeddings | Generate local embeddings using sentence-transformers; understand vector representations |
| 17 | Vector store | Implement FAISS/Chroma retrieval and persist/search indexed runbooks and historical incidents |
| 18 | RAG baseline | Question → retrieve chunks → provide context → LLM response with sources |
| 19 | Metadata filtering | Retrieve by system, incident type, document type, severity, date, environment |
| 20 | Hybrid retrieval | Combine semantic retrieval with keyword/BM25-style search |
| 21 | Reranking | Add reranking to improve which retrieved documents reach the LLM |
| 22 | RAG evaluation | Build ground-truth questions; measure Recall@K, Precision@K, MRR and retrieval failure cases |
| 23 | Local LLM integration | Configure Ollama/open-weight model and structured model invocation |
| 24 | Structured AI outputs | Require typed/Pydantic outputs rather than free-form agent responses |
| 25 | Incident Investigator v1 | Agent retrieves logs/runbooks/history and produces evidence-backed root-cause hypotheses |
| 26 | Investigator tools | Implement search_runbooks, query_logs, get_incident, search_history, diagnostic tools |
| 27 | Evidence grounding | Each conclusion must reference evidence; separate fact, hypothesis, recommendation |
| 28 | Hallucination control | Add “insufficient evidence” behavior, citation checks, unsupported-claim rejection |
| 29 | Investigator evaluation | Benchmark known incident scenarios: root-cause accuracy, evidence correctness, abstention accuracy |
| 30 | Business Analyst Agent | Convert business reports/incidents into requirements, technical tasks, acceptance criteria |
| 31 | BA RAG | Retrieve business rules, project standards, historical requirements and templates |
| 32 | Agent handoff schema | Define typed BA → Investigator → Engineering handoff objects |
| 33 | LangGraph foundation | Introduce workflow state, nodes, edges, conditional routing, checkpoints |
| 34 | BA + Investigator workflow | Complete first real multi-agent workflow with persistent state |
| 35 | Human approval workflow | Add approval checkpoints for priority, scope, remediation, and sensitive actions |
| 36 | Software Engineer Agent v1 | Agent reads ticket, inspects controlled repository, proposes implementation plan |
| 37 | Code search tools | Repository-aware retrieval: file search, symbol search, code-context retrieval |
| 38 | Controlled code editing | Engineer creates patch in isolated branch/worktree instead of modifying production code directly |
| 39 | Automated test execution | Engineer writes and runs unit tests; results become part of agent evidence |
| 40 | QA Agent | Independent validation against acceptance criteria, tests and expected behavior |
| 41 | Engineer ↔ QA loop | Failed QA sends ticket back to engineering; passed QA proceeds to human approval |
| 42 | Security Agent controls | Static checks, dependency checks, prompt-injection defenses, dangerous-action detection |
| 43 | Tool permissions | Implement explicit tool allowlists per agent and least-privilege capabilities |
| 44 | Rogue-agent protection | Recursion limits, call limits, timeouts, restricted commands, approval gates, immutable action logging |
| 45 | Prompt-injection testing | Seed malicious instructions into tickets, docs, logs and code comments; verify agents ignore them |
| 46 | Scrum Master Agent | Sprint planning support, daily stand-up summaries, blockers, sprint review and retrospective |
| 47 | Project Manager Agent | Milestones, risks, dependencies, delivery impact, escalation recommendations |
| 48 | Sprint orchestration | Connect backlog, sprint assignment, dependencies, PM and Scrum responsibilities |
| 49 | BI data model | Build clean analytical ticket/sprint/event dataset for reporting |
| 50 | BI metrics engine | Calculate lead time, cycle time, blocked time, QA time, throughput, reopen rate |
| 51 | Text-to-SQL Agent | User asks questions in natural language; agent produces restricted read-only SQL |
| 52 | SQL guardrails | Prevent DROP, DELETE, UPDATE, unrestricted joins or unauthorized access |
| 53 | BI dashboard | Visualize sprint performance, ticket aging, bottlenecks, throughput and cycle time |
| 54 | BI narrative Agent | Generate grounded explanations from verified SQL results rather than invented numbers |
| 55 | Full agent orchestrator | Connect BA → Investigator → PM/Scrum → Engineer → QA → Human → BI |
| 56 | End-to-end workflow | One submitted incident should successfully travel through the complete system |
| 57 | Workflow persistence | Resume interrupted workflows after restart; checkpoint state in persistent storage |
| 58 | Audit trail | Store agent, tool, input, output, approval, failure and transition records |
| 59 | Observability | Log model calls, tool calls, latency, token usage, failures, agent state and retrieval behavior |
| 60 | Evaluation dataset | Create 50–100 known scenarios: normal, ambiguous, impossible, malicious and conflicting-evidence cases |
| 61 | LLM baseline evaluation | Test raw LLM without RAG or agents |
| 62 | Naive RAG evaluation | Compare simple retrieval against baseline |
| 63 | Advanced RAG evaluation | Compare hybrid retrieval + reranking + grounding |
| 64 | Agent evaluation | Measure task completion, root-cause accuracy, tool reliability and workflow success |
| 65 | Security evaluation | Measure prompt-injection success, unauthorized-action attempts, tool misuse and blocked attacks |
| 66 | Reliability report | Produce benchmark comparing Baseline LLM vs RAG vs Advanced RAG vs Agentic system |
| 67 | Dockerization | Dockerize API, database, Ollama/vector store and supporting components |
| 68 | Local deployment | Start entire platform through docker compose up |
| 69 | CI pipeline | GitHub Actions for linting, tests, integration tests and AI evaluation smoke tests |
| 70 | Code quality cleanup | Refactor duplicated code, typing, naming, modules, dependencies and configuration |
| 71 | Security cleanup | Secrets via environment variables, .env.example, permissions, input sanitization |
| 72 | API documentation | Complete OpenAPI descriptions, endpoint examples, architecture documentation |
| 73 | Architecture documentation | System diagram, agent diagram, RAG architecture, database schema, workflow diagram |
| 74 | Agent documentation | Explain each agent’s purpose, tools, permissions, inputs, outputs and limitations |
| 75 | Security documentation | Document hallucination defenses, prompt injection controls, human approvals, least privilege |
| 76 | Evaluation documentation | Publish benchmarks, test methodology, limitations and observed failures |
| 77 | README overhaul | Employer-facing GitHub README: problem → architecture → demo → results → install → evaluation |
| 78 | Demo data | Add reproducible synthetic incidents, runbooks, logs and ticket scenarios |
| 79 | Employer demo scenario | Polish one end-to-end dashboard-refresh incident that demonstrates every major subsystem |
| 80 | Demo recording/screenshots | Produce screenshots/GIF/video showing incident intake through BI report |
| 81 | Resume bullets | Convert project accomplishments into measurable AI Engineer resume bullet points |
| 82 | Interview preparation | Prepare architectural questions, trade-offs, failures, security decisions and RAG explanations |
| 83 | Final regression run | Run complete unit, integration, RAG, agent and security test suites |
| 84 | GitHub release candidate | Tag v1.0.0-rc1, inspect repo as an employer would, fix broken instructions |
| 85 | Final release | Merge approved work into main, tag v1.0.0, publish final GitHub portfolio project |
