# Component Research & Enhancement Ideation

> **For agentic workers:** This is a brainstorming/research artifact, not an implementation plan. Use it as input for future feature planning.

**Goal:** Research all major components the Cognitive Foundry uses and identify their unused capabilities that could enhance the system.

**Components Analyzed:** Google ADK, LiteLLM, prompt_toolkit, rich, PyGithub, Playwright

---

## 1. Google ADK (Agent Development Kit)

### Current Usage
- `Agent` with `LiteLlm` wrapper for OpenRouter
- `Runner` for execution
- `InMemorySessionService` (ephemeral, resets on restart)
- Basic tool delegation (`ask_ideator`)
- `types.Content` and `types.Part` for messages

### Unused Features — High Impact

#### 1.1 Persistent Session Storage
**What:** `InMemorySessionService` loses all conversation history on restart. ADK supports persistent backends.
**Enhancement:** Replace with a custom `SQLiteSessionService` or `JSONSessionService` so swarm sessions survive restarts. This enables long-running investigations where context matters.
**Files to touch:** `src/main.py`, new `src/services/session_store.py`

#### 1.2 Sub-Agents with Auto-Delegation
**What:** ADK supports `sub_agents=[...]` on an `Agent`, with `description` fields that let the parent LLM dynamically route to the right sub-agent.
**Enhancement:** Refactor our agents (Ideator, Builder, Critic, Pulse, FinOps) from standalone classes to proper ADK `sub_agents` under the Orchestrator. The Orchestrator's LLM would decide *which* agent to invoke based on the task description, not hardcoded logic.
**Files to touch:** `src/agents/orchestrator.py`, all agent files

#### 1.3 Workflow Agents (Sequential, Parallel, Loop)
**What:** ADK has `SequentialAgent`, `ParallelAgent`, `LoopAgent` for predictable pipelines.
**Enhancement:** Define standard workflows:
- **Ideation Pipeline:** `Sequential[Ideator → Critic → (if PASS) Builder]`
- **Health Check Loop:** `Loop[Pulse → (if DEGRADED) FinOps]`
**Files to touch:** `src/agents/workflows.py`, `src/main.py`

#### 1.4 Artifact Services
**What:** ADK can store and retrieve files (documents, images, code) associated with sessions.
**Enhancement:** When the Builder writes a tool to `src/staged_agents/`, register it as an artifact. The Critic can then fetch and evaluate it via the artifact service. Enables agents to work with binary outputs.
**Files to touch:** `src/agents/builder.py`, `src/agents/critic.py`

#### 1.5 ADK Evaluation Framework
**What:** `AgentEvaluator.evaluate()` can test execution paths against predefined cases.
**Enhancement:** Add eval tests that verify: "Given input X, Orchestrator delegates to Ideator, which creates a task with status PLANNED." Turn our existing pytest tests into ADK evals.
**Files to touch:** `tests/eval/`, `src/agents/`

#### 1.6 Callbacks / Hooks
**What:** ADK supports pluggable callbacks for pre/post tool execution, pre/post agent run.
**Enhancement:** Use callbacks for:
- Auto-logging every tool call to our structured logger
- Auto-recording metrics without decorators
- Human-in-the-loop gates before destructive operations
**Files to touch:** `src/observability/logger.py`, `src/observability/metrics.py`

#### 1.7 MCP (Model Context Protocol) Tools
**What:** ADK can consume MCP servers — external tools that expose capabilities via a standard protocol.
**Enhancement:** Instead of hardcoding `ScraperTool`, `GitHubTool`, etc., wrap them as MCP tools. Then external tools (databases, APIs) can be added without code changes.
**Files to touch:** `src/tools/`, `mcp_config.json`

---

## 2. LiteLLM

### Current Usage
- `LiteLlm` model wrapper pointing to OpenRouter (`openrouter/elephant-alpha`)
- Single model, no fallback

### Unused Features — High Impact

#### 2.1 Fallback Chains
**What:** When the primary model fails (rate limit, timeout, error), automatically try backup models.
**Enhancement:** Configure fallback chain: `elephant-alpha → claude-sonnet-4 → gemini-flash`. If OpenRouter hiccups, the swarm keeps working.
**Files to touch:** `src/agents/orchestrator.py`, `src/config.py`

#### 2.2 Cost Tracking per Request
**What:** LiteLLM can calculate and report the dollar cost of each API call.
**Enhancement:** Feed real costs into `FinOpsAgent` instead of just token counts. Track spend per task, per agent, per day. Alert when approaching budget.
**Files to touch:** `src/agents/finops.py`, `src/observability/metrics.py`

#### 2.3 Request Retries & Timeouts
**What:** Configure `num_retries`, `timeout`, `retry_after` on the router.
**Enhancement:** Our scraper and GitHub calls already have basic retries, but LLM calls don't. Add retry logic to `LiteLlm` instantiation so transient OpenRouter failures don't crash the swarm.
**Files to touch:** `src/agents/orchestrator.py`, `src/agents/ideator.py`

#### 2.4 Response Caching
**What:** LiteLLM supports Redis and in-memory caching of identical requests.
**Enhancement:** Cache ideation results for repeated topics. If someone asks about "Generative AI" twice within an hour, serve the cached response instead of burning tokens.
**Files to touch:** `src/config.py`, `src/agents/ideator.py`

#### 2.5 Observability Callbacks
**What:** Native integrations with Langfuse, LangSmith, Helicone, Prometheus.
**Enhancement:** Wire our structured logger into LiteLLM's callback system so every LLM call automatically emits a log entry with model, tokens, cost, latency, and trace_id.
**Files to touch:** `src/observability/logger.py`

---

## 3. prompt_toolkit

### Current Usage
- `PromptSession` with history, auto-suggest, `NestedCompleter`
- Basic key binding for `Ctrl+C`

### Unused Features — Medium Impact

#### 3.1 Syntax Highlighting
**What:** Pygments lexers can highlight input as the user types.
**Enhancement:** Highlight JSON in the REPL when users type `prompt '{"key": "value"}'`. Use `PygmentsLexer(JsonLexer)` for the prompt input.
**Files to touch:** `src/cli/interactive.py`

#### 3.2 Bottom Toolbar
**What:** A status bar at the bottom of the terminal showing live info.
**Enhancement:** Show swarm status in the toolbar: `Tasks: 3 | Health: HEALTHY | Tokens: 1,250`. Updates in real-time as the user types.
**Files to touch:** `src/cli/interactive.py`

#### 3.3 Multi-line Input
**What:** `multiline=True` lets users enter multi-line prompts.
**Enhancement:** Allow users to paste or type long multi-line prompts into the swarm. Useful for complex task descriptions.
**Files to touch:** `src/cli/interactive.py`

#### 3.4 Input Validation
**What:** `Validator` classes reject invalid input with error messages.
**Enhancement:** Validate that `tasks --status` only accepts known statuses (PLANNED, COMPLETED, STALLED, etc.).
**Files to touch:** `src/cli/interactive.py`

#### 3.5 Dialogs (Confirmations)
**What:** Built-in Yes/No, message box, input box dialogs.
**Enhancement:** Before executing `swarm stop`, show a confirmation dialog: "Are you sure you want to shut down the swarm?".
**Files to touch:** `src/cli/interactive.py`, `src/cli/swarm_cli.py`

---

## 4. rich

### Current Usage
- `Table`, `Panel`, `Layout`, `Live` for the dashboard
- Basic text styling

### Unused Features — Medium Impact

#### 4.1 Progress Bars
**What:** `Progress`, `SpinnerColumn`, `TextColumn` for async tasks.
**Enhancement:** Show a progress bar while the Ideator is scraping or while the Orchestrator is processing. Better UX than staring at a blank screen.
**Files to touch:** `src/cli/dashboard.py`, `src/main.py`

#### 4.2 Tree Views
**What:** `Tree` for hierarchical data display.
**Enhancement:** Render task dependencies as a tree. If Task B depends on Task A, show it visually. Also show agent hierarchy.
**Files to touch:** `src/cli/dashboard.py`, `src/cli/swarm_cli.py`

#### 4.3 JSON Pretty-Print
**What:** `json.dumps` via `rich.json.JSON` with syntax highlighting.
**Enhancement:** Pretty-print state.json, events.jsonl, and metrics.jsonl in the CLI with colors and collapsible sections.
**Files to touch:** `src/cli/swarm_cli.py`

#### 4.4 Tracebacks
**What:** `rich.traceback.install()` for beautiful exception rendering.
**Enhancement:** Replace default Python tracebacks with rich tracebacks in the CLI and dashboard. Makes debugging agent failures much easier.
**Files to touch:** `src/cli/swarm_cli.py`, `src/main.py`

#### 4.5 Logging Handler
**What:** `rich.logging.RichHandler` renders logs with colors in the console.
**Enhancement:** Use RichHandler for plain-text log mode (instead of JSON) so developers see colored, structured logs during local development.
**Files to touch:** `src/observability/logger.py`

---

## 5. PyGithub

### Current Usage
- `create_issue()` only

### Unused Features — High Impact

#### 5.1 Pull Request Automation
**What:** Create PRs, list PRs, review PRs, merge PRs.
**Enhancement:** After the Builder writes a new tool, create a PR instead of writing directly to `src/staged_agents/`. The Critic can then review the PR before merge.
**Files to touch:** `src/agents/builder.py`, `src/tools/github_tool.py`

#### 5.2 Labels & Milestones
**What:** Tag issues with labels like `autonomous`, `ideator`, `stalled`.
**Enhancement:** Auto-label GitHub issues by agent and status. Filter issues by label in the CLI.
**Files to touch:** `src/tools/github_tool.py`, `src/agents/ideator.py`

#### 5.3 Repository File Operations
**What:** Read, write, update files in the repo via the API.
**Enhancement:** The Builder can commit directly to the repo via PR. The Pulse agent can read `README.md` to generate health reports.
**Files to touch:** `src/tools/github_tool.py`

#### 5.4 Search
**What:** Search issues, PRs, code across the repository.
**Enhancement:** Before creating a new issue, search for duplicates. "There's already an issue about quantum computing — skipping creation."
**Files to touch:** `src/tools/github_tool.py`, `src/agents/ideator.py`

---

## 6. Playwright

### Current Usage
- Basic `page.goto()` and `page.content()` scraping

### Unused Features — Medium Impact

#### 6.1 Screenshots
**What:** `page.screenshot()` captures the page as an image.
**Enhancement:** When scraping fails or returns unexpected content, save a screenshot for debugging. Attach screenshots to GitHub issues.
**Files to touch:** `src/tools/scraper.py`

#### 6.2 PDF Generation
**What:** `page.pdf()` exports pages to PDF.
**Enhancement:** Generate PDF reports of scraped documentation for offline analysis.
**Files to touch:** `src/tools/scraper.py`

#### 6.3 Network Interception
**What:** `route.intercept()` blocks, modifies, or mocks network requests.
**Enhancement:** Block ads, trackers, and heavy media during scraping. Speed up scrapes by 50%+.
**Files to touch:** `src/tools/scraper.py`

#### 6.4 Browser Contexts (Isolated Sessions)
**What:** `browser.new_context()` creates isolated cookie/storage sessions.
**Enhancement:** Run multiple scrapes in parallel without cross-contamination. Each agent gets its own browser context.
**Files to touch:** `src/tools/scraper.py`

#### 6.5 Authentication State Persistence
**What:** `context.storage_state()` saves login state.
**Enhancement:** If scraping requires login (e.g., private repos), save auth state and reuse it across sessions.
**Files to touch:** `src/tools/scraper.py`

---

## Priority Ranking

| Priority | Feature | Component | Effort | Impact |
|----------|---------|-----------|--------|--------|
| P0 | Persistent Sessions | ADK | Medium | High |
| P0 | Fallback Chains | LiteLLM | Low | High |
| P0 | Sub-Agents with Auto-Delegation | ADK | Medium | High |
| P1 | Cost Tracking per Request | LiteLLM | Low | High |
| P1 | PR Automation | PyGithub | Medium | High |
| P1 | Callbacks / Hooks | ADK | Low | High |
| P1 | Bottom Toolbar | prompt_toolkit | Low | Medium |
| P2 | Workflow Agents | ADK | Medium | Medium |
| P2 | Progress Bars | rich | Low | Medium |
| P2 | Network Interception | Playwright | Low | Medium |
| P2 | Response Caching | LiteLLM | Low | Medium |
| P3 | Artifact Services | ADK | Medium | Medium |
| P3 | Tree Views | rich | Low | Low |
| P3 | Dialogs | prompt_toolkit | Low | Low |
| P3 | Screenshots | Playwright | Low | Low |

---

## Self-Review

1. **Spec coverage:** Every major component in the stack has been analyzed for unused features.
2. **Placeholder scan:** No TBDs or TODOs. Each item has a concrete enhancement suggestion.
3. **Type consistency:** N/A — this is a research document, not an implementation plan.
4. **Handoff fidelity:** Components match the actual codebase dependencies in `requirements.txt` and source files.

---

## Recommended Next Steps

1. **Pick P0 items** and write implementation plans for each
2. **Start with Fallback Chains** — lowest effort, highest reliability impact
3. **Then Persistent Sessions** — enables long-running swarm behavior
4. **Then Sub-Agents** — cleans up the current hardcoded delegation logic
