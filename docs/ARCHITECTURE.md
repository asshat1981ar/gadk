# Architecture Reference
## Cognitive Foundry — Current and Target Design

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Entry Points                                      │
│  python3 -m src.main          python3 -m src.cli.swarm_cli          │
│  (autonomous loop)             (operator commands)                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Google ADK Runner                                  │
│  Agent: Orchestrator                                                │
│  Session: SQLiteSessionService (sessions.db)                        │
│  Callbacks: ObservabilityCallback                                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ delegates to sub-agents
            ┌──────────────────┼────────────────────────┐
            ▼                  ▼                          ▼
        Ideator            Builder                    Critic
        (PLAN)          (IMPLEMENT)                 (REVIEW)
            │                                           │
            ▼                                           │
        Pulse / FinOps ◄──────────────────────────────┘
        (OPERATE)

[ Architect and Governor are implemented but NOT in sub_agents — TD-001 ]
```

### Agent Responsibilities

| Agent | Phase | Key Tools |
|-------|-------|-----------|
| Orchestrator | routing | `batch_execute`, `route_task`, `retrieve_planning_context`, `execute_capability` |
| Ideator | PLAN | `create_structured_task`, `search_web`, `batch_execute`, GitHub read tools |
| Builder | IMPLEMENT | `build_tool`, `read_file`, `write_file`, `list_directory` |
| Critic | REVIEW | `evaluate`, `review_pr`, `create_review_verdict`, `get_review_graph_decision` |
| Pulse | OPERATE | `generate_report` |
| FinOps | OPERATE | budget/cost queries |
| **Architect** | **ARCHITECT** | `draft_architecture_note`, `architecture_gate_payload` — **not wired** |
| **Governor** | **GOVERN** | `run_governance_review`, `register_external_gate` — **not wired** |

### Tool Execution Paths

```
ADK native function calling
    └── works for: gpt-4o, Gemini 2.x, Claude
    └── unreliable for: elephant-alpha → falls back to ▼

Custom Planner (src/planner.py)
    └── prompts model to emit JSON blocks in text
    └── parses ```json {...} ``` blocks with repair_json
    └── executes via _TOOL_REGISTRY (same as ADK dispatcher)
    └── supports: read_file, write_file, list_directory,
                  read_repo_file, list_repo_contents,
                  search_web, execute_python_code
```

### Data Flow

```
User / operator
    │
    ▼ writes to
prompt_queue.jsonl ──► dequeue_prompts() ──► process_prompt()
                                                   │
                                          ADK Runner.run_async()
                                                   │
                                          Agent tool calls
                                                   │
                                          ┌────────┴─────────┐
                                          ▼                   ▼
                                     state.json          events.jsonl
                                     (task state)        (audit trail)
                                          │
                                          ▼
                                     GitHub API
                                     (issues / PRs)
```

### SDLC Phase Flow

```
PLAN ──► ARCHITECT ──► IMPLEMENT ──► REVIEW ──► GOVERN ──► OPERATE
                                         │
                                         ▼ (rework edge, max 2 retries)
                                      IMPLEMENT
```

Quality gates evaluated at each transition boundary:
- `ContentGuardGate` (REVIEW, GOVERN) — reject low-value/leaked content
- `LintGate` (REVIEW, GOVERN) — ruff check
- `TypecheckGate` (REVIEW, GOVERN) — mypy
- `SecurityScanGate` (GOVERN) — bandit
- `TestCoverageGate` (GOVERN) — coverage.xml ≥ 65%
- `CriticReviewGate` (REVIEW) — LLM-backed review verdict

### Capability Layer

```
CapabilityRegistry
    ├── swarm.status     → _swarm_status_handler
    ├── repo.read_file   → _repo_read_file_handler
    ├── repo.list_dir    → _repo_list_directory_handler
    ├── smithery.call    → _smithery_tool_handler
    └── planning.retrieval → _planning_retrieval_handler (main.py)

CapabilityService.execute(name, **args)
    └── calls handler → CapabilityResult envelope
    └── exposed as: execute_capability() (ADK tool)
    └── exposed as: MCP tools (mcp/server.py)
```

### Retrieval / Memory

```
RETRIEVAL_BACKEND=keyword (default)
    └── KeywordRetriever — scans local spec/plan docs

RETRIEVAL_BACKEND=sqlite-vec / vector
    └── SqliteVecBackend — embeds text with LiteLLMEmbedder
    └── EmbedQuota — daily token cap
    └── VectorIndex — cosine similarity search
```

---

## Target Architecture (Phase 1–4)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                                │
│   Web Chat UI (Next.js)           VS Code Extension Sidebar                │
│   ┌────────────────────┐          ┌─────────────────────────────────────┐  │
│   │ React + shadcn/ui  │◄────────►│ Webview Panel + vscode-languageclient│  │
│   │ EventSource stream │          │ Swarm status + task board           │  │
│   └────────┬───────────┘          └──────────────┬──────────────────────┘  │
└────────────┼────────────────────────────────────┼──────────────────────────┘
             │ WebSocket / SSE                     │ WebSocket
             ▼                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                         API Gateway (FastAPI)                               │
│   POST /projects/{id}/chat      GET /projects/{id}/tasks                   │
│   WS  /projects/{id}/stream     POST /projects/{id}/approve/{item_id}      │
│   GET /projects/{id}/phases     GET /metrics                                │
│   Auth: JWT                     Rate limiting: per-user token budget        │
└────────────────────────────┬───────────────────────────────────────────────┘
                             │
             ┌───────────────┼────────────────────┐
             ▼               ▼                    ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐
│  ADK Runner     │  │  Task Queue  │  │  Conversation Context Service     │
│  (per project)  │  │  (arq/Redis) │  │  session store + retrieval index  │
│  Orchestrator   │  │  background  │  │  per project_id                   │
│  sub-agents     │  │  SDLC cycles │  └──────────────────────────────────┘
└─────────────────┘  └──────────────┘
             │
    ┌────────┴──────────┐
    ▼                   ▼
GitHub API         Code Sandbox
(PyGithub)         (subprocess)
```

### Key Architectural Decisions for Target State

1. **FastAPI backend** is the new entry point for human interaction; `src/main.py` becomes a background worker entry point.
2. **Multi-project isolation**: every `project_id` gets its own state directory, session, and retrieval index.
3. **ADK remains top-level runtime** — the web layer calls into ADK sessions, not the other way around.
4. **Architect and Governor are fully wired** into the Orchestrator so all 6 SDLC phases are covered autonomously.
5. **Streaming responses**: FastAPI streams LLM tokens via SSE/WebSocket so users see output as it generates.
6. **Human approval gates**: the API has explicit `POST /approve` endpoints that unblock phase transitions awaiting user input.
