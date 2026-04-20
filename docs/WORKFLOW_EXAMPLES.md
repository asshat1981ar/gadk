# Workflow Examples
## Cognitive Foundry — End-to-End Walkthroughs

---

## Workflow 1: Idea to MVP (Future Phase 2 State)

**Scenario:** User wants to build a personal finance tracker web app.

### Step 1 — User describes the idea

User types in the Web Chat UI:
```
Build me a personal finance tracker. I want to track income, expenses,
and savings goals. Users should be able to log in, see a dashboard with
charts, and export their data as CSV.
```

### Step 2 — Ideator scans for context and creates a task

The Orchestrator delegates to **Ideator**.  
Ideator runs:
```python
# Parallel tool calls via batch_execute
[
  {"tool_name": "search_web", "args": {"query": "personal finance tracker fastapi react best practices 2025"}},
  {"tool_name": "search_web", "args": {"query": "Python finance tracker open source examples github"}}
]
```

Ideator creates a structured task:
```python
create_structured_task(
    title="Personal Finance Tracker — Initial MVP",
    description="FastAPI backend + React frontend with auth, dashboard, CSV export.",
    acceptance_criteria=[
        "User can register and log in (JWT auth)",
        "CRUD endpoints for income/expense records",
        "Dashboard with monthly summary charts",
        "CSV export endpoint",
        "≥ 65% test coverage"
    ],
    priority=2,
    complexity="large",
    suggested_agent="Builder"
)
```

**UI shows:** "Task created → advancing to ARCHITECT phase…"

### Step 3 — Architect produces the ADR (with user approval gate)

**Architect** reads the task, calls `draft_architecture_note`:
```
Context: User wants a personal finance tracker with FastAPI + React.
Decision: FastAPI + SQLAlchemy + SQLite (dev) / PostgreSQL (prod); React + Recharts.
Alternatives considered:
  - Django REST Framework (heavier, slower iteration)
  - Vue.js (smaller ecosystem for charts)
Consequences:
  - FastAPI gives async endpoints and auto-generated OpenAPI docs
  - SQLAlchemy async mode enables future scaling
  - Recharts is lightweight and widely documented
Touched paths:
  - backend/main.py, backend/models.py, backend/routers/
  - frontend/src/components/Dashboard.tsx
```

**Chat UI shows** the architecture note with **[Approve] / [Revise]** buttons.

User clicks **[Approve]** → phase advances to IMPLEMENT.

### Step 4 — Builder implements

**Builder** receives the ADR and task.  
Writes files via `write_file`:
- `backend/main.py` — FastAPI app with auth endpoints
- `backend/models.py` — SQLAlchemy ORM models
- `backend/routers/transactions.py` — CRUD routes
- `frontend/src/App.tsx` — React app shell
- `frontend/src/components/Dashboard.tsx` — charts

Commits to branch `feature/personal-finance-tracker` via `commit_files_to_branch`.

### Step 5 — Critic reviews

**Critic** evaluates the staged code:
- Runs `evaluate()` on Python files in sandbox
- Calls `create_review_verdict()` → `{"status": "retry", "summary": "Missing input validation on POST /transactions"}`
- Routes back to Builder for one rework cycle (bounded)

Builder adds input validation. Critic re-evaluates → `{"status": "pass"}`.

### Step 6 — Governor approves release

**Governor** runs `run_governance_review()`:
- ContentGuardGate: PR body is substantial ✅
- LintGate (ruff): 0 violations ✅
- TypecheckGate (mypy): clean ✅
- SecurityScanGate (bandit): no HIGH issues ✅
- TestCoverageGate: 68% ✅ (≥ 65%)
- Budget: $0.42 used of $10.00 ✅

Verdict: `ready=True`.

**Chat UI shows:** "Your Personal Finance Tracker is ready! [View PR]"

Governor opens PR on GitHub. User reviews and merges.

---

## Workflow 2: Feature Request via CLI (Current State)

**Scenario:** Developer wants to add a new API endpoint to an existing project.

```bash
# Inject a prompt into the running swarm
python3 -m src.cli.swarm_cli prompt \
  "Add a /health endpoint to the FastAPI app in src/api.py that returns uptime and version"
```

The swarm picks this up from `prompt_queue.jsonl` within `SWARM_LOOP_POLL_SEC` (default 2 s).

Orchestrator → Ideator → creates task → Builder → writes code → Critic → Governor → PR opened.

```bash
# Monitor progress
python3 -m src.cli.swarm_cli dashboard --refresh 3
```

---

## Workflow 3: Autonomous Improvement Loop (Current State)

**Scenario:** `AUTONOMOUS_MODE=true` swarm running against `project-chimera`.

```
Loop iteration (every SWARM_LOOP_POLL_SEC seconds):

1. dequeue_prompts() — check for injected prompts
2. self_prompt_tick (every 60 s) — scan for gap signals:
   - collect_coverage_signals(coverage.xml) → flag modules < threshold
   - collect_event_signals(events.jsonl) → flag unresolved STALLED tasks
   - collect_backlog_signals(state.json) → flag tasks stalled > 24 h
3. For each gap signal:
   - Deduplicate by SHA-256(phase + intent)
   - Rate-limit: max 6 prompts/hour
   - Write to prompt_queue.jsonl
4. Next loop iteration picks up the synthesized prompt and routes to Ideator
```

Stop the loop:
```bash
touch .swarm_shutdown
# or
python3 -m src.cli.swarm_cli stop
```

---

## Workflow 4: Phase Management via CLI (Current State)

```bash
# Check current phase of a work item
python3 -m src.cli.swarm_cli phase status task-1234-my-feature

# Output:
# task-1234-my-feature  IMPLEMENT
# History:
#   PLAN → ARCHITECT  2026-04-20T10:00:00Z  "Ideator proposal approved"
#   ARCHITECT → IMPLEMENT  2026-04-20T10:05:00Z  "ADR-001 accepted"

# Advance a work item (with gate evaluation)
python3 -m src.cli.swarm_cli phase advance task-1234-my-feature REVIEW

# Force-advance past a failing gate (operator override)
python3 -m src.cli.swarm_cli phase advance task-1234-my-feature GOVERN \
  --force --reason "Waiving coverage gate for prototype"
```

---

## Workflow 5: Interactive REPL Session (Current State)

```bash
python3 -m src.cli.interactive
```

```
╔═══════════════════════════════════════════════════════════╗
║     Cognitive Foundry Swarm Interactive Shell             ║
╚═══════════════════════════════════════════════════════════╝

swarm> status
Swarm PID: 12345 | Health: HEALTHY | Tasks: 3 | Queue: 0

swarm> tasks --status PENDING
task-001-add-auth-endpoint       PENDING   priority=1
task-002-fix-coverage-gap        PENDING   priority=3

swarm> prompt "Investigate why tests are flaky in src/services/"
Prompt queued. The swarm will process it within 2 seconds.

swarm> dashboard --refresh 5
[Live task board — refreshes every 5 seconds]

swarm> exit
Exiting swarm shell.
```

---

## Workflow 6: MCP Integration (Current State)

An MCP client (VS Code extension, another agent) can call:

```json
// Tool: swarm_status
{}

// Response:
{
  "status": "ok",
  "payload": {
    "pid": 12345,
    "health": "HEALTHY",
    "total_tasks": 5,
    "completed": 3,
    "stalled": 0,
    "queue_depth": 1
  }
}
```

```json
// Tool: repo_read_file
{"path": "src/main.py"}

// Response:
{
  "status": "ok",
  "payload": {"path": "src/main.py", "content": "import asyncio..."}
}
```

Start the MCP server:
```bash
python3 -m src.mcp.server
```

Configure in `.vscode/settings.json`:
```json
{
  "mcp.servers": {
    "cognitive-foundry": {
      "command": "python3",
      "args": ["-m", "src.mcp.server"],
      "cwd": "/path/to/gadk"
    }
  }
}
```
