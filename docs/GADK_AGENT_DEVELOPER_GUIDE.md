# GADK Agent Developer Guide

> **For autonomous agents, sub-agents, skills, MCP servers, and plugins.**
> This guide is the canonical reference for understanding, extending, and operating GADK (Cognitive Foundry Swarm) without duplicating the existing CLAUDE.md (project management focus) or ARCHITECTURE.md (system design focus).
> Last updated: 2026-04-21

---

## 1. System Identity

**GADK** (Cognitive Foundry Swarm) is a multi-agent SDLC system built on Google ADK. It orchestrates 8 specialized agents through 6 SDLC phases to autonomously discover, plan, build, review, and govern work against target GitHub repositories.

```
Version:    0.1.0
Target:     asshat1981ar/project-chimera (Android RPG)
License:     Proprietary
Python:      3.11+
ADK:         google-adk
State:       Atomic JSON (state.json + events.jsonl)
Embedding:   OpenRouter (LiteLLM)
```

---

## 2. Agent Taxonomy

All 8 agents live in `src/agents/`. Every agent follows the **Architect pattern**: pure functions at module scope for testability, with an optional ADK `Agent` wrapper gated on a successful `google.adk` import.

```
src/agents/
├── orchestrator.py   (75 lines)  — Router/dispatcher to specialist agents
├── ideator.py        (130 lines) — PLAN phase: goal → structured tasks
├── architect.py      (186 lines) — ARCHITECT phase: ADR-style decisions
├── builder.py        (704 lines) — IMPLEMENT phase: code + PR creation
├── critic.py         (104 lines) — REVIEW phase: bounded retry code review
├── governor.py       (220 lines) — GOVERN phase: release readiness gates
├── pulse.py          (670 lines) — OPERATE phase: health monitoring + alerts
├── finops.py         (816 lines) — OPERATE phase: cost tracking + budgets
└── refactor_agent.py  (38 lines) — One-shot refactoring tasks
```

### 2.1 Agent Contract Pattern

Every agent module exposes a typed contract and a pure-tool wrapper:

```python
"""src/agents/architect.py — simplified"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── Pure tool functions (testable without ADK) ────────────────────────────────

@dataclass
class ArchitectureDecision:
    task_id: str
    decision: str
    rationale: str
    alternatives_considered: list[str]

def produce_architecture(task_id: str, requirements: dict[str, Any]) -> ArchitectureDecision:
    """Pure function: given requirements, produce an ADR."""
    return ArchitectureDecision(...)

# ── ADK wrapper (optional import) ─────────────────────────────────────────────

try:
    from google.adk.agents import Agent
    architect_agent = Agent(
        name="architect",
        model="openrouter/google/gemini-2.5-flash",
        instruction="You produce architecture decisions...",
        tools=[produce_architecture],
    )
except ImportError:
    architect_agent = None
```

**Rule:** All business logic MUST be in pure module-level functions. The ADK `Agent` wrapper is only for the ADK runtime — tests and tools import the pure functions directly.

### 2.2 Agent Hierarchy

```
Orchestrator (75L)
├── Ideator (PLAN)
├── Architect (ARCHITECT)
├── Builder (IMPLEMENT)
├── Critic (REVIEW)          ← bounded retry cycles
├── Governor (GOVERN)
├── Pulse (OPERATE)          ← health + metrics
└── FinOps (OPERATE)         ← costs + budgets
```

### 2.3 How the Orchestrator Dispatches

`orchestrator.py` is the router. It reads the current `phase` from `StateManager` and dispatches to the appropriate specialist:

```python
# src/agents/orchestrator.py (75 lines)
# Key dispatch logic pattern:
async def route_to_phase(phase: Phase, context: dict) -> dict:
    if phase == Phase.PLAN:
        return await ideator_agent.run(context)
    elif phase == Phase.ARCHITECT:
        return await architect_agent.run(context)
    # ... etc
```

---

## 3. Six-Phase SDLC

Phases are defined in `src/services/sdlc_phase.py` (128 lines):

```
PLAN → ARCHITECT → IMPLEMENT → REVIEW → GOVERN → OPERATE
       ↑__________________________↓ (rework edge on critic rejection)
```

| Phase | Owner | Key Method | Exit Gate |
|-------|-------|------------|-----------|
| PLAN | Ideator | `plan_from_goal()` | At least 1 task produced |
| ARCHITECT | Architect | `produce_architecture()` | ADR written |
| IMPLEMENT | Builder | `implement_task()` | Code + PR created |
| REVIEW | Critic | `review_code()` | 1 APPROVE or N retries exhausted |
| GOVERN | Governor | `check_release_readiness()` | All quality gates pass |
| OPERATE | Pulse/FinOps | `run_health_check()` | Health report generated |

### 3.1 Phase Transitions

**Never mutate `WorkItem.phase` directly.** Always use `PhaseController`:

```python
from src.services.phase_controller import PhaseController
from src.services.sdlc_phase import Phase, WorkItem

controller = PhaseController()
result = await controller.advance(
    work_item,
    target=Phase.ARCHITECT,
    reason="Architecture complete"
)
```

`PhaseController` (`src/services/phase_controller.py`) evaluates quality gates before allowing transitions.

---

## 4. Core Services

### 4.1 State Management (`src/state.py`)

Uses atomic JSON writes (`tempfile` + `os.replace`). Never write `state.json` directly.

```python
from src.state import StateManager

state = StateManager()
state.update_work_item(task_id="task-123", phase=Phase.PLAN)
work_items = state.list_work_items()
```

State file: `state.json` (primary), `state.json.bak` (backup).

### 4.2 Task Queue (`src/services/task_queue.py` — 825 lines)

The central inbox for all work items. Key operations:

```python
from src.services.task_queue import TaskQueue

queue = TaskQueue()
queue.enqueue({"task_id": "t-1", "phase": "PLAN", "priority": 1})
item = queue.dequeue()         # blocking pop
queue.requeue(item)            # push back on failure
queue.complete(task_id)        # mark done
queue.get_gaps()               # for self-prompt gap mining
```

### 4.3 Retrieval Context (`src/services/retrieval_context.py` — 688 lines)

Longest service in the codebase. Provides context-aware planning support by retrieving relevant history, past decisions, and similar tasks. Has multiple fallback paths (vector → keyword → sqlite-vec).

```python
from src.services.retrieval_context import RetrievalContext

ctx = RetrievalContext()
context = await ctx.get_context(task_id="t-1", query="authentication")
```

**Note:** This module has had multiple fixes for retrieval logic instabilities — expect further refactoring per the v2 autonomy overhaul plan.

### 4.4 Self-Prompt Engine (`src/services/self_prompt.py` — 337 lines)

Gap-driven autonomous prompt generation. Synthesizes work from queue gaps and generates new tasks:

```python
from src.services.self_prompt import SelfPromptEngine

engine = SelfPromptEngine()
prompts = await engine.synthesize_and_queue(write=True)  # write to prompt queue
```

Dry run first: `python3 -m src.cli.swarm_cli self-prompt --dry-run`

### 4.5 Quality Gates (`src/services/quality_gates.py` — 228 lines)

Pluggable gate system. Each gate is a class extending `QualityGate`:

```python
from src.services.quality_gates import QualityGate, GateResult

class MyGate(QualityGate):
    async def evaluate(self, context: dict) -> GateResult:
        return GateResult(passed=True, evidence={"key": "value"})
```

Gates are registered in `PhaseController._get_gate_for_phase()`.

### 4.6 Specialist Registry (`src/services/specialist_registry.py` — 61 lines)

Maps phases to agent owners:

```python
from src.services.specialist_registry import SpecialistRegistry

registry = SpecialistRegistry()
owner = registry.get_owner(Phase.IMPLEMENT)  # returns "builder"
```

---

## 5. Tools (`src/tools/`)

```
src/tools/
├── __init__.py
├── dispatcher.py        (185 lines) — routes tool calls to implementations
├── github_tool.py       (380 lines) — GitHub API: PRs, issues, reviews
├── content_guards.py    (199 lines) — Output safety + content filtering
├── filesystem.py        (192 lines) — File read/write within allowed dirs
├── sandbox_executor.py  (56 lines)  — Subprocess with sandbox flag
├── scraper.py           (32 lines)  — Web scraping (minimal)
├── smithery_bridge.py   (50 lines)  — Smithery marketplace tool bridge
├── toolbank_app.py      (66 lines)  — Toolbank MCP integration
└── web_search.py        (59 lines)  — Web search capability
```

### 5.1 Adding a New Tool

1. Create `src/tools/my_tool.py` with pure functions
2. Register in `src/tools/dispatcher.py`
3. Export from `src/tools/__init__.py`
4. Write tests in `tests/tools/test_my_tool.py`

### 5.2 GitHub Tool Pattern

```python
from src.tools.github_tool import GitHubTool

gh = GitHubTool()
await gh.create_pull_request(title="...", body="...", head="branch", base="main")
await gh.review_pull_request(pr_number=123, body="...", event="APPROVE")
```

---

## 6. MCP Integration (`src/mcp/`)

### 6.1 MCP Server (`src/mcp/server.py` — 114 lines)

Provides MCP tools to external clients. Key tools:
- `swarm.status` — health check
- `repo.search` — search repository
- `repo.analyze` — analyze code

Run: `python3 -m src.mcp.server`

### 6.2 SDLC Client (`src/mcp/sdlc_client.py` — 173 lines)

Internal MCP client that the swarm's agents use to call the MCP server. Governs gate verdict forwarding when `SDLC_MCP_ENABLED=true`.

---

## 7. Orchestration (`src/orchestration/`)

### 7.1 Graph Orchestrator (`src/orchestration/graph_orchestrator.py` — 16 lines)

Minimal stub. Per the v2 autonomy overhaul plan, this is being expanded to replace `PhaseController` with a LangGraph workflow skeleton supporting reflection nodes and dynamic routing.

```python
from src.orchestration.graph_orchestrator import GraphOrchestrator

orchestrator = GraphOrchestrator()
graph = orchestrator.build_workflow()
```

### 7.2 Reflection Node (`src/orchestration/reflection_node.py` — 24 lines)

Self-correction loop for autonomous adjustment. Used by the graph orchestrator to evaluate "was the last action correct?" and route to self-correct if needed.

---

## 8. Capabilities System (`src/capabilities/`)

```
src/capabilities/
├── contracts.py   — capability agreement definitions
├── helpers.py      — shared helpers
├── registry.py    — capability registration
└── service.py     — capability service
```

Used to define what agents can do and negotiate capability agreements between agents.

---

## 9. CLI Commands (`src/cli/`)

| Command | File | Purpose |
|---------|------|---------|
| `python3 -m src.main` | `src/main.py` | Start swarm runtime |
| `python3 -m src.cli.swarm_cli status` | `swarm_cli.py` | Health check |
| `python3 -m src.cli.swarm_cli tasks` | `swarm_cli.py` | List work items |
| `python3 -m src.cli.swarm_cli queue` | `swarm_cli.py` | Inspect prompt queue |
| `python3 -m src.cli.swarm_cli phase status <id>` | `swarm_cli.py` | Phase status |
| `python3 -m src.cli.swarm_cli phase advance <id> <PHASE>` | `swarm_cli.py` | Advance phase |
| `python3 -m src.cli.swarm_cli self-prompt --dry-run` | `swarm_cli.py` | Self-prompt synthesis |
| `python3 -m src.mcp.server` | `src/mcp/server.py` | Start MCP server |

---

## 10. Observability (`src/observability/`)

```
src/observability/
├── cost_tracker.py       — token + cost aggregation (litellm)
├── litellm_callbacks.py — LLM call logging
├── logger.py             — structured logging (JSON to stdout)
├── metrics.py            — metrics registry
├── model_performance.py  — per-model latency/accuracy tracking
└── adk_callbacks.py     — ADK runtime callbacks
```

Structured logs go to stdout in JSON format. Use `get_logger(__name__)` — never `print()` in library code.

---

## 11. Testing (`tests/`)

```
tests/
├── conftest.py           — pytest fixtures + mock_llm
├── agents/
│   ├── test_ideator.py
│   ├── test_architect.py
│   ├── test_builder.py
│   └── ...
├── services/
│   ├── test_phase_controller.py
│   ├── test_quality_gates.py
│   └── ...
└── tools/
    ├── test_github_tool.py
    └── ...
```

### 11.1 Test Commands

```bash
# Always use .venv python
.venv/bin/python -m pytest -q                    # Full suite
.venv/bin/python -m pytest tests/services -q     # Service tests
.venv/bin/python -m pytest -k test_name -v       # Specific test

# Quality gates (required before commit)
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
```

### 11.2 Test Mode

```python
from src.config import Config

if Config.TEST_MODE:
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
    from src.testing.github_mocks import MockGitHubTool as GitHubTool
else:
    from google.adk.models.lite_llm import LiteLlm
    from src.tools.github_tool import GitHubTool
```

---

## 12. Configuration (`src/config.py`)

All feature flags live in `Settings` (Pydantic `BaseSettings`). Key flags:

| Variable | Default | Purpose |
|----------|---------|---------|
| `TEST_MODE` | `false` | Use mocks instead of real LLM/GitHub |
| `SELF_PROMPT_ENABLED` | `false` | Enable gap-driven auto-prompt |
| `SDLC_MCP_ENABLED` | `false` | Forward gate verdicts to external MCP |
| `RETRIEVAL_BACKEND` | `keyword` | `vector` for sqlite-vec |
| `GRAPH_MODE_ENABLED` | `false` | Use graph orchestrator (v2) |
| `BUDGET_USD` | `50.0` | Monthly budget |
| `GITHUB_TOKEN` | — | GitHub API token |
| `OPENROUTER_API_KEY` | — | LLM API key |
| `REPO_NAME` | `project-chimera` | Target repo |

---

## 13. Key Entry Points for Extension

### 13.1 Adding a New Agent

1. Create `src/agents/<name>.py` following the Architect pattern (pure functions + optional ADK wrapper)
2. Register phase ownership in `src/services/specialist_registry.py`
3. Add to `Orchestrator` routing in `src/agents/orchestrator.py`
4. Write tests in `tests/agents/test_<name>.py`

### 13.2 Adding a New Quality Gate

1. Extend `QualityGate` ABC in `src/services/quality_gates.py`
2. Register in `PhaseController._get_gate_for_phase()`
3. Add gate-specific config to `Settings` in `src/config.py`

### 13.3 Adding a New Tool

1. Implement in `src/tools/<name>.py`
2. Register in `src/tools/dispatcher.py`
3. Export from `src/tools/__init__.py`
4. Add capability registration if shared across agents

### 13.4 Adding a New MCP Tool

1. Add tool function to `src/mcp/server.py`
2. Use `mcp_server` decorator pattern if needed
3. Document in `docs/API_REFERENCE.md`

---

## 14. Directory Layout

```
/home/westonaAaron675/gadk/          # Project root (note capital A)
├── src/
│   ├── agents/                     # 8 ADK agents
│   ├── autonomous_sdlc.py           # Main autonomous loop
│   ├── capabilities/                # Agent capability contracts
│   ├── cli/                         # CLI commands (swarm_cli, swarm_ctl, dashboard)
│   ├── config.py                    # Settings (Pydantic BaseSettings)
│   ├── exceptions.py                # Custom exceptions
│   ├── main.py                      # Entry point
│   ├── mcp/                         # MCP server + client
│   │   ├── server.py               # MCP tools (swarm.status, repo.*)
│   │   └── sdlc_client.py          # Internal MCP client
│   ├── observability/               # Logging, metrics, cost tracking
│   ├── orchestration/               # Graph orchestrator + reflection node
│   │   ├── graph_orchestrator.py   # LangGraph workflow (v2 stub)
│   │   └── reflection_node.py       # Self-correction loop
│   ├── planner.py                   # Legacy planner (pre-graph)
│   ├── services/                    # 16 services (phase, quality, retrieval, etc.)
│   ├── state.py                     # StateManager (atomic JSON)
│   ├── staged_agents/               # Work-in-progress agent specs
│   ├── testing/                     # MockLLM, GitHub mocks, test tools
│   └── tools/                       # 9 tools (GitHub, filesystem, dispatcher, etc.)
├── tests/                           # Pytest test suite
├── docs/                            # Architecture, API, deployment docs
└── .env                             # Environment variables (not committed)
```

---

## 15. Important Conventions

### 15.1 Imports
```python
from __future__ import annotations  # Always first
import os                           # Stdlib
from typing import Any              # Typing
from pydantic import BaseModel     # Third-party
from src.config import Config       # Local (always src. prefix)
```

### 15.2 Type Hints
- Required for all new code in Phase 1+ modules
- Use `X | None` instead of `Optional[X]`
- Use built-in generics: `list[str]`, `dict[str, Any]`

### 15.3 Logging
```python
from src.observability.logger import get_logger
logger = get_logger(__name__)
logger.info("event_name", extra={"key": "value"})
# Never print() in library code
```

### 15.4 Python Version
Target Python 3.11+. No `from __future__ import annotations` hackery needed for type hints — 3.11+ handles it natively, but `from __future__ import annotations` is still included for forward compatibility.

---

## 16. Critical Project-Specific Notes

### 16.1 `.venv/bin/python` is Mandatory
The system Python (`python3`) is missing dependencies (litellm, langgraph, etc.). **Always use `.venv/bin/python`** for pytest, mypy, ruff, and any test/build commands. This is not a project bug — it's an environmental constraint on this machine.

```bash
# Wrong (missing dependencies)
python3 -m pytest -q

# Correct (uses venv with all deps)
.venv/bin/python -m pytest -q
```

### 16.2 Directory Path Difference
`~/gadk` → `/home/westonaAaron675/gadk` (capital A in "Aaron")
The filesystem MCP uses `/home/westonaAaron675/gadk/1` (lowercase `aaron`) which is a DIFFERENT directory from `/home/westonaAaron675/gadk` (capital A).
- **GADK project root:** `/home/westonaAaron675/gadk/`
- **Toolbank MCP project:** `/home/westonaAaron675/gadk/1/`

### 16.3 Merge + Catch-up Pattern
When syncing with remote main:
1. Commit local changes first
2. `git merge origin/main --no-ff`
3. Resolve conflicts with `patch` tool
4. Run `ruff check --fix --unsafe-fixes && ruff format --check && pytest -q`
5. Update (do not revert) failing tests when upstream error-handling or fallback logic changed
6. Push

Common issues after merge: duplicate fallback calls, stale metric files, tests expecting old exception messages.

### 16.4 ADK Import Gating
Never `import google.adk` at module level. Always gate:
```python
try:
    from google.adk.agents import Agent
except ImportError:
    Agent = None  # or skip ADK-specific code
```

### 16.5 State is Not Multi-Process Safe
`StateManager` uses advisory locking. For concurrent multi-process access, use `fcntl.flock` or switch to SQLite. Current design assumes single-process ADK runtime.

---

## 17. v2 Autonomy Overhaul (In Progress)

Per `docs/plans/2026-04-21-gadk-v2-autonomy-overhaul.md`, the following replacements are planned:

| Old | Replacement | Status |
|-----|-------------|--------|
| `PhaseController` + `sdlc_phase` | `GraphOrchestrator` (LangGraph) | Stub (16L) |
| `SelfPromptEngine` | Reflection + Self-Correction Node | Not started |
| `RetrievalContext` | Unified MemoryGraph (vector + semantic) | Not started |
| `StateManager` | Persistent actor-like memory | Not started |

This guide should be updated as each module is replaced.

---

## 18. Troubleshooting Quick Reference

| Problem | Solution |
|---------|---------|
| `ImportError: No module named 'google.adk'` | Use `.venv/bin/python`, not system python3 |
| `ModuleNotFoundError: No module named 'src'` | Run from project root `/home/westonaAaron675/gadk/` |
| Collection errors in pytest | Ensure `.venv/bin/python -m pytest` (not `python3`) |
| State corruption | Check `state.json.bak`, events are append-only in `events.jsonl` |
| Phase transition failures | Check `events.jsonl` for `phase.transition` events with failure reasons |
| MCP tools not found | Restart Hermes after config changes |

---

## 19. External Integrations

### 19.1 Smithery Marketplace
```python
from src.tools.smithery_bridge import call_smithery_tool
result = await call_smithery_tool("tool_name", {"arg": "value"})
```

### 19.2 Toolbank MCP (Separate Project)
Located at `/home/westonaAaron675/gadk/1/`. Integration via `src/tools/toolbank_app.py`:
```python
from src.tools.toolbank_app import ToolbankApp
tb = ToolbankApp()
results = await tb.search_tools("stripe payment")
```

### 19.3 GitHub
```python
from src.tools.github_tool import GitHubTool
gh = GitHubTool()
```

### 19.4 OpenRouter LLM
Configured via `OPENROUTER_API_KEY` in `.env`. Routed through `src/services/model_router.py`.
