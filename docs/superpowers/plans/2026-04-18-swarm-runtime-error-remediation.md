# Swarm Runtime Error Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the current autonomous swarm runtime failures by aligning the remote-repository tool surface, routing self-prompt execution through the repo's robust planner path, and adding regression coverage for the confirmed failure modes.

**Architecture:** The confirmed root causes are a tool-surface mismatch in the ADK agent instructions and an unreliable native ADK function-calling path for `elephant-alpha` on OpenRouter. The fix should keep ADK for agent composition, but move autonomous self-prompt tool execution onto the existing `src.planner.run_planner(...)` path that already repairs malformed JSON and executes tool calls explicitly.

**Tech Stack:** Python 3.11, Google ADK, LiteLLM/OpenRouter, `json-repair`, `pytest`, `pytest-asyncio`

---

**Planning handoff**

- **Approved spec path:** none for this debugging task; this plan is derived from confirmed runtime evidence in `swarm_self_prompt.log`
- **In scope:** the autonomous/self-prompt runtime path in `src/main.py`, orchestrator/ideator instruction surfaces, remote repo exploration tool usage, and regression tests for the confirmed runtime failures
- **Out of scope:** redesigning all agents, changing the target repo (`project-chimera`), or replacing ADK as the top-level runtime
- **Known files/directories:** `src/main.py`, `src/planner.py`, `src/agents/orchestrator.py`, `src/agents/ideator.py`, `src/tools/github_tool.py`, `src/tools/dispatcher.py`, `src/testing/mock_llm.py`, `tests/test_runtime_capabilities.py`, `tests/test_sub_agents.py`

### Task 1: Add regression coverage for the confirmed runtime failure modes

**Files:**
- Create: `tests/runtime/test_autonomous_runtime.py`
- Test: `tests/runtime/test_autonomous_runtime.py`

- [ ] **Step 1: Write the failing tests**

```python
from src.agents.orchestrator import orchestrator_agent
from src.main import _build_autonomous_prompt
from src.services.runtime_strategy import should_use_planner_for_autonomous_run


def test_autonomous_runtime_uses_planner_for_elephant_openrouter():
    assert should_use_planner_for_autonomous_run("openrouter/elephant-alpha") is True


def test_orchestrator_instruction_mentions_remote_repo_tools():
    instruction = orchestrator_agent.instruction
    assert "read_repo_file" in instruction
    assert "list_repo_contents" in instruction


def test_autonomous_prompt_uses_registered_remote_repo_tools():
    prompt = _build_autonomous_prompt("project-chimera")
    assert "list_repo_contents" in prompt
    assert "read_repo_file" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/runtime/test_autonomous_runtime.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing-symbol assertions for `should_use_planner_for_autonomous_run` / `_build_autonomous_prompt`

- [ ] **Step 3: Write minimal implementation scaffolding**

```python
# src/services/runtime_strategy.py
def should_use_planner_for_autonomous_run(model_name: str) -> bool:
    return model_name.startswith("openrouter/elephant")


# src/main.py
def _build_autonomous_prompt(repo_name: str) -> str:
    return (
        f"First, use 'list_repo_contents' to explore the '{repo_name}' repository. "
        "Read key files using 'read_repo_file' and then create structured tasks."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/runtime/test_autonomous_runtime.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/runtime/test_autonomous_runtime.py src/main.py src/services/runtime_strategy.py
git commit -m "test: add autonomous runtime regression coverage"
```

### Task 2: Route autonomous self-prompt execution through the planner path

**Files:**
- Create: `src/services/runtime_strategy.py`
- Modify: `src/main.py`
- Test: `tests/runtime/test_autonomous_runtime.py`

- [ ] **Step 1: Write the failing test for planner routing**

```python
import pytest

import src.main as main_module


@pytest.mark.asyncio
async def test_process_prompt_uses_planner_for_autonomous_runs(monkeypatch):
    calls = []

    async def fake_run_planner(*, user_prompt: str, system_prompt: str, max_iterations: int):
        calls.append((user_prompt, system_prompt, max_iterations))
        return "DONE"

    monkeypatch.setattr(main_module, "run_planner", fake_run_planner)

    await main_module._run_autonomous_prompt_with_tools("prompt text")

    assert calls == [("prompt text", main_module.AUTONOMOUS_SYSTEM_PROMPT, 8)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/runtime/test_autonomous_runtime.py::test_process_prompt_uses_planner_for_autonomous_runs -q`
Expected: FAIL with `AttributeError` because `_run_autonomous_prompt_with_tools` and `AUTONOMOUS_SYSTEM_PROMPT` do not exist yet

- [ ] **Step 3: Write minimal planner-backed runtime implementation**

```python
# src/main.py
from src.planner import run_planner

AUTONOMOUS_SYSTEM_PROMPT = (
    "You are the Cognitive Foundry autonomous runtime. "
    "Use registered tools exactly as named. "
    "For remote GitHub repo exploration, use read_repo_file and list_repo_contents."
)


async def _run_autonomous_prompt_with_tools(user_prompt: str) -> str:
    return await run_planner(
        user_prompt=user_prompt,
        system_prompt=AUTONOMOUS_SYSTEM_PROMPT,
        max_iterations=8,
    )
```

- [ ] **Step 4: Wire `run_swarm_loop()` to the planner-backed path**

```python
# src/main.py
async def run_swarm_loop(session_service, session, runner) -> None:
    initial_query = _build_autonomous_prompt("project-chimera")
    response = await _run_autonomous_prompt_with_tools(initial_query)
    print(f"Swarm: {response}")
    logger.info(f"Swarm response: {response}", extra={"session_id": session.id})
    ...
```

- [ ] **Step 5: Run focused tests**

Run: `./venv/bin/python -m pytest tests/runtime/test_autonomous_runtime.py tests/test_runtime_capabilities.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/main.py src/services/runtime_strategy.py tests/runtime/test_autonomous_runtime.py
git commit -m "feat: route autonomous runtime through planner"
```

### Task 3: Align orchestrator and ideator instructions with the actual remote repo tool surface

**Files:**
- Modify: `src/agents/orchestrator.py`
- Modify: `src/agents/ideator.py`
- Test: `tests/runtime/test_autonomous_runtime.py`

- [ ] **Step 1: Write the failing instruction-surface test**

```python
from src.agents.ideator import ideator_agent
from src.agents.orchestrator import orchestrator_agent


def test_instruction_surface_uses_remote_repo_tools_not_fake_capabilities():
    orchestrator_text = orchestrator_agent.instruction
    ideator_text = ideator_agent.instruction

    assert "read_repo_file" in orchestrator_text
    assert "list_repo_contents" in orchestrator_text
    assert "read_repo_file" in ideator_text
    assert "list_repo_contents" in ideator_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/runtime/test_autonomous_runtime.py::test_instruction_surface_uses_remote_repo_tools_not_fake_capabilities -q`
Expected: FAIL because the orchestrator instruction currently emphasizes `execute_capability` and does not teach the remote GitHub tool names clearly enough

- [ ] **Step 3: Update the instructions minimally**

```python
# src/agents/orchestrator.py
instruction = """You are the master orchestrator of the Cognitive Foundry.
For remote GitHub repository exploration, use read_repo_file and list_repo_contents directly.
Reserve execute_capability for shared local runtime capabilities like swarm.status, repo.read_file, and repo.list_directory.
Use retrieve_planning_context only for specs, plans, and history in this repository.
"""


# src/agents/ideator.py
instruction = """You are the Ideator of the Cognitive Foundry.
When analyzing a remote GitHub repository, use read_repo_file and list_repo_contents.
Do not treat list_repo_contents as a capability name.
Use create_structured_task only after you have concrete repository evidence.
"""
```

- [ ] **Step 4: Run tests**

Run: `./venv/bin/python -m pytest tests/runtime/test_autonomous_runtime.py tests/test_sub_agents.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/orchestrator.py src/agents/ideator.py tests/runtime/test_autonomous_runtime.py
git commit -m "fix: align swarm instructions with remote repo tools"
```

### Task 4: Add a bounded fallback for malformed ADK tool-call JSON during runtime execution

**Files:**
- Modify: `src/main.py`
- Modify: `src/observability/logger.py`
- Test: `tests/runtime/test_autonomous_runtime.py`

- [ ] **Step 1: Write the failing fallback test**

```python
import json
import pytest

import src.main as main_module


@pytest.mark.asyncio
async def test_process_prompt_falls_back_on_tool_call_json_decode_error(monkeypatch):
    class BrokenRunner:
        def run_async(self, **kwargs):
            async def _events():
                raise json.JSONDecodeError("bad tool call", "{", 1)
                yield
            return _events()

    fallback_calls = []

    async def fake_run_planner(*, user_prompt: str, system_prompt: str, max_iterations: int):
        fallback_calls.append(user_prompt)
        return "recovered"

    monkeypatch.setattr(main_module, "run_planner", fake_run_planner)

    await main_module.process_prompt(BrokenRunner(), type("S", (), {"id": "s1"})(), "prompt text")

    assert fallback_calls == ["prompt text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/runtime/test_autonomous_runtime.py::test_process_prompt_falls_back_on_tool_call_json_decode_error -q`
Expected: FAIL because `process_prompt()` currently only logs the error and does not recover

- [ ] **Step 3: Implement the narrow fallback**

```python
# src/main.py
except json.JSONDecodeError as e:
    span.record_exception(e)
    span.set_status(Status(StatusCode.ERROR, str(e)))
    logger.exception("ADK tool-call JSON decode failure; retrying via planner")
    fallback = await _run_autonomous_prompt_with_tools(user_query)
    print(f"Swarm: {fallback}")
    logger.info(f"Swarm response: {fallback}", extra={"session_id": session.id})
```

- [ ] **Step 4: Run focused tests**

Run: `./venv/bin/python -m pytest tests/runtime/test_autonomous_runtime.py tests/test_runtime_capabilities.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/main.py src/observability/logger.py tests/runtime/test_autonomous_runtime.py
git commit -m "fix: fall back when ADK tool-call JSON is malformed"
```

### Task 5: Verify the autonomous swarm end-to-end against the confirmed reproduction

**Files:**
- Modify: `tests/runtime/test_autonomous_runtime.py`
- Test: `tests/runtime/test_autonomous_runtime.py`

- [ ] **Step 1: Add an end-to-end smoke test for the repaired runtime path**

```python
import pytest

import src.main as main_module


@pytest.mark.asyncio
async def test_autonomous_prompt_runs_without_runtime_exception(monkeypatch):
    async def fake_run_planner(*, user_prompt: str, system_prompt: str, max_iterations: int):
        return "DONE: explored repository"

    monkeypatch.setattr(main_module, "run_planner", fake_run_planner)

    result = await main_module._run_autonomous_prompt_with_tools(
        main_module._build_autonomous_prompt("project-chimera")
    )

    assert result == "DONE: explored repository"
```

- [ ] **Step 2: Run the automated tests**

Run: `./venv/bin/python -m pytest tests/runtime/test_autonomous_runtime.py tests/test_sub_agents.py tests/test_runtime_capabilities.py -q`
Expected: PASS

- [ ] **Step 3: Run the runtime reproduction manually**

Run: `AUTONOMOUS_MODE=true ./venv/bin/python -m src.main`
Expected: the swarm stays up, prints `Cognitive Foundry Swarm Active`, and no longer crashes with `JSONDecodeError` while handling the initial self-prompt

- [ ] **Step 4: Commit**

```bash
git add tests/runtime/test_autonomous_runtime.py
git commit -m "test: verify autonomous swarm runtime path"
```
