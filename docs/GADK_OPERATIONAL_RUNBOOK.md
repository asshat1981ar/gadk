# GADK Operational Runbook

> **Troubleshooting, debugging, and operating the Cognitive Foundry Swarm in production.**
> companion to `GADK_AGENT_DEVELOPER_GUIDE.md` (architecture) and `GADK_DEVELOPER_ALMANAC.md` (API reference).
> Last updated: 2026-04-21

---

## 1. Environment Setup

### 1.1 Prerequisites

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.11+ | Required |
| `.venv` | — | All packages installed here |
| `OPENROUTER_API_KEY` | — | Required for LLM calls |
| `GITHUB_TOKEN` | — | For repo access |
| Git | any | For version control |

### 1.2 First-Time Setup

```bash
cd /home/westonaaron675/gadk

# Create and activate venv
python3 -m venv .venv
source .venv/bin/activate

# Install all dependencies
pip install -e .

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Verify the installation
.venv/bin/python -c "import src.config; print('OK')"
```

### 1.3 The `.env` File

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-...

# Optional
GITHUB_TOKEN=github_pat_...
REPO_NAME=project-chimera

# Feature flags
TEST_MODE=false
SELF_PROMPT_ENABLED=false
SDLC_MCP_ENABLED=false
AUTONOMOUS_MODE=false
GRAPH_MODE_ENABLED=false
LANGGRAPH_ENABLED=false

# Budget
BUDGET_USD=50.0

# Tuning
SWARM_LOOP_POLL_SEC=2.0
SELF_PROMPT_TICK_INTERVAL_SEC=60.0
LLM_TIMEOUT=30
LLM_RETRIES=3
```

### 1.4 Key Constraint — Always Use `.venv/bin/python`

**System Python is missing dependencies.** Every command must use `.venv/bin/python`, not `python3`:

```bash
# WRONG — system python, missing dependencies
python3 -m pytest -q

# CORRECT — venv python with all dependencies
.venv/bin/python -m pytest -q
```

This applies to: `pytest`, `mypy`, `ruff`, `python -m src.main`, `python -m src.cli.swarm_cli`, everything.

---

## 2. Starting and Stopping

### 2.1 Start the Swarm (Single Run)

```bash
.venv/bin/python -m src.main
```

### 2.2 Start the Swarm (Autonomous Loop)

```bash
AUTONOMOUS_MODE=true .venv/bin/python -m src.main
# Or set autonomous_mode=true in .env
```

### 2.3 Start the MCP Server (Separate)

```bash
.venv/bin/python -m src.mcp.server
```

### 2.4 Stop the Swarm

```bash
python3 -m src.cli.swarm_ctl stop
# Or create the shutdown sentinel manually:
echo "" > .shutdown_sdlc
```

### 2.5 Self-Prompt Preview (Dry Run)

```bash
.venv/bin/python -m src.cli.swarm_cli self-prompt --dry-run
```

---

## 3. Health Checks

### 3.1 CLI Status

```bash
.venv/bin/python -m src.cli.swarm_cli status
```

Output:
```json
{
  "pid": 12345,
  "shutdown_requested": false,
  "queue_depth": 0,
  "total_tasks": 12,
  "planned_tasks": 3,
  "completed_tasks": 8,
  "stalled_tasks": 1,
  "health": "DEGRADED"
}
```

### 3.2 List All Tasks

```bash
.venv/bin/python -m src.cli.swarm_cli tasks
```

### 3.3 Inspect Prompt Queue

```bash
.venv/bin/python -m src.cli.swarm_cli queue
```

### 3.4 Phase Status

```bash
.venv/bin/python -m src.cli.swarm_cli phase status sdlc-my-task-id
```

### 3.5 Advance Phase Manually

```bash
.venv/bin/python -m src.cli.swarm_cli phase advance sdlc-my-task-id IMPLEMENT
```

---

## 4. Troubleshooting

### 4.1 `ImportError: No module named 'google.adk'`

**Cause:** Using system Python instead of the venv.  
**Fix:** `.venv/bin/python -m pytest ...`

### 4.2 `ModuleNotFoundError: No module named 'src'`

**Cause:** Not running from the project root.  
**Fix:** `cd /home/westonaAaron675/gadk && .venv/bin/python ...`

### 4.3 Collection Errors in Pytest

**Cause:** Running with system python3 instead of `.venv/bin/python`.  
**Fix:** Always use `.venv/bin/python -m pytest`.

### 4.4 State Corruption

**Symptom:** Tasks have wrong phase, missing fields, or contradictory state.  
**Recovery:**
```bash
# Check the backup
cat state.json.bak

# Events are append-only — audit the last N events:
tail -50 events.jsonl

# Manually fix state:
# 1. Stop the swarm
# 2. Restore from backup
cp state.json.bak state.json
# 3. Restart
```

### 4.5 Phase Transition Failures

**Symptom:** `advance()` returns `{"allowed": false, "skipped": [...], ...}`.  
**Diagnosis:**
```bash
# Check events for the transition
grep "sdlc-my-task-id" events.jsonl | grep "phase.transition"
```
**Cause:** Usually a quality gate failed. Check gate results in the event payload.

### 4.6 LLM Rate Limits

**Symptom:** `RateLimitError` in logs.  
**Fix:**
```bash
# Reduce concurrency
LLM_TIMEOUT=60

# Or use a faster/fallback model
OPENROUTER_MODEL=openrouter/google/gemini-2.5-flash
```

### 4.7 Planner Returning Empty Responses

**Symptom:** `EmptyPlannerResponseError` in logs.  
**Cause:** Model returned empty content.  
**Fix:** The `run_planner` has `AsyncRetrying` with `wait_exponential` — it retries automatically up to `LLM_RETRIES` times (default 3). If all fail, check API key and model name.

### 4.8 Swarm Loop Not Processing Prompts

**Diagnosis:**
```bash
# Check queue depth
.venv/bin/python -m src.cli.swarm_cli queue

# Check if prompts are in the queue file
cat prompt_queue.jsonl
```
**Cause:** Queue is empty, or loop is sleeping. `SWARM_LOOP_POLL_SEC` controls sleep between iterations (default 2s).

### 4.9 MCP Tools Not Found

**Cause:** MCP server config change requires Hermes restart.  
**Fix:** Restart the Hermes MCP server after any config change.

### 4.10 Review Always Returns "retry"

**Diagnosis:**
```bash
# Check the review extraction
grep "Status:" events.jsonl
```
**Cause:** `_extract_review_status()` keyword scan is too loose. "issue", "concern", "fail" all trigger "retry".  
**Fix:** Use structured output (`INSTRUCTOR_ENABLED=true`) to get typed `ReviewVerdict` instead of keyword scanning.

### 4.11 High Memory Usage

**Cause:** `events.jsonl` grows unbounded, no log rotation.  
**Fix:**
```bash
# Rotate events log periodically
mv events.jsonl events.jsonl.$(date +%Y%m%d)
# Restart swarm (it creates a new file)
```

### 4.12 `elephant-alpha` Tool Calls Failing

**Cause:** Elephant-alpha doesn't support native ADK tool calls well.  
**Fix:** The codebase has automatic fallback from ADK → `run_planner` for this. If fallback is failing, check:
```bash
OPENROUTER_MODEL=openrouter/openai/gpt-4o
```

---

## 5. Debugging Techniques

### 5.1 Structured Logging

Logs are JSON to stdout. Parse with `jq`:

```bash
# View last 20 swarm events
tail -20 events.jsonl | jq .

# Count errors by type
grep '"level":"ERROR"' events.jsonl | jq '.extra.error_type' | sort | uniq -c

# Trace a specific task
grep "sdlc-my-task" events.jsonl | jq '{event: .event, phase: .extra.phase}'
```

### 5.2 Increase Log Verbosity

```bash
LOG_LEVEL=DEBUG .venv/bin/python -m src.main
```

### 5.3 JSON Logs for Humans

```bash
JSON_LOGS=false .venv/bin/python -m src.main
```

### 5.4 Check Metrics

```bash
cat metrics.jsonl
```

### 5.5 Trace a Specific Session

```bash
# Find the session ID
grep "session_id" events.jsonl | tail -5 | jq '.session_id'

# Set a trace ID for correlation
TRACE_ID=my-debug-run .venv/bin/python -m src.main
```

### 5.6 Inspect Planner Output

The planner logs each iteration:
```
INFO planner: Planner iteration 1/10
INFO planner: LLM response length: 1234 chars
INFO planner: Detected 2 tool call(s): ['read_file', 'write_file']
```

Set `LOG_LEVEL=DEBUG` for full LLM prompt/response logging.

---

## 6. Performance Tuning

### 6.1 Slow Discovery Phase

**Symptom:** `_discover()` takes >30s.  
**Cause:** LLM timeout too short, or too many `list_repo_contents` calls.  
**Fix:**
```bash
LLM_TIMEOUT=60
```

### 6.2 Too Many Review Retries

**Symptom:** Cycles take forever, review keeps returning "retry".  
**Fix:**
```bash
MAX_REVIEW_RETRIES=1  # default is 2
```
Or improve the critic prompt to be more decisive.

### 6.3 Prompt Queue Bloat

**Symptom:** `prompt_queue.jsonl` has thousands of entries.  
**Cause:** Self-prompt engine keeps generating prompts that aren't consumed.  
**Fix:** Disable self-prompt:
```bash
SELF_PROMPT_ENABLED=false
```
Then drain the queue:
```bash
echo "" > prompt_queue.jsonl
```

### 6.4 Slow Phase Transitions

**Symptom:** `PhaseController.advance()` takes >5s.  
**Cause:** Quality gates are running slow subprocess commands (lint, typecheck).  
**Fix:** Increase gate timeout:
```bash
GATE_SUBPROCESS_TIMEOUT_SEC=300
```
Or disable specific gates during development.

### 6.5 Token Quota Exhaustion

**Symptom:** `TokenQuotaExceeded` errors.  
**Fix:**
```bash
TOKEN_QUOTA_PER_TASK=100000  # increase
# Or use a cheaper model:
OPENROUTER_MODEL=openrouter/google/gemini-2.5-flash
```

---

## 7. Security Considerations

### 7.1 `OPENROUTER_API_KEY`

- Never commit `.env` to version control
- Rotate the key periodically
- Use a scoped key with minimal permissions for production

### 7.2 `GITHUB_TOKEN`

- Use a GitHub PAT with minimal repo permissions
- For production: use a dedicated service account
- Never log the token value

### 7.3 `execute_python_code` Tool

**WARNING:** This tool executes arbitrary Python in a sandbox. Only enable it in trusted environments:

```python
# In .env — disable for production
SANDBOX_ENABLED=false
```

### 7.4 Prompt Injection

The `RetrievalContext` and `SelfPromptEngine` read from `events.jsonl` and `state.json`. A compromised event log could inject malicious prompts. Mitigate by:
- Running with minimal permissions
- Not logging sensitive task payloads
- Reviewing the prompt queue before execution: `python3 -m src.cli.swarm_cli queue`

### 7.5 Subprocess Execution

The `SandboxExecutor` runs shell commands. Always use `sandbox=True`:
```python
result = execute_python_code(code, sandbox=True)  # default
```

---

## 8. Monitoring in Production

### 8.1 Health Endpoint (MCP)

```bash
# If MCP server is running:
# Tools: swarm_status, repo_read_file, repo_list_directory
```

### 8.2 Metrics to Watch

| Metric | Warning | Critical |
|---|---|---|
| `stalled_tasks` | > 0 | > 5 |
| `queue_depth` | > 100 | > 500 |
| `tasks_failed` | increasing | > 10 |
| LLM error rate | > 5% | > 20% |

### 8.3 Log-Based Alerting

```bash
# Alert if ERROR rate spikes
tail -100 events.jsonl | grep '"level":"ERROR"' | wc -l

# Alert if no completed tasks in 1 hour
grep "DELIVERED" events.jsonl | tail -1
# Check timestamp is recent
```

### 8.4 Cost Monitoring

```bash
# Check token usage
cat metrics.jsonl | jq '.token_usage'

# Check FinOps for budget
.venv/bin/python -c "
from src.agents.finops import tracker
print(tracker.get_current_costs())
"
```

---

## 9. Common Tasks Reference

### 9.1 Reset All State

```bash
# Stop the swarm
python3 -m src.cli.swarm_ctl stop

# Remove state files
rm -f state.json state.json.bak events.jsonl sessions.db

# Remove prompt queue
rm -f prompt_queue.jsonl

# Remove metrics
rm -f metrics.jsonl

# Restart
.venv/bin/python -m src.main
```

### 9.2 Run Specific Test

```bash
.venv/bin/python -m pytest tests/agents/test_builder.py::test_specific_case -v
```

### 9.3 Run Full Test Suite

```bash
.venv/bin/python -m pytest -q
```

### 9.4 Lint and Type Check

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
.venv/bin/python -m mypy src
```

### 9.5 Manually Trigger Self-Prompt

```bash
.venv/bin/python -m src.cli.swarm_cli self-prompt
```

### 9.6 View Event Log

```bash
# Last 20 events
tail -20 events.jsonl | jq .

# All events for a specific task
grep "sdlc-my-task" events.jsonl | jq .
```

---

## 10. Feature Flag Reference

| Flag | Default | Purpose |
|---|---|---|
| `TEST_MODE` | `false` | Use mock LLM and GitHub |
| `AUTONOMOUS_MODE` | `false` | Run continuous discovery loop |
| `SELF_PROMPT_ENABLED` | `false` | Enable gap-driven prompt generation |
| `SDLC_MCP_ENABLED` | `false` | Forward gates to external MCP |
| `LANGGRAPH_ENABLED` | `false` | Use LangGraph-accelerated workflows |
| `GRAPH_MODE_ENABLED` | `false` | Use new graph orchestrator |
| `INSTRUCTOR_ENABLED` | `false` | Use Instructor for structured output |
| `PYDANTIC_AI_ENABLED` | `false` | Use PydanticAI agent routing |
| `RETRIEVAL_BACKEND` | `keyword` | Vector store: `keyword`, `vector`, `sqlite-vec` |

---

## 11. File Reference

| File | Purpose |
|---|---|
| `state.json` | Current task state |
| `state.json.bak` | Backup of last state |
| `events.jsonl` | Append-only event log |
| `prompt_queue.jsonl` | Pending prompts for swarm loop |
| `sessions.db` | ADK session storage (SQLite) |
| `metrics.jsonl` | Aggregated metrics |
| `swarm.pid` | Running process ID |
| `.shutdown_sdlc` | Shutdown sentinel |
| `swarm_alerts.jsonl` | Pulse alerts |
| `budget_alerts.jsonl` | FinOps budget alerts |
| `pulse_metrics.jsonl` | Pulse health metrics |

---

## 12. Error Code Reference

| Exception | File | Cause |
|---|---|---|
| `SwarmStartupError` | `main.py` | Session/runner/init failure |
| `ToolExecutionError` | `exceptions.py` | Tool call failed |
| `PromptProcessingError` | `main.py` | ADK/planner execution failure |
| `ConfigurationError` | `main.py` | Missing env var |
| `SwarmLoopError` | `main.py` | Loop iteration crash |
| `SelfPromptError` | `main.py` | Self-prompt tick failed |
| `StructuredOutputError` | `structured_output.py` | Pydantic validation failed |
| `EmptyPlannerResponseError` | `planner.py` | LLM returned no content |
| `RateLimitError` | LiteLLM | OpenRouter rate limit hit |
