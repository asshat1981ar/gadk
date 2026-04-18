# Cognitive Foundry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an industrial-grade, proactive multi-agent SDLC swarm using Google Agent Development Kit (Python) with autonomous scraping and self-propagation capabilities.

**Architecture:** A Hierarchical Factory model utilizing Google ADK Runners, A2A messaging, and a high-frequency State Table for coordination. Agents scavenge data via Playwright, manage tasks via GitHub Issues, and expand the system via a staged "Shadow Source" propagation engine.

**Tech Stack:** Google ADK (Python), Gemini 1.5 Pro, Playwright, GitHub REST API, MCP Agent Memory.

---

## Phase 1: Foundations (Core Engine)

### Task 1: Environment Setup & Configuration
**Files:**
- Create: `src/config.py`
- Create: `requirements.txt`

- [ ] **Step 1: Define dependencies**
```text
google-cloud-aiplatform
google-adk-sdk
playwright
pygithub
python-dotenv
pytest
```

- [ ] **Step 2: Create config module**
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    REPO_NAME = os.getenv("REPO_NAME")
    STATE_TABLE_TYPE = os.getenv("STATE_TABLE_TYPE", "json")  # Default to local JSON for dev
    AUTONOMOUS_MODE = os.getenv("AUTONOMOUS_MODE", "false").lower() == "true"
    TOKEN_QUOTA_PER_TASK = 50000
```

- [ ] **Step 3: Commit**
```bash
git add src/config.py requirements.txt
git commit -m "chore: setup foundations and config"
```

### Task 2: State Table Interface
**Files:**
- Create: `src/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write state table tests**
```python
import pytest
from src.state import StateManager

def test_set_and_get_task():
    sm = StateManager(storage_type="memory")
    sm.set_task("task-1", {"status": "PENDING", "priority": 1})
    task = sm.get_task("task-1")
    assert task["status"] == "PENDING"
```

- [ ] **Step 2: Implement StateManager**
```python
import json

class StateManager:
    def __init__(self, storage_type="json"):
        self.storage_type = storage_type
        self.data = {}

    def set_task(self, task_id, task_data):
        self.data[task_id] = task_data
        if self.storage_type == "json":
            with open("state.json", "w") as f:
                json.dump(self.data, f)

    def get_task(self, task_id):
        return self.data.get(task_id)
```

- [ ] **Step 3: Run tests**
`pytest tests/test_state.py`

- [ ] **Step 4: Commit**
```bash
git add src/state.py tests/test_state.py
git commit -m "feat: implement StateManager for coordination"
```

### Task 3: Basic ADK Orchestrator
**Files:**
- Create: `src/agents/orchestrator.py`
- Create: `src/main.py`

- [ ] **Step 1: Implement Orchestrator Agent**
```python
from google.adk import Agent, Runner

class OrchestratorAgent(Agent):
    def __init__(self):
        super().__init__(name="Orchestrator")

    async def on_event(self, event):
        print(f"Orchestrator received: {event}")
        # Logic for A2A routing will go here
```

- [ ] **Step 2: Setup main entry point**
```python
import asyncio
from src.agents.orchestrator import OrchestratorAgent
from google.adk import Runner

async def main():
    orchestrator = OrchestratorAgent()
    runner = Runner(agents=[orchestrator])
    await runner.run()

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Commit**
```bash
git add src/agents/orchestrator.py src/main.py
git commit -m "feat: setup basic ADK Orchestrator and Runner"
```

## Phase 2: Task & Scrape Integration

### Task 4: Playwright Scraper Tool
**Files:**
- Create: `src/tools/scraper.py`
- Test: `tests/test_scraper.py`

- [ ] **Step 1: Implement Scraper with Guardrails**
```python
from playwright.async_api import async_playwright
from google.adk import Tool

class ScraperTool(Tool):
    def __init__(self, allowlist):
        self.allowlist = allowlist

    async def scrape(self, url):
        if not any(domain in url for domain in self.allowlist):
            return "Error: Domain not in allowlist"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url)
            content = await page.content()
            await browser.close()
            return content
```

- [ ] **Step 2: Commit**
```bash
git add src/tools/scraper.py
git commit -m "feat: add Playwright Scraper tool with domain allowlist"
```

### Task 5: GitHub Issues Tool
**Files:**
- Create: `src/tools/github_tool.py`

- [ ] **Step 1: Implement GitHub Tool**
```python
from github import Github
from google.adk import Tool
from src.config import Config

class GitHubTool(Tool):
    def __init__(self):
        self.gh = Github(Config.GITHUB_TOKEN)
        self.repo = self.gh.get_repo(Config.REPO_NAME)

    async def create_issue(self, title, body):
        issue = self.repo.create_issue(title=title, body=body)
        return issue.html_url
```

- [ ] **Step 2: Commit**
```bash
git add src/tools/github_tool.py
git commit -m "feat: implement GitHub Issues tool"
```

## Phase 3: Propagation & Critique

### Task 6: Structural Builder & Critic
**Files:**
- Create: `src/agents/builder.py`
- Create: `src/agents/critic.py`

- [ ] **Step 1: Implement Builder (Shadow Source)**
```python
from google.adk import Agent

class BuilderAgent(Agent):
    async def build_tool(self, tool_spec):
        # Writes new tool to src/staged_agents/
        path = f"src/staged_agents/{tool_spec['name']}.py"
        with open(path, "w") as f:
            f.write(tool_spec['code'])
        return path
```

- [ ] **Step 2: Implement Critic (Sandbox Eval)**
```python
from google.adk import Agent

class CriticAgent(Agent):
    async def evaluate(self, staged_path):
        # Logic to run code in src/sandbox/
        # For now, a simple 'mock' pass
        return {"status": "PASS", "score": 0.9}
```

- [ ] **Step 3: Commit**
```bash
git add src/agents/builder.py src/agents/critic.py
git commit -m "feat: implement Builder and Critic for self-propagation"
```

## Phase 4: Optimization & Pulse

### Task 7: Pulse Agent & Status Command
**Files:**
- Create: `src/agents/pulse.py`
- Create: `.claude/commands/status.md`

- [ ] **Step 1: Implement Pulse Agent**
```python
from google.adk import Agent

class PulseAgent(Agent):
    async def generate_report(self, state_data):
        return f"Pulse: Swarm is active. {len(state_data)} tasks in progress."
```

- [ ] **Step 2: Create /status command**
```markdown
---
description: Get the current status of the Cognitive Foundry swarm
---
Get the current status of the swarm from the State Table and generate a summary report.
```

- [ ] **Step 3: Commit**
```bash
git add src/agents/pulse.py .claude/commands/status.md
git commit -m "feat: add Pulse agent and /status command"
```

## Phase 5: FinOps & Sustainability

### Task 8: FinOps Token Tracker
**Files:**
- Create: `src/agents/finops.py`

- [ ] **Step 1: Implement Token Tracker**
```python
from google.adk import Agent
from src.config import Config

class FinOpsAgent(Agent):
    def __init__(self):
        self.total_usage = 0

    async def check_quota(self, usage):
        self.total_usage += usage
        if self.total_usage > Config.TOKEN_QUOTA_PER_TASK:
            return "QUOTA_EXCEEDED"
        return "OK"
```

- [ ] **Step 2: Commit**
```bash
git add src/agents/finops.py
git commit -m "feat: implement FinOps agent for token tracking"
```
