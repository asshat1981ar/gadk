# GADK — Cognitive Foundry Swarm: Claude Development Guide

> **For Claude Code agents working on the GADK repository**
> Last updated: 2026-04-20

## Project Identity

**GADK** (Game Agent Development Kit / Cognitive Foundry Swarm) is a multi-agent SDLC system built on Google ADK. It orchestrates 8 specialized agents through a 6-phase software development lifecycle to autonomously discover, plan, build, review, and govern work against target repositories via GitHub.

**Current Version:** 0.1.0  
**Target Repository:** project-chimera (Android RPG game)  
**License:** Proprietary

---

## Quick Reference

### Entry Points
```python
# Start swarm runtime
python3 -m src.main

# CLI operations
python3 -m src.cli.swarm_cli status    # Health check
python3 -m src.cli.swarm_cli tasks     # List tasks
python3 -m src.cli.swarm_cli queue     # Inspect prompt queue

# Phase operations
python3 -m src.cli.swarm_cli phase status <id>
python3 -m src.cli.swarm_cli phase advance <id> <PHASE>

# Self-prompt (dry-run first)
python3 -m src.cli.swarm_cli self-prompt --dry-run
```

### Quality Gates (Required Before Commit)
```bash
ruff check src tests                 # Lint
ruff format --check src tests        # Format check
pytest -q                            # Tests
mypy src                             # Type check
```

---

## Architecture Overview

### Six-Phase SDLC
```
PLAN → ARCHITECT → IMPLEMENT → REVIEW → GOVERN → OPERATE
       ↑__________________________↓ (rework edge)
```

| Phase | Owner | Purpose |
|-------|-------|---------|
| PLAN | Ideator | Create structured tasks from user goals |
| ARCHITECT | Architect | Produce ADR-style architecture decisions |
| IMPLEMENT | Builder | Write code and create PRs |
| REVIEW | Critic | Code review with bounded retry cycles |
| GOVERN | Governor | Release readiness checks |
| OPERATE | Pulse/FinOps | Monitor health and costs |

### Agent Hierarchy
```
Orchestrator (Router)
├── Ideator (PLAN)
├── Architect (ARCHITECT)
├── Builder (IMPLEMENT)
├── Critic (REVIEW)
├── Governor (GOVERN)
├── Pulse (OPERATE)
└── FinOps (OPERATE)
```

### Key Services
- **PhaseController** (`src/services/phase_controller.py`) — Evaluates quality gates, manages transitions
- **QualityGates** (`src/services/quality_gates.py`) — Pluggable gate system (lint, typecheck, security, coverage, review)
- **StateManager** (`src/state.py`) — Atomic JSON persistence with advisory locking
- **SelfPrompt** (`src/services/self_prompt.py`) — Gap-driven autonomous prompt generation
- **RetrievalContext** (`src/services/retrieval_context.py`) — Context-aware planning support

---

## Development Patterns

### Agent Implementation Pattern
All agents follow the Architect/Governor pattern for testability:

```python
"""Module docstring explaining purpose."""
from __future__ import annotations

from src.config import Config

if Config.TEST_MODE:
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
else:
    from google.adk.models.lite_llm import LiteLlm

# Pure tool functions (testable without ADK)
def pure_tool_function(arg: str) -> dict:
    """Validate and return serializable payload."""
    return {"status": "ok", "result": arg}

# ADK wrapper (conditional import)
try:
    from google.adk.agents import Agent

    agent = Agent(
        name="AgentName",
        model=tool_model,
        instruction="...",
        tools=[pure_tool_function],
    )
except ImportError:
    agent = None
```

### Phase Transition Pattern
Never mutate `WorkItem.phase` directly. Always use PhaseController:

```python
from src.services.phase_controller import PhaseController
from src.services.sdlc_phase import Phase, WorkItem

controller = PhaseController()
work_item = WorkItem(id="task-123", phase=Phase.PLAN)

# Advance with gate evaluation
result = await controller.advance(
    work_item,
    target=Phase.ARCHITECT,
    reason="Architecture complete"
)
```

### Adding New Quality Gates
```python
from src.services.quality_gates import QualityGate, GateResult

class CustomGate(QualityGate):
    async def evaluate(self, context: dict) -> GateResult:
        # Implementation
        return GateResult(passed=True, evidence={"key": "value"})
```

---

## Code Standards

### Style
- **Line length:** 100 characters
- **Quotes:** Double
- **Target:** Python 3.11+
- **Formatter:** ruff (v0.5.7 pinned)
- **Type checker:** mypy (strict for Phase 1+ modules)

### Imports
```python
from __future__ import annotations  # Always first

import os                           # Stdlib
from typing import Any              # Third-party

from pydantic import BaseModel      # Third-party

from src.config import Config       # Local (always use src. prefix)
```

### Type Hints
- Required for all new code in Phase 1+ modules
- Use `X | None` instead of `Optional[X]`
- Use built-in generics: `list[str]`, `dict[str, Any]`
- Strict typing for: `sdlc_phase.py`, `quality_gates.py`, `phase_controller.py`

### Logging
```python
from src.observability.logger import get_logger

logger = get_logger(__name__)
logger.info("event_name", extra={"key": "value"})
```

**Never use `print()` in library code.** CLI commands are the exception.

---

## Testing Strategy

### Test Mode
```python
from src.config import Config

if Config.TEST_MODE:
    # Use mocks
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
    from src.testing.github_mocks import MockGitHubTool as GitHubTool
else:
    # Use real implementations
    from google.adk.models.lite_llm import LiteLlm
    from src.tools.github_tool import GitHubTool
```

### Test Commands
```bash
pytest -q                          # Full suite
pytest tests/services -q           # Service tests
pytest -k test_name -v             # Specific test
```

### Coverage
Current threshold: 0% (Phase 0)  
Target: 65% (Phase 5)

---

## Configuration

### Environment Variables (`.env`)
```bash
OPENROUTER_API_KEY=your_key
GITHUB_TOKEN=your_token
REPO_NAME=project-chimera

# Optional flags
TEST_MODE=false
SELF_PROMPT_ENABLED=false
SDLC_MCP_ENABLED=false
RETRIEVAL_BACKEND=keyword  # or "vector" for sqlite-vec
```

### Config Gating
All feature flags live in `src/config.py::Settings`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    feature_enabled: bool = False  # Default off
    max_retries: int = 3
```

---

## State Management

### Persistence Model
| File | Purpose | Access Pattern |
|------|---------|----------------|
| `state.json` | Task state | Atomic JSON writes |
| `events.jsonl` | Event log | Advisory-locked appends |
| `sessions.db` | Session data | SQLite |
| `prompt_queue.jsonl` | Pending prompts | Line-appended JSON |

### Atomic Writes
`StateManager` uses `tempfile` + `os.replace` for safe concurrent writes.

### Shutdown Signal
Create `.swarm_shutdown` in working directory for graceful termination.

---

## Common Tasks

### Adding a New Agent
1. Create `src/agents/<name>.py` following the Architect pattern
2. Register phase ownership in `src/services/specialist_registry.py`
3. Add to Orchestrator's `sub_agents` list
4. Write tests in `tests/agents/test_<name>.py`

### Adding a New Tool
1. Implement in `src/tools/<name>.py`
2. Add capability registration if shared
3. Register in `src/tools/dispatcher.py` if needed
4. Export from `src/tools/__init__.py`

### Adding a New Quality Gate
1. Extend `QualityGate` ABC in `src/services/quality_gates.py`
2. Register in `PhaseController._get_gate_for_phase()`
3. Add gate-specific config to `Settings`

### Triggering Self-Prompt
```python
from src.services.self_prompt import SelfPromptEngine

engine = SelfPromptEngine()
await engine.synthesize_and_queue()  # Dry run
await engine.synthesize_and_queue(write=True)  # Write to queue
```

---

## MCP Integration

### MCP Server (Built-in)
```python
# src/mcp/server.py
# Provides: swarm.status, repo.* tools
# Run: python3 -m src.mcp.server
```

### External SDLC MCP
Enable with `SDLC_MCP_ENABLED=true` in `.env`. Governor forwards gate verdicts to external server.

---

## External Tooling

### Smithery Marketplace
```python
from src.tools.smithery_bridge import call_smithery_tool

result = await call_smithery_tool("tool_name", {"arg": "value"})
```

### GitHub Operations
```python
from src.tools.github_tool import GitHubTool

gh = GitHubTool()
await gh.create_pull_request(title="...", body="...", head="branch")
await gh.review_pull_request(pr_number=123, body="...", event="APPROVE")
```

---

## Documentation

### Specs
Design specs live in `docs/superpowers/specs/YYYY-MM-DD-<name>-design.md`

### Plans
Implementation plans in `docs/superpowers/plans/YYYY-MM-DD-<name>.md`

### ADRs
Architecture Decision Records in `docs/architecture/`

---

## Troubleshooting

### Import Errors
Ensure `src.` prefix is used for all local imports.

### ADK Not Found
Modules should be importable without `google-adk`. Use `Config.TEST_MODE` gating.

### State Corruption
Check `state.json.bak` for recovery. Events are append-only in `events.jsonl`.

### Phase Transition Failures
Check `events.jsonl` for `phase.transition` events with failure reasons.

---

## Philosophy

1. **Agent-First:** Every service supports the agent swarm
2. **Phase-Gated:** Work flows through explicit, validated transitions
3. **Observable:** Structured logging, metrics, cost tracking throughout
4. **Testable:** All modules importable without ADK
5. **Bounded:** Retry cycles are bounded, resources are capped
6. **Transparent:** Events and state are human-readable

---

## References

- Main: `src/main.py`
- Config: `src/config.py`
- SDLC: `src/services/sdlc_phase.py`
- Gates: `src/services/quality_gates.py`
- Agents: `src/agents/`
- Tools: `src/tools/`
- README: `README.md`
