# Advanced Toolset and Function Calling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Research and develop an advanced toolset (Code Sandbox, Web Search, MCP Bridge) and ensure robust function-calling compatibility with OpenRouter Elephant for the Cognitive Foundry swarm.

**Architecture:** Expand the `src/tools/` directory with new standalone tools that inherit from the ADK `Tool` base class (or standard Python functions with type hints that the ADK can parse into JSON Schema). Integrate a basic Code Execution sandbox for the Critic agent, a Web Search tool for the Ideator, and an MCP Bridge to dynamically load external capabilities.

**Tech Stack:** Python, Google ADK, LiteLLM (OpenRouter/Elephant), standard library `subprocess` (for basic sandbox prototyping), `aiohttp` for web requests.

---

### Task 1: Code Execution Sandbox Tool

**Files:**
- Create: `src/tools/sandbox_executor.py`
- Test: `tests/test_sandbox.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
import os
from src.tools.sandbox_executor import execute_python_code

@pytest.mark.asyncio
async def test_execute_safe_code():
    code = "print('Hello Sandbox')"
    result = await execute_python_code(code)
    assert "Hello Sandbox" in result

@pytest.mark.asyncio
async def test_execute_timeout():
    code = "import time; time.sleep(5)"
    result = await execute_python_code(code, timeout=1)
    assert "Timeout" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/test_sandbox.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

- [ ] **Step 3: Write minimal implementation**

```python
import asyncio
import tempfile
import os
import sys

async def execute_python_code(code: str, timeout: int = 5) -> str:
    """
    Executes Python code in a restricted temporary environment.
    Args:
        code: The Python code to execute.
        timeout: Maximum execution time in seconds.
    """
    # Restrict dangerous imports trivially for prototype
    if "os.system" in code or "subprocess" in code:
        return "Error: Dangerous operations detected."

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode()
            err_output = stderr.decode()
            if err_output:
                return f"Error: {err_output}"
            return output.strip()
        except asyncio.TimeoutError:
            proc.kill()
            return "Error: Execution Timeout."
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/test_sandbox.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/tools/sandbox_executor.py tests/test_sandbox.py
git commit -m "feat: add Code Execution Sandbox tool"
```

### Task 2: Web Search Tool (DuckDuckGo Lite)

**Files:**
- Create: `src/tools/web_search.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add dependency**
Append `duckduckgo-search` to `requirements.txt`.

- [ ] **Step 2: Write minimal implementation**

```python
from duckduckgo_search import DDGS
import asyncio

def search_web(query: str, max_results: int = 3) -> str:
    """
    Searches the web using DuckDuckGo to find real-time information.
    Args:
        query: The search query.
        max_results: The maximum number of results to return.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No results found."
            
            formatted = []
            for r in results:
                formatted.append(f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}")
            return "\n\n".join(formatted)
    except Exception as e:
        return f"Search Error: {str(e)}"
```

- [ ] **Step 3: Commit**

```bash
git add src/tools/web_search.py requirements.txt
git commit -m "feat: add DuckDuckGo Web Search tool"
```

### Task 3: Enhance Critic Agent with Sandbox

**Files:**
- Modify: `src/agents/critic.py`

- [ ] **Step 1: Write minimal implementation**
Replace the placeholder mock logic in `CriticAgent` with the new sandbox tool.

```python
try:
    from google.adk.agents import Agent
except ImportError:
    class Agent:
        def __init__(self, name, model=None, instruction=None, tools=None): 
            self.name = name
            self.tools = tools

from src.tools.sandbox_executor import execute_python_code

class CriticAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Critic",
            instruction="You evaluate staged Python code by executing it in a sandbox. Ensure it runs without syntax errors.",
            tools=[execute_python_code]
        )

    async def evaluate(self, staged_path: str):
        if not staged_path.endswith(".py"):
            return {"status": "FAIL", "reason": "Not a python file"}
        
        try:
            with open(staged_path, "r") as f:
                code = f.read()
            
            # Execute in sandbox
            result = await execute_python_code(code)
            
            if result.startswith("Error:"):
                return {"status": "FAIL", "reason": result}
            
            return {"status": "PASS", "score": 1.0, "output": result}
        except Exception as e:
            return {"status": "FAIL", "reason": str(e)}
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/critic.py
git commit -m "feat: enhance Critic agent to use Python Sandbox execution"
```

### Task 4: Integrate Search Tool to Ideator

**Files:**
- Modify: `src/agents/ideator.py`

- [ ] **Step 1: Write minimal implementation**
Add `search_web` to the `Ideator` agent's tools.

*Edit `src/agents/ideator.py` to import and append the tool:*

```python
# ... existing imports ...
from src.tools.web_search import search_web

# ... existing code ...

ideator_agent = Agent(
    name="Ideator",
    model=elephant_model,
    instruction="""You are the Ideator of the Cognitive Foundry. 
    Your goal is to proactively scavenge the web for new technical trends and technical debt. 
    Use the search_web tool to find topics, then use scavenge_and_plan to create autonomous tasks.""",
    tools=[search_web, scavenge_and_plan]
)
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/ideator.py
git commit -m "feat: integrate Web Search tool into Ideator agent"
```
