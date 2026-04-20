# Tech Stack Reference
## Cognitive Foundry — Current and Target

---

## Current Stack (as-built)

### Runtime & Orchestration
| Component | Library / Service | Version | Notes |
|-----------|-------------------|---------|-------|
| Agent runtime | `google-adk` | ≥ 0.3 | Top-level session + routing |
| LLM backend | `litellm` | ≥ 1.50 | Normalises provider APIs |
| LLM provider | OpenRouter | — | All models routed through `openrouter/` prefix |
| Primary model | `openrouter/elephant-alpha` | — | Text-based tool-call parsing (see planner.py) |
| Tool model | `openrouter/openai/gpt-4o` | — | Function calling; configurable via `OPENROUTER_TOOL_MODEL` |
| Fallback chain | Gemini 2.5-flash → Gemini 2.0-flash → Claude Sonnet 4 → elephant-alpha | — | |
| Structured output | `instructor` | ≥ 1.3 | Optional; `INSTRUCTOR_ENABLED` flag |
| Workflow graphs | `langgraph` | ≥ 0.2 | Optional subordinate subflows; `LANGGRAPH_ENABLED` flag |
| RAG / retrieval | `llama-index` | ≥ 0.11 | Optional; `LLAMAINDEX_ENABLED` flag |
| PydanticAI | `pydantic-ai` | ≥ 0.0.30 | Optional; `PYDANTIC_AI_ENABLED` flag |

### Tool Execution
| Component | Library | Notes |
|-----------|---------|-------|
| Parallel dispatcher | `asyncio.gather` + `asyncio.Semaphore` | MAX_CONCURRENCY = 10 |
| Sandbox | `exec()` in subprocess | `src/tools/sandbox_executor.py` |
| Web search | `duckduckgo-search` | ≥ 6.0 |
| Web scraper | `playwright` | ≥ 1.40 |
| GitHub integration | `pygithub` | ≥ 2.1 |
| MCP server | `mcp` (FastMCP) | ≥ 1.0 |
| Smithery bridge | HTTP via `httpx` | External tool marketplace |

### Data & State
| Component | Library / Format | Notes |
|-----------|-----------------|-------|
| Task state | `state.json` (flat file) | `StateManager` with `fcntl.flock` |
| Audit events | `events.jsonl` (append-only) | One JSON line per event |
| Sessions | `sessions.db` (SQLite) | ADK `SQLiteSessionService` |
| Vector index | `sqlite-vec` | Optional; `RETRIEVAL_BACKEND=sqlite-vec` |
| Embedder | `litellm` (`text-embedding-3-small`) | `EmbedQuota` daily cap |
| File lock | `fcntl.flock` (POSIX) | `src/utils/file_lock.py` |

### Configuration
| Component | Library | Notes |
|-----------|---------|-------|
| Settings | `pydantic-settings` | ≥ 2.1; loads from env + `.env` |
| Validation | `pydantic` | ≥ 2.5 |
| JSON repair | `json-repair` | ≥ 0.25; planner tool-call recovery |
| Retry logic | `tenacity` | ≥ 8.2 |

### CLI & UI
| Component | Library | Notes |
|-----------|---------|-------|
| CLI parser | `argparse` (stdlib) | `src/cli/swarm_cli.py` |
| Interactive REPL | `prompt_toolkit` | ≥ 3.0 |
| Rich dashboard | `rich` | ≥ 13.0 |

### Observability
| Component | Library | Notes |
|-----------|---------|-------|
| Structured logging | stdlib `logging` + custom `JsonFormatter` | `src/observability/logger.py` |
| Metrics | Custom registry → `metrics.jsonl` | `src/observability/metrics.py` |
| Cost tracking | Custom `CostTracker` → `costs.jsonl` | `src/observability/cost_tracker.py` |
| LiteLLM callbacks | `litellm` callbacks | `src/observability/litellm_callbacks.py` |
| Optional APM | Langfuse / Helicone / AgentOps / MLflow / Sentry | All feature-flagged |

### Dev Tooling
| Component | Library | Version |
|-----------|---------|---------|
| Linter + formatter | `ruff` | 0.5.7 (pinned) |
| Type checker | `mypy` | ≥ 1.10 |
| Security scan | `bandit` | ≥ 1.7 |
| Dependency audit | `pip-audit` | ≥ 2.7 |
| Test runner | `pytest` + `pytest-asyncio` | ≥ 8.0 / 0.23 |
| Coverage | `coverage[toml]` | ≥ 7.5 |
| Pre-commit hooks | `pre-commit` | ≥ 3.7 |

---

## Target Stack Additions (Phases 1–4)

### Web Backend (Phase 1–2)
| Component | Library | Rationale |
|-----------|---------|-----------|
| API server | `fastapi` | Async-native; WebSocket support |
| ASGI server | `uvicorn` | Standard production ASGI |
| WebSocket streaming | FastAPI + `asyncio.Queue` | Stream LLM tokens to UI |
| Auth | `python-jose` + `passlib` | JWT for multi-user isolation |
| DB (multi-tenant state) | `sqlalchemy` async + PostgreSQL | Replace flat `state.json` at scale |
| Task queue | `celery` + Redis (or `arq`) | Background SDLC loop workers |

### Web Frontend (Phase 2)
| Component | Library | Rationale |
|-----------|---------|-----------|
| Framework | Next.js 14+ (React) | SSR, streaming, App Router |
| Streaming | `react-markdown` + EventSource | Render streamed tokens |
| State | Zustand or React Query | Client-side task/session state |
| UI components | shadcn/ui + Tailwind CSS | Accessible, composable |
| Code editor embed | Monaco Editor | In-browser code review |

### VS Code Extension (Phase 2)
| Component | Library | Rationale |
|-----------|---------|-----------|
| Extension scaffold | `yo code` (Yeoman) | Standard VS Code extension |
| Language client | `vscode-languageclient` | LSP integration |
| Webview panel | VS Code Webview API | Embed chat UI in sidebar |
| IPC | VS Code `window.createOutputChannel` + WebSocket | Swarm status streaming |

### Code Generation Improvements (Phase 3)
| Component | Library | Rationale |
|-----------|---------|-----------|
| AST manipulation | `libcst` (Python) | Safe refactoring without regex |
| Formatter bridge | `black` / `prettier` / `ktlint` | Language-specific formatting |
| Dependency resolver | `pip-tools` / `npm` / `gradle` | Auto-update dependency files |

---

## Key Tech Constraints

1. **ADK is the top-level runtime.** LangGraph, PydanticAI, LlamaIndex are subordinate optional libraries — never replace the ADK session loop.
2. **All LLM calls go through OpenRouter.** Model strings must carry the `openrouter/` prefix to use OpenRouter's `/chat/completions` endpoint and avoid provider-native 404s.
3. **elephant-alpha requires the custom planner.** Native ADK function calling is unreliable with that model; `src/planner.py` is the stable path.
4. **Test mode must work without google-adk.** All agent modules guard ADK imports so unit tests can run in pure-Python mode with `MockLiteLlm`.
5. **No secrets in state or GitHub artifacts.** `GitHubTool` sanitizes issue/PR bodies; `src/tools/filesystem.py` blocks secrets-like file patterns.
