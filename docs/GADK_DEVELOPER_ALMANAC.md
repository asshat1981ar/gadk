# GADK Developer Almanac

> **Complete technical reference for building, extending, and operating the Cognitive Foundry Swarm.**
> This is a living supplement to `CLAUDE.md` (project management) and `GADK_AGENT_DEVELOPER_GUIDE.md` (architecture + agent patterns). Where those docs give you the *what* and *why*, this almanac gives you the *exactly how* — exact signatures, import paths, error classes, config keys, file formats, and runtime behaviors.
> Last updated: 2026-04-21

---

## Table of Contents

1. [Startup Sequence](#1-startup-sequence)
2. [Config System](#2-config-system)
3. [Exception Hierarchy](#3-exception-hierarchy)
4. [Planner — Text + Structured](#4-planner--text--structured)
5. [AutonomousSDLC Engine](#5-autonomoussdlc-engine)
6. [Tool Dispatcher](#6-tool-dispatcher)
7. [Capabilities System](#7-capabilities-system)
8. [PhaseController + Phase Transitions](#8-phasecontroller--phase-transitions)
9. [Workflow Graphs (Review + Retry)](#9-workflow-graphs-review--retry)
10. [StateManager](#10-statemanager)
11. [SessionStore + SQLiteSessionService](#11-sessionstore--sqlitesessionservice)
12. [Self-Prompt Engine](#12-self-prompt-engine)
13. [RetrievalContext](#13-retrievalcontext)
14. [Agents — Full Reference](#14-agents--full-reference)
15. [CLI Commands](#15-cli-commands)
16. [MCP Server + SDLC Client](#16-mcp-server--sdlc-client)
17. [Observability Stack](#17-observability-stack)
18. [Workflows for Common Tasks](#18-workflows-for-common-tasks)

---

## 1. Startup Sequence

**File:** `src/main.py`

```
main() entry point:
  1. clear_shutdown()          — remove stale sentinel
  2. write_pid()               — write PID to swarm.pid
  3. setup_callbacks()          — wire LiteLLM + ADK callbacks
  4. SQLiteSessionService()     — create/reload session DB
  5. session_service.create_session() — create swarm session
  6. Runner(orchestrator_agent, app_name, session_service) — build ADK runner
  7. ObservabilityCallback() wired to runner.callbacks
  8. API key check (OPENROUTER_API_KEY required)
  9. AUTONOMOUS_MODE?
     → true:  run_swarm_loop() + _self_prompt_tick() concurrently
     → false: run_single()
```

### 1.1 Swarm Loop (`run_swarm_loop`)

```python
# src/main.py — run_swarm_loop
initial_query = _build_autonomous_prompt("project-chimera")
if should_use_planner_for_autonomous_run(Config.OPENROUTER_MODEL):
    await _run_autonomous_prompt_with_tools(initial_query)  # bypass ADK
else:
    await process_prompt(runner, session, initial_query)

while True:
    if is_shutdown_requested(): break
    prompts = dequeue_prompts()  # from prompt_queue.jsonl
    for entry in prompts:
        await process_prompt(runner, session, entry["prompt"])
    await asyncio.sleep(Config.SWARM_LOOP_POLL_SEC)
```

### 1.2 Self-Prompt Tick

Runs as `asyncio.create_task(_self_prompt_tick(sm))` alongside the swarm loop when `SELF_PROMPT_ENABLED=true`. Cadence is `SELF_PROMPT_TICK_INTERVAL_SEC` (default 60s).

```python
# src/main.py — _self_prompt_tick
while not is_shutdown_requested() and not _self_prompt.off_switch_active():
    await asyncio.to_thread(_self_prompt.run_once, sm=sm)
    await asyncio.sleep(effective_interval)
```

### 1.3 ADK Fallback to Planner

When `process_prompt` encounters a JSON decode error in ADK tool calls (common with `elephant-alpha`), it automatically retries via `run_planner`:

```python
# src/main.py — _should_fallback_to_planner
# Returns True when the exception chain contains JSONDecodeError
# or "tool" + "json" + any of ("decode", "malformed", "invalid", "parse")
```

---

## 2. Config System

**Files:** `src/config.py` (Settings class + Config shim)

### 2.1 Settings (Pydantic)

All settings are loaded from environment + `.env` via `pydantic_settings.BaseSettings`:

```python
# src/config.py — Settings fields
github_token: str | None = None
repo_name: str | None = None
state_table_type: str = "json"
autonomous_mode: bool = False
test_mode: bool = False
pydantic_ai_enabled: bool = False
instructor_enabled: bool = False
langgraph_enabled: bool = False          # enable LangGraph-accelerated workflow graphs
llamaindex_enabled: bool = False
token_quota_per_task: int = 50000
openrouter_api_key: str | None = None
openrouter_api_base: str = "https://openrouter.ai/api/v1"
openrouter_model: str = "openrouter/elephant-alpha"
openrouter_tool_model: str = "openrouter/elephant-alpha"
fallback_models: list[str] = Field(default_factory=_default_fallback_models)
llm_timeout: int = 30
llm_retries: int = 3
self_prompt_enabled: bool = False  # DEPRECATED — superseded by ReflectionNode
self_prompt_max_per_hour: int = 6  # DEPRECATED — superseded by ReflectionNode
sdlc_mcp_enabled: bool = False
retrieval_backend: Literal["keyword", "vector", "sqlite-vec", "sqlitevec"] = "keyword"
embed_model: str = "openrouter/openai/text-embedding-3-small"
swarm_loop_poll_sec: float = 2.0
self_prompt_tick_interval_sec: float = 60.0  # DEPRECATED — superseded by ReflectionNode
planner_max_content_bytes: int = 500_000
```

### 2.2 Config Shim

Code uses `Config.OPENROUTER_API_KEY` (uppercase, no `getattr` needed). The `Settings` class is the source of truth.

```python
# All config access goes through this shim
Config.OPENROUTER_API_KEY      # → _settings.openrouter_api_key
Config.OPENROUTER_MODEL        # → _settings.openrouter_model
Config.TEST_MODE               # → _settings.test_mode
Config.LANGGRAPH_ENABLED      # → _settings.langgraph_enabled
Config.FALLBACK_MODELS         # → _settings.fallback_models
Config.MODEL_CAPABILITY_MAP    # hardcoded dict (not from env)
Config.MODEL_COST_MAP          # hardcoded dict (not from env)
```

### 2.3 Model Routing

`Config.MODEL_CAPABILITY_MAP` maps task types to preferred models in priority order:

```python
Config.MODEL_CAPABILITY_MAP = {
    "code":    ["openrouter/openai/gpt-4o", "openrouter/anthropic/claude-sonnet-4", ...],
    "review":  ["openrouter/anthropic/claude-sonnet-4", "openrouter/openai/gpt-4o", ...],
    "analysis":["openrouter/anthropic/claude-sonnet-4", "openrouter/openai/gpt-4o", ...],
    "creative": ["openrouter/openai/gpt-4o", "openrouter/google/gemini-2.5-pro", ...],
    "quick":   ["openrouter/openai/gpt-4o-mini", "openrouter/google/gemini-2.0-flash-001", ...],
}
```

---

## 3. Exception Hierarchy

**File:** `src/exceptions.py`

```
SwarmError (base)
├── SwarmStartupError       — session/runner/service init failure
│   └── raises: component=str, session_id
├── ToolExecutionError       — tool call failure
│   └── raises: tool_name, tool_args
├── PromptProcessingError    — ADK/planner execution failure
│   └── raises: prompt, stage, use_planner_fallback
├── ConfigurationError       — missing/invalid env/config
│   └── raises: config_key, config_value
├── SwarmLoopError           — autonomous loop crash
│   └── raises: iteration, recoverable=bool
└── SelfPromptError          — self-prompt background task crash
    └── raises: tick_count
```

All exceptions inherit `SwarmError` which provides:
- `session_id: str | None`
- `context: dict[str, Any]`
- `to_log_context()` → dict for structured logging

```python
# Example: catching SwarmStartupError
from src.exceptions import SwarmStartupError, ConfigurationError

try:
    await session_service.create_session(...)
except SwarmStartupError as e:
    logger.error(f"Startup failed in {e.component}: {e}",
                 extra=e.to_log_context())
    raise

# Example: catching ConfigurationError
if not os.getenv("OPENROUTER_API_KEY"):
    raise ConfigurationError(
        "OPENROUTER_API_KEY not found",
        config_key="OPENROUTER_API_KEY",
        session_id=session.id
    )
```

---

## 4. Planner — Text + Structured

**File:** `src/planner.py` (~440 lines)

### 4.1 Text Planner (`run_planner`)

```python
async def run_planner(
    user_prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    max_iterations: int = 10,
    model: str = None,              # defaults to Config.OPENROUTER_MODEL
    allowed_tools: set | None = None,  # filter tool registry
) -> str:
    """
    Lightweight planner: LLM → parse tool calls → execute → feed back → repeat.
    Handles multiple JSON formats the LLM might emit.
    """
```

**Flow:**
1. Injects `TOOL_PROMPT_SUFFIX` into system prompt (tool registry + JSON format spec)
2. Calls `_llm_turn()` → parses ````json ... ``` ` blocks
3. Extracts tool calls via `_parse_tool_calls()` — 6 different formats supported
4. Filters by `allowed_tools` if provided
5. Executes all calls concurrently via `asyncio.gather`
6. Appends results to messages, loops
7. On max_iterations: sends final "no more tools" message, returns last text

**Retry behavior:**
- `AsyncRetrying` (tenacity) for `EmptyPlannerResponseError`, `TimeoutError`, `ConnectionError`, `RateLimitError`
- `wait_exponential(multiplier=1, min=1, max=8)`

**Tool registry:** `_TOOL_REGISTRY` from `src/tools/dispatcher.py`

### 4.2 Structured Planner (`run_planner_structured`)

```python
async def run_planner_structured(
    user_prompt: str,
    response_model: type[BaseModel],   # Pydantic model
    system_prompt: str = "You are a helpful assistant.",
    model: str = None,
) -> BaseModel:                        # validated Pydantic model
```

Uses Instructor bridge via `request_structured_output()`. Returns a fully validated Pydantic object.

### 4.3 Tool Call Extraction Formats

The planner handles 6 JSON formats the LLM might emit:

```python
# Format 1: canonic
{"action": "tool_call", "tool_name": "read_file", "args": {"path": "src/main.py"}}

# Format 2: simplified
{"action": "write_file", "args": {"path": "a.py", "content": "..."}}

# Format 3: nested arguments
{"action": "tool_call", "arguments": {"tool_name": "x", "args": {...}}}

# Format 4: flat root-level
{"tool_name": "read_file", "args": {"path": "a.py"}}

# Format 5: tools array
{"action": "read_file", "tools": [{"name": "x", "arguments": {...}}]}

# Format 6: inline function call
read_file("src/main.py")
```

### 4.4 `_execute_tool_call`

```python
async def _execute_tool_call(call: dict[str, Any]) -> dict[str, Any]:
    # Returns: {"status": "success"|"error", "tool_name": str, "output": Any, "message": str}
    name = call.get("tool_name")
    if name not in _TOOL_REGISTRY:
        return {"status": "error", "message": f"Tool '{name}' not found."}
    func = _TOOL_REGISTRY[name]
    if asyncio.iscoroutinefunction(func):
        result = await func(**args)
    else:
        result = func(**args)
    registry.record_tool_call(name, 0.0)
    return {"status": "success", "tool_name": name, "output": result}
```

---

## 5. AutonomousSDLC Engine

**File:** `src/autonomous_sdlc.py` (~480 lines)

### 5.1 Class Signature

```python
class AutonomousSDLCEngine:
    def __init__(
        self,
        state_manager: StateManager | None = None,
        github_tool: GitHubTool | None = None,
        phase_controller: PhaseController | None = None,
    ) -> None:
```

### 5.2 Cycle Flow

```
run_cycle():
  _discover()     → GitHub repo scan via run_planner (Ideator)
       ↓
  _plan(tasks)    → pick highest-priority non-in-flight task
       ↓
  WorkItem @ PLAN → ensure_work_item() + phase=PLAN
       ↓
  PLAN → ARCHITECT: _architecture_note_from_task() (no LLM, pure synthesis)
       ↓
  ARCHITECT → IMPLEMENT: _build(task)
       ↓
  IMPLEMENT → REVIEW: _review(artifact, task) + bounded rework loop
       ↓
  REVIEW → GOVERN: register_external_gate()
       ↓
  GOVERN → OPERATE: _deliver(artifact, task, review)
       ↓
  save_work_item() + log metrics
```

### 5.3 Key Constants

```python
REPO = Config.REPO_NAME                    # "project-chimera"
MAX_CYCLES = int(os.getenv("MAX_CYCLES", "10"))
CYCLE_SLEEP_SEC = int(os.getenv("CYCLE_SLEEP_SEC", "30"))
SHUTDOWN_FILE = os.getenv("SHUTDOWN_FILE", ".shutdown_sdlc")
TASKS_FILE = "docs/sdlc_tasks.json"
MAX_REVIEW_RETRIES = int(os.getenv("MAX_REVIEW_RETRIES", "2"))
```

### 5.4 `_slugify_task_id`

```python
def _slugify_task_id(prefix: str, title: str, max_len: int = 40) -> str:
    # "Add user auth" → "sdlc-add-user-auth"
    # Validates against r"^[a-z0-9][a-z0-9\-]{0,62}$"
    # Raises ValueError if title produces unsafe ID
```

### 5.5 `_extract_review_status`

```python
def _extract_review_status(review_text: str) -> str:
    # Returns: "pass" | "retry" | "block"
    # Looks for "Status: pass|retry|block" in formatted review
    # Falls back to keyword scanning: "block" → "block",
    # "retry|fail|issue|concern" → "retry", else "pass"
```

### 5.6 Bounded Rework Loop

```python
# Inside run_cycle():
while True:
    next_step = self.controller.decide_rework(
        item,
        builder_attempts=builder_attempts,
        review_status=review_status,
        latest_summary=review[:200],
        max_retries=MAX_REVIEW_RETRIES,
    )
    if next_step == "stop":        break  # review passed
    if next_step == "critic_stop":  # blocked or budget exhausted
        self.tasks_failed += 1
        return False
    # next_step == "builder": rework
    rebuilt = await self._build(task)
    review = await self._review(artifact, task)
    review_status = _extract_review_status(review)
```

---

## 6. Tool Dispatcher

**File:** `src/tools/dispatcher.py` (185 lines)

```python
from src.tools.dispatcher import register_tool, execute_capability

# Register a tool
register_tool("my_tool", my_function)

# Execute via dispatcher
result = execute_capability("my_tool", {"arg": "value"})
```

The dispatcher is a `dict[str, Callable]` registry. Tools are registered at startup in `main.py`:

```python
# src/main.py — tool registration at startup
register_tool("execute_capability", execute_capability)
register_tool("search_web", search_web)
register_tool("execute_python_code", execute_python_code)
register_tool("call_smithery_tool", call_smithery_tool)
register_tool("read_file", read_file)
register_tool("write_file", write_file)
register_tool("list_directory", list_directory)
register_tool("read_repo_file", read_repo_file)
register_tool("list_repo_contents", list_repo_contents)
register_tool("retrieve_planning_context", retrieve_planning_context)
```

---

## 7. Capabilities System

**File:** `src/capabilities/` (registry, service, contracts, helpers)

### 7.1 Register a Capability

```python
from src.capabilities.registry import CapabilityRegistry
from src.capabilities.service import CapabilityService

registry = CapabilityRegistry()
registry.register(
    name="my.capability",
    description="Does something useful",
    backend="local",
    handler=lambda request: {"result": "ok"},
)
service = CapabilityService(registry)
result = await service.execute("my.capability", arg="value")
```

### 7.2 Capability Result Shape

```python
# src/capabilities/service.py — CapabilityResult
class CapabilityResult:
    status: str              # "success" | "error"
    payload: Any             # the actual result
    error: str | None
    source_backend: str
    retryable: bool
```

### 7.3 Agent Contracts (Pydantic Models)

```python
# src/services/agent_contracts.py
DelegationDecision    — target_agent, reason, required_capabilities
TaskProposal          — title, summary, description, acceptance_criteria, recommended_agent
ReviewVerdict         — status: Literal["pass", "retry", "block"], summary, concerns
SpecialistRegistration— name, role, description, inputs, outputs, capability_needs
AgentDecision         — confidence, reasoning, action, payload, estimated_cost_usd
AgentMemory           — agent_id, memory_type, content, timestamp, ttl
```

---

## 8. PhaseController + Phase Transitions

**File:** `src/services/phase_controller.py`

```python
from src.services.phase_controller import PhaseController
from src.services.sdlc_phase import Phase, WorkItem

controller = PhaseController(state_manager=sm)

# Advance a WorkItem to the next phase
result = controller.advance(
    work_item,
    target=Phase.ARCHITECT,
    reason="Architecture complete",
    force=False,   # skip quality gates (use with caution)
)
# result: {"allowed": bool, "skipped": list[str], "gates_run": int}

# Bounded rework decision
next_step = controller.decide_rework(
    work_item,
    builder_attempts=1,
    review_status="retry",
    latest_summary="...",
    max_retries=2,
)
# next_step: "stop" | "builder" | "critic_stop"
```

Phase transitions write `phase.transition` events to `events.jsonl`.

---

## 9. Workflow Graphs (Review + Retry)

**File:** `src/services/workflow_graphs.py` (193 lines)

### 9.1 LangGraph Opt-In

```python
from src.services.workflow_graphs import LANGGRAPH_AVAILABLE

if LANGGRAPH_AVAILABLE:
    # Uses LangGraph-accelerated path
else:
    # Pure Python fallback (identical semantics)
```

LangGraph is **subordinate** to ADK. The graph only runs inside individual workflow nodes — the outer session/routing lifecycle is always owned by ADK.

### 9.2 Review Rework Decision

```python
from src.services.workflow_graphs import (
    ReviewLoopState,
    run_review_rework_cycle,
)

state = ReviewLoopState(
    builder_attempts=1,
    review_status="retry",   # "pass" | "retry" | "block"
    latest_summary="Missing null check",
)
decision = run_review_rework_cycle(state, max_retries=2)
# decision.next_step: "stop" | "builder" | "critic_stop"
```

**Decision table:**

| review_status | attempts < max | attempts >= max |
|---|---|---|
| pass | stop | stop |
| block | critic_stop | critic_stop |
| retry | builder | critic_stop |

### 9.3 Autonomous Retry

```python
from src.services.workflow_graphs import (
    AutonomousRetryState,
    run_autonomous_retry,
)

state = AutonomousRetryState(
    cycle_attempts=2,
    last_status="retry",     # "success" | "retry" | "stop"
    failure_reason="...",
)
decision = run_autonomous_retry(state, max_cycles=3)
# decision.next_step: "retry" | "stop"
```

---

## 10. StateManager

**File:** `src/state.py`

```python
from src.state import StateManager

sm = StateManager(
    filename="state.json",        # default
    event_filename="events.jsonl",
)
sm.get_all_tasks()                # → dict of all tasks
sm.get_task(task_id)             # → task dict or None
sm.set_task(task_id, data)       # set task fields
sm.update_work_item(task_id, phase=Phase.PLAN)  # typed phase update
sm.list_work_items()             # → list[WorkItem]
```

**Event log:** `events.jsonl` is append-only. Events look like:
```json
{"event": "phase.transition", "task_id": "sdlc-xxx", "from": "PLAN", "to": "ARCHITECT", "reason": "...", "ts": "..."}
```

---

## 11. SessionStore + SQLiteSessionService

**File:** `src/services/session_store.py`

```python
from src.services.session_store import SQLiteSessionService

service = SQLiteSessionService(db_path="sessions.db")
session = await service.create_session(user_id="swarm_admin", app_name="CognitiveFoundry")
# session.id → UUID string
```

Used by `src/main.py` to create an ADK session for the orchestrator.

---

## 12. ReflectionNode (Supersedes Self-Prompt Engine)

**File:** `src/orchestration/reflection_node.py` (~120 lines)

```python
from src.orchestration.reflection_node import ReflectionNode

node = ReflectionNode(mcp_available=True)
result = await node.analyze_previous_step(
    task_query="build authentication for the API",
    previous_output={"status": "errors", "errors": ["KeyError: token"]},
)
# result.errors, result.retry, result.gaps, result.deliverable
```

**How it works:**
1. Attempts MCP `sequential_thinking` when `mcp_available=True`
2. Falls back to rule-based keyword analysis when MCP unavailable
3. Detects: errors → retry signal, missing coverage → gaps, successful build → deliverable

**Migration from `self_prompt.py`:**
All functions in `src/services/self_prompt.py` are **deprecated** and emit `DeprecationWarning` on every call:
- `collect_coverage_signals` → ReflectionNode gap analysis
- `collect_event_log_signals` → ReflectionNode event analysis
- `collect_backlog_signals` → ReflectionNode backlog analysis
- `synthesize` → ReflectionNode intent synthesis
- `dispatch` / `run_once` → ReflectionNode analysis + GraphOrchestrator execution

**CLI (deprecated):**
```bash
python3 -m src.cli.swarm_cli self-prompt --dry-run   # emits 4 DeprecationWarnings
python3 -m src.cli.swarm_cli self-prompt            # emits 4 DeprecationWarnings
```

**Off-switch (deprecated):**
```python
from src.services import self_prompt as _self_prompt
_self_prompt.off_switch_active()   # deprecated — use .swarm_shutdown instead
```

---

## 13. RetrievalContext

**File:** `src/services/retrieval_context.py` (688 lines)

```python
from src.services.retrieval_context import (
    RetrievalContext,
    RetrievalQuery,
    retrieve_context,
    retrieve_planning_context,
)

ctx = RetrievalContext()
result = await ctx.get_context(task_id="t-1", query="authentication")
```

**Backends:** `keyword` (default), `vector` (ChromaDB), `sqlite-vec`

---

## 14. Agents — Full Reference

### 14.1 Orchestrator (75 lines)

```python
from src.agents.orchestrator import orchestrator_agent
# The ADK Agent that routes to specialists based on phase
```

### 14.2 Builder (704 lines — largest agent)

```python
from src.agents.builder import (
    implement_task,        # pure function
    implement_pr,           # pure function
    builder_agent,         # ADK Agent wrapper
)
```

**Key methods:**
- `implement_task()` — writes staged agent output
- `implement_pr()` — opens GitHub PR

### 14.3 Ideator (130 lines)

```python
from src.agents.ideator import ideator_agent
# Owns PLAN phase: goal → structured tasks
```

### 14.4 Architect (186 lines)

```python
from src.agents.architect import draft_architecture_note
# Produces ADR-style architecture decisions
# `draft_architecture_note()` is a pure function (no ADK needed)
```

### 14.5 Critic (104 lines)

```python
from src.agents.critic import critic_agent
# REVIEW phase: bounded retry code review
```

### 14.6 Governor (220 lines)

```python
from src.agents.governor import register_external_gate
# GOVERN phase: release readiness gates
# `register_external_gate()` — writes governance verdict
```

### 14.7 Pulse (670 lines)

```python
from src.agents.pulse import (
    HealthReport,
    AlertSeverity,
    pulse_agent,
)
# OPERATE phase: health monitoring + alerting
```

### 14.8 FinOps (816 lines — second largest)

```python
from src.agents.finops import (
    BudgetAlert,
    tracker,              # CostTracker instance
    get_current_costs,
    set_budget_alert,
    get_budget_recommendations,
)
# OPERATE phase: cost tracking + budget management
```

---

## 15. CLI Commands

**File:** `src/cli/swarm_cli.py`

```bash
# Start the swarm
python3 -m src.main

# CLI operations
python3 -m src.cli.swarm_cli status                  # Health check
python3 -m src.cli.swarm_cli tasks                   # List work items
python3 -m src.cli.swarm_cli queue                   # Inspect prompt queue
python3 -m src.cli.swarm_cli phase status <id>        # Phase status
python3 -m src.cli.swarm_cli phase advance <id> <PHASE>  # Advance phase
python3 -m src.cli.swarm_cli self-prompt --dry-run    # Self-prompt preview
python3 -m src.cli.swarm_cli self-prompt              # Write prompts to queue

# Shutdown
python3 -m src.cli.swarm_ctl stop                    # Create shutdown sentinel
```

### 15.1 Prompt Queue Files

```python
# src/cli/swarm_ctl.py
QUEUE_PATH = "prompt_queue.jsonl"       # pending prompts
SENTINEL_PATH = ".shutdown_sdlc"         # shutdown sentinel
PID_FILE = "swarm.pid"                   # running PID
```

---

## 16. MCP Server + SDLC Client

### 16.1 MCP Server (`src/mcp/server.py` — 114 lines)

Provides 3 tools to external MCP clients:

```python
# Build and run
server = build_mcp_server()  # returns FastMCP instance
server.run(transport="stdio")

# Tools exposed:
# 1. swarm_status  → _build_swarm_status_payload() → CapabilityResult envelope
# 2. repo_read_file(path: str) → CapabilityResult envelope
# 3. repo_list_directory(path: str = ".") → CapabilityResult envelope
```

### 16.2 SDLC Client (`src/mcp/sdlc_client.py` — 173 lines)

Internal MCP client used by agents to call the MCP server. Enabled when `SDLC_MCP_ENABLED=true`.

```bash
python3 -m src.mcp.server   # Start the MCP server (separate from main swarm)
```

---

## 17. Observability Stack

### 17.1 Logging

```python
from src.observability.logger import configure_logging, get_logger, set_trace_id, set_session_id

configure_logging(level="INFO", json_format=True)
logger = get_logger(__name__)
logger.info("event_name", extra={"key": "value"})
set_trace_id("cycle-1")
set_session_id("session-uuid")
```

### 17.2 Metrics

```python
from src.observability.metrics import registry

registry.record_tool_call("read_file", 0.0)         # tool_name, cost
registry.record_tool_call("read_file", 0.0, error=Exception("timeout"))
```

### 17.3 LiteLLM Callbacks

```python
from src.observability.litellm_callbacks import setup_callbacks
setup_callbacks()   # called in main() at startup
```

### 17.4 ADK Callbacks

```python
from src.observability.adk_callbacks import ObservabilityCallback
runner.callbacks = [ObservabilityCallback()]
```

### 17.5 Cost Tracking

```python
from src.observability.cost_tracker import CostTracker
tracker = CostTracker()
```

---

## 18. Workflows for Common Tasks

### 18.1 Add a New Agent

```python
# 1. src/agents/my_agent.py
"""My Agent — owns the X phase."""
from __future__ import annotations

from dataclasses import dataclass

@dataclass
class MyResult:
    task_id: str
    output: dict

def do_work(task_id: str, input_data: dict) -> MyResult:
    """Pure function — testable without ADK."""
    return MyResult(task_id=task_id, output={"status": "done"})

try:
    from google.adk.agents import Agent
    my_agent = Agent(name="my_agent", model=..., tools=[do_work])
except ImportError:
    my_agent = None
```

```python
# 2. Register in src/services/specialist_registry.py
SPECIALIST_OWNERS[Phase.X] = "my_agent"

# 3. Add routing in src/agents/orchestrator.py
if phase == Phase.X:
    return await my_agent.run(context)

# 4. Write tests in tests/agents/test_my_agent.py
```

### 18.2 Add a New Quality Gate

```python
# 1. src/services/quality_gates.py
class MyGate(QualityGate):
    async def evaluate(self, context: dict) -> GateResult:
        return GateResult(
            passed=True,
            evidence={"my_check": "ok"},
        )

# 2. Register in PhaseController._get_gate_for_phase()
def _get_gate_for_phase(phase: Phase) -> list[QualityGate]:
    if phase == Phase.IMPLEMENT:
        return [LintGate(), TypeCheckGate(), MyGate()]
```

### 18.3 Add a New Tool to the Dispatcher

```python
# 1. src/tools/my_tool.py
async def my_tool(arg: str) -> dict:
    return {"result": arg}

# 2. src/main.py — register at startup
register_tool("my_tool", my_tool)

# 3. Add to TOOL_PROMPT_SUFFIX in src/planner.py
# 4. Write tests in tests/tools/test_my_tool.py
```

### 18.4 Run a Single Test

```bash
# Always use .venv python
.venv/bin/python -m pytest tests/agents/test_builder.py::test_specific_case -v
```

### 18.5 Add a Phase Transition with Gate

```python
# Using PhaseController
from src.services.phase_controller import PhaseController

controller = PhaseController(state_manager=sm)
result = controller.advance(
    work_item=item,
    target=Phase.ARCHITECT,
    reason="Requirements analyzed",
    force=False,  # run quality gates
)
# result: {"allowed": bool, "skipped": list[str], "gates_run": int}
if not result["allowed"]:
    logger.warning(f"Gates blocked transition: {result['skipped']}")
```

### 18.6 Register a Capability (MCP or internal)

```python
from src.capabilities.registry import CapabilityRegistry
from src.capabilities.service import CapabilityService

registry = CapabilityRegistry()
registry.register(
    name="my.feature",
    description="...",
    backend="local",
    handler=lambda req: {"data": "value"},
)
service = CapabilityService(registry)
# Now callable via execute_capability("my.feature", {...})
```
