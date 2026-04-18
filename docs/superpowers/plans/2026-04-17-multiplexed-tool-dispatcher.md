# Multiplexed Tool Dispatcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a batch tool execution layer to enable parallel throughput and complex coordination for the Elephant AI model.

**Architecture:** Create a `src/tools/dispatcher.py` module containing the `batch_execute` tool. This tool acts as a "meta-tool" that maps string identifiers to existing async tools (e.g., `search_web`, `execute_python_code`) and runs them concurrently.

**Tech Stack:** Python, Google ADK, LiteLLM, asyncio.

---

### Task 1: The Multiplexed Dispatcher Tool

**Files:**
- Create: `src/tools/dispatcher.py`
- Test: `tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from src.tools.dispatcher import batch_execute

@pytest.mark.asyncio
async def test_batch_execute_success():
    # Test executing a simple echo mock (we'll implement a registry later)
    requests = [
        {"tool_name": "mock_echo", "args": {"msg": "Hello"}},
        {"tool_name": "mock_echo", "args": {"msg": "World"}}
    ]
    results = await batch_execute(requests)
    assert len(results) == 2
    assert results[0]["output"] == "Hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_dispatcher.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement Dispatcher and Registry**

```python
import asyncio
from typing import List, Dict, Any, Callable
from pydantic import BaseModel

# Tool Registry to avoid circular imports
_TOOL_REGISTRY: Dict[str, Callable] = {}

def register_tool(name: str, func: Callable):
    _TOOL_REGISTRY[name] = func

async def batch_execute(requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Executes multiple tool calls concurrently.
    Args:
        requests: List of dicts with 'tool_name' and 'args'.
    """
    async def run_task(req):
        name = req.get("tool_name")
        args = req.get("args", {})
        
        if name not in _TOOL_REGISTRY:
            return {"status": "error", "message": f"Tool '{name}' not found."}
        
        try:
            func = _TOOL_REGISTRY[name]
            if asyncio.iscoroutinefunction(func):
                res = await func(**args)
            else:
                res = func(**args)
            return {"status": "success", "output": res}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return await asyncio.gather(*(run_task(r) for r in requests))
```

- [ ] **Step 4: Update test with mock registry and verify it passes**

```python
# Add to tests/test_dispatcher.py
from src.tools.dispatcher import register_tool

def mock_echo(msg: str) -> str:
    return msg

register_tool("mock_echo", mock_echo)
```

Run: `PYTHONPATH=. pytest tests/test_dispatcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/dispatcher.py tests/test_dispatcher.py
git commit -m "feat: add Multiplexed Tool Dispatcher with registry"
```

### Task 2: Register Core Tools

**Files:**
- Modify: `src/main.py` (or a dedicated registry initialization file)

- [ ] **Step 1: Initialize Registry**
Register existing tools (`search_web`, `execute_python_code`, `scavenge_and_plan`) so the dispatcher can find them.

```python
from src.tools.dispatcher import register_tool
from src.tools.web_search import search_web
from src.tools.sandbox_executor import execute_python_code
from src.agents.ideator import scavenge_and_plan

register_tool("search_web", search_web)
register_tool("execute_python_code", execute_python_code)
register_tool("scavenge_and_plan", scavenge_and_plan)
```

- [ ] **Step 2: Commit**

```bash
git add src/main.py
git commit -m "feat: register core tools for multiplexed dispatch"
```

### Task 3: Update Ideator for Parallel Throughput

**Files:**
- Modify: `src/agents/ideator.py`

- [ ] **Step 1: Add batch_execute to Ideator**
Update the Ideator agent to prioritize `batch_execute` for multiple searches.

```python
from src.tools.dispatcher import batch_execute

# ... existing code ...

ideator_agent = Agent(
    name="Ideator",
    model=elephant_model,
    instruction="""You are the Ideator of the Cognitive Foundry. 
    Your goal is to proactively scavenge the web for new technical trends. 
    Use the batch_execute tool to perform multiple searches at once (throughput). 
    Provide an array of 'tool_name': 'search_web' requests in the batch.""",
    tools=[batch_execute, search_web, scavenge_and_plan]
)
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/ideator.py
git commit -m "feat: enable high-throughput searching in Ideator via batch_execute"
```

### Task 4: Parallel Validation for Critic

**Files:**
- Modify: `src/agents/critic.py`

- [ ] **Step 1: Add batch_execute to Critic**
Enable the Critic to validate multiple code snippets or test cases concurrently.

```python
from src.tools.dispatcher import batch_execute

# ... existing code ...

class CriticAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Critic",
            instruction="""You evaluate Python code. 
            Use batch_execute to run multiple validation tests or code snippets in parallel 
            using 'tool_name': 'execute_python_code'.""",
            tools=[batch_execute, execute_python_code]
        )
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/critic.py
git commit -m "feat: enable parallel code validation in Critic"
```
