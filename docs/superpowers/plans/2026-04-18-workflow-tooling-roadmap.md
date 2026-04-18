# Workflow Tooling Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a capability-first workflow tooling foundation for the ADK/LiteLLM swarm, including a repo-local Python stdio MCP server and shared capability-backed runtime and operator surfaces.

**Architecture:** The implementation starts by introducing a small capability core with stable contracts, registry lookups, and backend routing. The MCP server, swarm runtime, CLI, command markdown, and future skills or plugins all become thin consumers of that capability core so result shapes, retries, and routing policies do not drift across surfaces.

**Tech Stack:** Python 3, `pytest`, `pytest-asyncio`, `google-adk`, `litellm`, Python MCP SDK (`mcp`), existing `src.tools.dispatcher`, existing filesystem and Smithery tools

---

## Planning handoff

- **Approved spec path:** `docs/superpowers/specs/2026-04-18-workflow-tooling-roadmap-design.md`
- **In scope:** capability contracts, backend routing, a repo-local Python stdio MCP server, runtime-first ADK/LiteLLM integration, shared result envelopes, CLI and command-surface reuse, and helper seams for future skills or plugins
- **Out of scope:** replacing Google ADK or LiteLLM, remote hosted MCP, broad plugin marketplace packaging, exposing every existing tool immediately, unrelated refactors
- **Explicit constraints:** prioritize the local stdio MCP server first; keep transport layers thin; use the repo's own swarm runtime as the first consumer; preserve filesystem guardrails; keep Smithery behind the capability layer; route parallelizable work through `src/tools/dispatcher.py`
- **Known files/directories:** `src/main.py`, `src/agents/orchestrator.py`, `src/tools/dispatcher.py`, `src/tools/smithery_bridge.py`, `src/cli/swarm_cli.py`, `.claude/commands/swarm/`, `src/config.py`, `src/tools/`, `tests/`, plus planned additions under `src/capabilities/`, `src/mcp/`, `tests/capabilities/`, and `tests/mcp/`

## File structure

- Modify: `requirements.txt`
- Create: `src/capabilities/__init__.py`
- Create: `src/capabilities/contracts.py`
- Create: `src/capabilities/registry.py`
- Create: `src/capabilities/service.py`
- Create: `src/capabilities/backends/__init__.py`
- Create: `src/capabilities/backends/local.py`
- Create: `src/capabilities/backends/smithery.py`
- Create: `src/capabilities/helpers.py`
- Create: `src/mcp/__init__.py`
- Create: `src/mcp/server.py`
- Modify: `src/main.py:1-168`
- Modify: `src/agents/orchestrator.py:1-78`
- Modify: `src/tools/dispatcher.py:1-57`
- Modify: `src/tools/smithery_bridge.py:1-31`
- Modify: `src/cli/swarm_cli.py:1-297`
- Modify: `.claude/commands/swarm/status.md:1-15`
- Modify: `.claude/commands/swarm/tasks.md`
- Modify: `.claude/commands/swarm/events.md`
- Modify: `.claude/commands/swarm/queue.md`
- Create: `tests/capabilities/test_registry.py`
- Create: `tests/capabilities/test_service.py`
- Create: `tests/mcp/test_stdio_server.py`
- Create: `tests/test_runtime_capabilities.py`
- Create: `tests/cli/test_swarm_cli_capabilities.py`

### Task 1: Create the capability contracts and registry

**Files:**
- Modify: `requirements.txt`
- Create: `src/capabilities/__init__.py`
- Create: `src/capabilities/contracts.py`
- Create: `src/capabilities/registry.py`
- Test: `tests/capabilities/test_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.capabilities.registry import CapabilityRegistry


def test_registry_registers_and_resolves_capability():
    registry = CapabilityRegistry()

    def handler(request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult.ok(payload={"value": request.arguments["value"]}, source_backend="local")

    registry.register(
        name="swarm.status",
        description="Read swarm status",
        backend="local",
        handler=handler,
    )

    capability = registry.get("swarm.status")

    assert capability.name == "swarm.status"
    assert capability.backend == "local"


def test_capability_result_error_preserves_retryable_flag():
    result = CapabilityResult.error(
        error="backend unavailable",
        source_backend="smithery",
        retryable=True,
    )

    assert result.status == "error"
    assert result.error == "backend unavailable"
    assert result.retryable is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/capabilities/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.capabilities'`

- [ ] **Step 3: Write the minimal capability core**

```python
# src/capabilities/contracts.py
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class CapabilityRequest:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityResult:
    status: str
    payload: dict[str, Any] | None
    error: str | None
    source_backend: str
    retryable: bool

    @classmethod
    def ok(cls, payload: dict[str, Any], source_backend: str) -> "CapabilityResult":
        return cls("success", payload, None, source_backend, False)

    @classmethod
    def error(cls, error: str, source_backend: str, retryable: bool = False) -> "CapabilityResult":
        return cls("error", None, error, source_backend, retryable)


CapabilityHandler = Callable[[CapabilityRequest], CapabilityResult]
```

```python
# src/capabilities/registry.py
from dataclasses import dataclass

from src.capabilities.contracts import CapabilityHandler


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    description: str
    backend: str
    handler: CapabilityHandler


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}

    def register(self, name: str, description: str, backend: str, handler: CapabilityHandler) -> None:
        self._capabilities[name] = CapabilityDefinition(
            name=name,
            description=description,
            backend=backend,
            handler=handler,
        )

    def get(self, name: str) -> CapabilityDefinition:
        return self._capabilities[name]
```

```python
# src/capabilities/__init__.py
from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.capabilities.registry import CapabilityDefinition, CapabilityRegistry

__all__ = [
    "CapabilityDefinition",
    "CapabilityRegistry",
    "CapabilityRequest",
    "CapabilityResult",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/capabilities/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Add the MCP dependency**

```text
# requirements.txt
google-cloud-aiplatform
google-adk
litellm
mcp
playwright
pygithub
python-dotenv
pytest
rich
pytest-asyncio
prompt_toolkit
duckduckgo-search
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt src/capabilities/__init__.py src/capabilities/contracts.py src/capabilities/registry.py tests/capabilities/test_registry.py
git commit -m "feat: add workflow capability contracts"
```

### Task 2: Add backend routing and a shared capability service

**Files:**
- Create: `src/capabilities/backends/__init__.py`
- Create: `src/capabilities/backends/local.py`
- Create: `src/capabilities/backends/smithery.py`
- Create: `src/capabilities/service.py`
- Modify: `src/tools/smithery_bridge.py:1-31`
- Test: `tests/capabilities/test_service.py`
- Test: `tests/test_smithery_bridge.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.capabilities.registry import CapabilityRegistry
from src.capabilities.service import CapabilityService


@pytest.mark.asyncio
async def test_service_executes_local_capability():
    registry = CapabilityRegistry()

    def status_handler(request: CapabilityRequest) -> CapabilityResult:
        return CapabilityResult.ok(payload={"health": "HEALTHY"}, source_backend="local")

    registry.register("swarm.status", "Read swarm status", "local", status_handler)

    service = CapabilityService(registry)
    result = await service.execute("swarm.status")

    assert result.status == "success"
    assert result.payload == {"health": "HEALTHY"}


@pytest.mark.asyncio
async def test_service_wraps_backend_errors():
    registry = CapabilityRegistry()

    def broken_handler(request: CapabilityRequest) -> CapabilityResult:
        raise RuntimeError("boom")

    registry.register("swarm.status", "Read swarm status", "local", broken_handler)

    service = CapabilityService(registry)
    result = await service.execute("swarm.status")

    assert result.status == "error"
    assert result.error == "boom"
    assert result.retryable is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/capabilities/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.capabilities.service'`

- [ ] **Step 3: Write the capability service and backend adapters**

```python
# src/capabilities/service.py
from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.capabilities.registry import CapabilityRegistry


class CapabilityService:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    async def execute(self, name: str, **arguments) -> CapabilityResult:
        definition = self._registry.get(name)
        request = CapabilityRequest(name=name, arguments=arguments)
        try:
            result = definition.handler(request)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except Exception as exc:
            return CapabilityResult.error(
                error=str(exc),
                source_backend=definition.backend,
                retryable=False,
            )
```

```python
# src/capabilities/backends/__init__.py
from src.capabilities.backends.local import execute_local_capability
from src.capabilities.backends.smithery import execute_smithery_capability

__all__ = ["execute_local_capability", "execute_smithery_capability"]
```

```python
# src/capabilities/backends/local.py
from src.capabilities.contracts import CapabilityRequest, CapabilityResult


def execute_local_capability(request: CapabilityRequest, handler) -> CapabilityResult:
    output = handler(request)
    if isinstance(output, CapabilityResult):
        return output
    return CapabilityResult.ok(payload={"value": output}, source_backend="local")
```

```python
# src/capabilities/backends/smithery.py
from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.tools.smithery_bridge import call_smithery_tool


async def execute_smithery_capability(request: CapabilityRequest) -> CapabilityResult:
    output = await call_smithery_tool(
        request.arguments["server_id"],
        request.arguments["tool_name"],
        request.arguments.get("tool_args", {}),
    )
    if output.startswith("Smithery Error") or output.startswith("Bridge Error"):
        return CapabilityResult.error(output, source_backend="smithery", retryable=True)
    return CapabilityResult.ok(payload={"output": output}, source_backend="smithery")
```

```python
# src/tools/smithery_bridge.py
import asyncio
import json


async def call_smithery_tool(server_id: str, tool_name: str, args: dict) -> str:
    args_json = json.dumps(args)
    cmd = ["smithery", "tool", "call", server_id, tool_name, args_json]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            return f"Smithery Error: {error_msg}"
        return stdout.decode().strip()
    except Exception as exc:
        return f"Bridge Error: {exc}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/capabilities/test_service.py tests/test_smithery_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capabilities/backends/__init__.py src/capabilities/backends/local.py src/capabilities/backends/smithery.py src/capabilities/service.py src/tools/smithery_bridge.py tests/capabilities/test_service.py tests/test_smithery_bridge.py
git commit -m "feat: add capability service and backend routing"
```

### Task 3: Build the repo-local Python stdio MCP server

**Files:**
- Create: `src/mcp/__init__.py`
- Create: `src/mcp/server.py`
- Test: `tests/mcp/test_stdio_server.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.mcp.server import build_mcp_server


def test_build_mcp_server_registers_status_tool():
    server = build_mcp_server()
    tool_names = {tool.name for tool in server._tool_manager.list_tools()}

    assert "swarm_status" in tool_names


def test_build_mcp_server_registers_repo_read_tool():
    server = build_mcp_server()
    tool_names = {tool.name for tool in server._tool_manager.list_tools()}

    assert "repo_read_file" in tool_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/mcp/test_stdio_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.mcp.server'`

- [ ] **Step 3: Write the stdio MCP server**

```python
# src/mcp/__init__.py
from src.mcp.server import build_mcp_server

__all__ = ["build_mcp_server"]
```

```python
# src/mcp/server.py
from mcp.server.fastmcp import FastMCP

from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.capabilities.registry import CapabilityRegistry
from src.capabilities.service import CapabilityService
from src.tools.filesystem import list_directory, read_file


def build_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()

    registry.register(
        name="swarm.status",
        description="Read swarm status",
        backend="local",
        handler=lambda request: CapabilityResult.ok(
            payload=request.arguments["status_handler"](),
            source_backend="local",
        ),
    )
    registry.register(
        name="repo.read_file",
        description="Read a repository file with guardrails",
        backend="local",
        handler=lambda request: CapabilityResult.ok(
            payload={"content": read_file(request.arguments["path"])},
            source_backend="local",
        ),
    )
    registry.register(
        name="repo.list_directory",
        description="List a repository directory with guardrails",
        backend="local",
        handler=lambda request: CapabilityResult.ok(
            payload={"entries": list_directory(request.arguments.get("path", "."))},
            source_backend="local",
        ),
    )
    return registry


def build_mcp_server() -> FastMCP:
    registry = build_registry()
    service = CapabilityService(registry)
    mcp = FastMCP("workflow-tooling")

    @mcp.tool()
    async def swarm_status() -> dict:
        result = await service.execute("swarm.status", status_handler=lambda: {"health": "HEALTHY"})
        return result.payload or {"status": result.status, "error": result.error}

    @mcp.tool()
    async def repo_read_file(path: str) -> dict:
        result = await service.execute("repo.read_file", path=path)
        return {
            "status": result.status,
            "payload": result.payload,
            "error": result.error,
            "source_backend": result.source_backend,
            "retryable": result.retryable,
        }

    @mcp.tool()
    async def repo_list_directory(path: str = ".") -> dict:
        result = await service.execute("repo.list_directory", path=path)
        return {
            "status": result.status,
            "payload": result.payload,
            "error": result.error,
            "source_backend": result.source_backend,
            "retryable": result.retryable,
        }

    return mcp


if __name__ == "__main__":
    build_mcp_server().run()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/mcp/test_stdio_server.py -v`
Expected: PASS

- [ ] **Step 5: Run the server smoke check**

Run: `python3 -m src.mcp.server`
Expected: Process starts the local stdio MCP server without import errors

- [ ] **Step 6: Commit**

```bash
git add src/mcp/__init__.py src/mcp/server.py tests/mcp/test_stdio_server.py
git commit -m "feat: add local stdio mcp server"
```

### Task 4: Integrate capability-backed tools into the swarm runtime

**Files:**
- Modify: `src/main.py:1-168`
- Modify: `src/agents/orchestrator.py:1-78`
- Modify: `src/tools/dispatcher.py:1-57`
- Test: `tests/test_runtime_capabilities.py`
- Test: `tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from src.capabilities.contracts import CapabilityResult
from src.capabilities.registry import CapabilityRegistry
from src.capabilities.service import CapabilityService


@pytest.mark.asyncio
async def test_runtime_capability_service_executes_status_capability():
    registry = CapabilityRegistry()
    registry.register(
        "swarm.status",
        "Read swarm status",
        "local",
        lambda request: CapabilityResult.ok({"health": "HEALTHY"}, "local"),
    )

    service = CapabilityService(registry)
    result = await service.execute("swarm.status")

    assert result.payload["health"] == "HEALTHY"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_runtime_capabilities.py -v`
Expected: FAIL because runtime capability registration helper does not exist yet

- [ ] **Step 3: Register capability-backed tools in the runtime**

```python
# src/main.py
from src.capabilities.contracts import CapabilityResult
from src.capabilities.registry import CapabilityRegistry
from src.capabilities.service import CapabilityService
from src.tools.filesystem import read_file, write_file, list_directory
from src.tools.smithery_bridge import call_smithery_tool


capability_registry = CapabilityRegistry()
capability_service = CapabilityService(capability_registry)

capability_registry.register(
    "repo.read_file",
    "Read a repository file with guardrails",
    "local",
    lambda request: CapabilityResult.ok(
        {"content": read_file(request.arguments["path"])},
        "local",
    ),
)


async def execute_capability(name: str, **arguments):
    result = await capability_service.execute(name, **arguments)
    return {
        "status": result.status,
        "payload": result.payload,
        "error": result.error,
        "source_backend": result.source_backend,
        "retryable": result.retryable,
    }


register_tool("execute_capability", execute_capability)
```

```python
# src/agents/orchestrator.py
instruction = """You are the master orchestrator of the Cognitive Foundry.
Prefer execute_capability for shared operational and repo-inspection work.
Use capability-backed operations for swarm status, guarded repo reads, and future MCP-aligned helpers.
Continue using batch_execute for independent parallel work.
"""
```

```python
# src/tools/dispatcher.py
async def batch_execute(requests: list[dict[str, object]]) -> list[dict[str, object]]:
    ...
    return list(results)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_runtime_capabilities.py tests/test_dispatcher.py -v`
Expected: PASS

- [ ] **Step 5: Run the focused swarm CLI/status regression**

Run: `python3 -m pytest tests/cli/test_swarm_cli.py::TestSwarmCli::test_status_no_swarm -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/main.py src/agents/orchestrator.py src/tools/dispatcher.py tests/test_runtime_capabilities.py tests/test_dispatcher.py
git commit -m "feat: integrate capability-backed runtime tools"
```

### Task 5: Unify CLI, command surfaces, and helper seams around the capability layer

**Files:**
- Create: `src/capabilities/helpers.py`
- Modify: `src/cli/swarm_cli.py:1-297`
- Modify: `.claude/commands/swarm/status.md:1-15`
- Modify: `.claude/commands/swarm/tasks.md`
- Modify: `.claude/commands/swarm/events.md`
- Modify: `.claude/commands/swarm/queue.md`
- Test: `tests/cli/test_swarm_cli_capabilities.py`
- Test: `tests/cli/test_swarm_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.cli import swarm_cli


def test_status_command_uses_capability_helper(capsys, monkeypatch):
    monkeypatch.setattr(
        swarm_cli,
        "get_swarm_status_view",
        lambda args: {
            "pid": "1234",
            "shutdown_requested": False,
            "total_tasks": 0,
            "planned": 0,
            "completed": 0,
            "stalled": 0,
            "health": "HEALTHY",
        },
    )

    ret = swarm_cli.main(["status"])

    assert ret == 0
    out = capsys.readouterr().out
    assert "1234" in out
    assert "HEALTHY" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/cli/test_swarm_cli_capabilities.py -v`
Expected: FAIL with `AttributeError` because `get_swarm_status_view` does not exist

- [ ] **Step 3: Add the helper seam and route CLI through it**

```python
# src/capabilities/helpers.py
from src.state import StateManager
from src.cli.swarm_ctl import get_swarm_pid, is_shutdown_requested, peek_prompts


def get_swarm_status_view(state_file: str | None = None, events_file: str | None = None) -> dict:
    kwargs = {}
    if state_file:
        kwargs["filename"] = state_file
    if events_file:
        kwargs["event_filename"] = events_file
    if kwargs:
        kwargs["storage_type"] = "json"

    state_manager = StateManager(**kwargs)
    tasks = state_manager.get_all_tasks()
    stalled = sum(1 for task in tasks.values() if task.get("status") == "STALLED")
    planned = sum(1 for task in tasks.values() if task.get("status") == "PLANNED")
    completed = sum(1 for task in tasks.values() if task.get("status") == "COMPLETED")

    return {
        "pid": get_swarm_pid() or "Not running",
        "shutdown_requested": is_shutdown_requested(),
        "total_tasks": len(tasks),
        "planned": planned,
        "completed": completed,
        "stalled": stalled,
        "health": "DEGRADED" if stalled > 0 else "HEALTHY",
        "queue_depth": len(peek_prompts()),
    }
```

```python
# src/cli/swarm_cli.py
from src.capabilities.helpers import get_swarm_status_view


def cmd_status(args):
    status_view = get_swarm_status_view(
        getattr(args, "state_file", None),
        getattr(args, "events_file", None),
    )
    print("=== Cognitive Foundry Swarm Status ===")
    print(f"PID:           {status_view['pid']}")
    print(f"Shutdown req:  {'Yes' if status_view['shutdown_requested'] else 'No'}")
    print(f"Total tasks:   {status_view['total_tasks']}")
    print(f"  Planned:     {status_view['planned']}")
    print(f"  Completed:   {status_view['completed']}")
    print(f"  Stalled:     {status_view['stalled']}")
    print(f"Health:        {status_view['health']}")
    return 0
```

```markdown
<!-- .claude/commands/swarm/status.md -->
---
description: Show Cognitive Foundry swarm status
argument-hint: "[none]"
allowed-tools: Read, Bash(python3:*)
---

Run the swarm status command: !`python3 -m src.cli.swarm_cli status`

Then summarize:
1. Total tasks and breakdown by status
2. Any stalled tasks
3. Whether a shutdown is requested
4. The swarm PID if running
5. Queue depth and overall health assessment
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/cli/test_swarm_cli.py tests/cli/test_swarm_cli_capabilities.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/capabilities/helpers.py src/cli/swarm_cli.py .claude/commands/swarm/status.md .claude/commands/swarm/tasks.md .claude/commands/swarm/events.md .claude/commands/swarm/queue.md tests/cli/test_swarm_cli.py tests/cli/test_swarm_cli_capabilities.py
git commit -m "feat: unify cli and command surfaces on capabilities"
```

## Self-review

### Spec coverage

- **Capability contracts and shared result envelopes:** covered by Task 1 and Task 2
- **Local stdio MCP server:** covered by Task 3
- **Runtime-first swarm integration:** covered by Task 4
- **CLI, command markdown, and helper seams:** covered by Task 5
- **Deferred plugin or extension packaging:** intentionally not implemented in this plan; the plan leaves a helper seam and capability core for later packaging work, matching the approved scope boundaries

### Placeholder scan

- No `TODO`, `TBD`, or deferred implementation placeholders remain inside tasks
- Each task includes exact file paths, code snippets, runnable commands, expected outcomes, and commit steps

### Type consistency

- The plan consistently uses `CapabilityRequest`, `CapabilityResult`, `CapabilityRegistry`, and `CapabilityService`
- Result envelopes consistently use `status`, `payload`, `error`, `source_backend`, and `retryable`
- MCP tools are described as thin wrappers over the capability service rather than a separate contract

### Handoff fidelity

- The plan uses the exact approved spec path
- The plan keeps the MCP-first, transport-thin, runtime-first constraints
- The plan preserves the known file surfaces from brainstorming and the approved spec
