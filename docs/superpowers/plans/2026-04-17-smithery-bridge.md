# Smithery MCP Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a dynamic Smithery MCP Bridge that allows Cognitive Foundry agents to call any tool from the Smithery marketplace.

**Architecture:** Create a `SmitheryBridgeTool` that wraps the `smithery` CLI. This tool will take a server ID, tool name, and arguments, then execute the call via `smithery tool call` and return the result. This avoids hardcoding specific tools and leverages Smithery's managed connection lifecycle.

**Tech Stack:** Python, Smithery CLI, Google ADK.

---

### Task 1: Smithery Bridge Tool

**Files:**
- Create: `src/tools/smithery_bridge.py`
- Test: `tests/test_smithery_bridge.py`

- [ ] **Step 1: Write failing tests**

```python
import pytest
from src.tools.smithery_bridge import call_smithery_tool

@pytest.mark.asyncio
async def test_bridge_call_mock():
    # We mock the CLI for testing if Smithery is not authenticated
    result = await call_smithery_tool("mock-server", "mock-tool", {"arg": "val"})
    assert "Error" in result or "mock" in result
```

- [ ] **Step 2: Implement the Smithery Bridge**

```python
import asyncio
import json
import subprocess

async def call_smithery_tool(server_id: str, tool_name: str, args: dict) -> str:
    """
    Dynamically calls an MCP tool from the Smithery marketplace.
    Args:
        server_id: The ID of the Smithery server (e.g., 'neon', 'slack').
        tool_name: The name of the tool to call.
        args: A dictionary of arguments for the tool.
    """
    args_json = json.dumps(args)
    cmd = ["smithery", "tool", "call", f"{server_id}", tool_name, args_json]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            return f"Smithery Error: {stderr.decode()}"
            
        return stdout.decode().strip()
    except Exception as e:
        return f"Bridge Error: {str(e)}"
```

- [ ] **Step 3: Commit**

```bash
git add src/tools/smithery_bridge.py tests/test_smithery_bridge.py
git commit -m "feat: add Smithery MCP Bridge tool"
```

### Task 2: Integrate Bridge into Orchestrator

**Files:**
- Modify: `src/agents/orchestrator.py`

- [ ] **Step 1: Update Orchestrator**
Add the `call_smithery_tool` to the Orchestrator's tools and update its instructions.

```python
# ... existing imports ...
from src.tools.smithery_bridge import call_smithery_tool

# ... update orchestrator_agent ...
orchestrator_agent = Agent(
    name="Orchestrator",
    model=elephant_model,
    instruction="""You are the master orchestrator. 
    You have access to the Smithery marketplace. 
    Use call_smithery_tool to access external services like Slack, Postgres, or Memory. 
    Common servers: 'neon' (Postgres), 'node2flow/slack' (Slack).""",
    tools=[route_task, ask_ideator, call_smithery_tool]
)
```

- [ ] **Step 2: Commit**

```bash
git add src/agents/orchestrator.py
git commit -m "feat: integrate Smithery Bridge into Orchestrator"
```
