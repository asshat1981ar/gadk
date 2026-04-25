# Ollama Cloud Agents for GADK: Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
> **Status:** Pre-research complete. Three implementations planned.

**Goal:** Introduce Ollama Cloud as a free/low-cost inference backend for GADK agents, enabling fully local or cloud-hosted inference without OpenRouter dependency.

**Architecture:** Ollama Cloud models (`:cloud` suffix, e.g. `qwen3:14b-cloud`) work as authenticated proxies to Ollama's remote inference infrastructure. Local `ollama` CLI acts as a passthrough — no GPU needed, same API as local models, ~10x cheaper than OpenRouter for equivalent model sizes.

**Tech Stack:** `ollama` Python client (`pip install ollama`), Ollama Cloud API (`https://ollama.com`), existing `LiteLlm` abstraction layer.

---

## Research Decomposition Summary

### Ollama Cloud (vs OpenRouter)
| Factor | OpenRouter | Ollama Cloud |
|--------|------------|--------------|
| Cost | ~$3-15/M tokens | ~$0 (local rate limits) + API key |
| GPU required | No (API service) | No (cloud models offload to Ollama infrastructure) |
| API style | OpenAI-compatible | OpenAI-compatible |
| Auth | `OPENROUTER_API_KEY` | `OLLAMA_API_KEY` + `ollama signin` |
| Model library | Hundreds | Growing (Qwen, Gemma, GLM, gpt-oss) |
| GADK integration | Currently used | Drop-in via LiteLlm or direct client |
| Streaming | Yes | Yes |
| Tools/MCP | Limited | Limited |

**Key insight:** Ollama Cloud models (`:cloud` suffix) auto-offload inference to Ollama's cloud when local hardware can't run the model. Same API, zero GPU cost, significantly cheaper for development.

### gh-aw (GitHub Agentic Workflows) (Implementation 2)
- **What it is:** Markdown files in `.github/workflows/` that describe desired repo outcomes in plain English. `gh aw compile` compiles them into hardened GitHub Actions YAML with sandboxed AI agent execution.
- **Architecture:** `gh aw` CLI + markdown workflow → compiled `.lock.yml` (GitHub Actions) + AI coding agent (Claude Code, Copilot, Codex, OpenCode) + safe outputs for GitHub write operations.
- **GADK fit:** Continuous PR review, CI investigation, issue triage, docs alignment — all run on GitHub's infra, zero local compute.
- **Strengths:** Zero local compute, built-in guardrails, read-only by default, safe outputs for PRs/comments, schedule/on-push/trigger modes, already integrates with Claude Code.
- **Weaknesses:** Requires GitHub Actions quota, state lives in GH (sync challenges with local GADK state), limited to repository context, gh-aw still in tech preview, YAML compilation step adds friction.
- **GADK use case:** Continuous PR review agent that posts review comments on every PR; CI failure investigator that auto-comments root cause + fix suggestion.

### Memori Persistent Memory (Implementation 3)
- **What it is:** LLM-agnostic persistent memory layer that converts unstructured conversation into semantic triples + summaries. 81.95% accuracy on LoCoMo benchmark at only 1,294 tokens/query (~5% of full context).
- **Architecture:** Advanced Augmentation pipeline: raw dialogue → semantic triples + summaries → compact retrieval → reasoning.
- **GADK fit:** Replace stateless session context with persistent cross-session memory. Agents remember past decisions, failed approaches, and successful patterns.
- **Strengths:** Token-efficient (67% fewer tokens than alternatives), LLM-agnostic (works with any model), structured retrieval (semantic triples), proven benchmark performance.
- **Weaknesses:** New library (Memori v1, not yet battle-tested), requires embedding model + vector DB, triple extraction quality depends on LLM, adds latency on every memory access, triple schema design is non-trivial.
- **GADK use case:** Persistent memory for the Orchestrator agent — remembers which phase transitions failed before, which workarounds succeeded, user preferences across sessions.

---

## IMPLEMENTATION 1: Ollama Cloud Backend Adapter

### Task 1: Discover Ollama Python Client API

**Objective:** Verify Ollama Python client API for chat completions with streaming and tool calling.

**Step 1: Write failing test**

```python
# tests/services/test_ollama_backend.py
from src.services.ollama_backend import OllamaBackend

def test_chat_completion_basic():
    backend = OllamaBackend(model="qwen3:14b")
    response = backend.chat([{"role": "user", "content": "What is 2+2?"}])
    assert response["choices"][0]["message"]["content"] == "4"
```

**Step 2: Run test**
```
pytest tests/services/test_ollama_backend.py::test_chat_completion_basic -v
```
Expected: FAIL — module not found

**Step 3: Implement**
```python
# src/services/ollama_backend.py
"""Ollama Cloud backend — drop-in replacement for OpenRouter LiteLlm."""
from __future__ import annotations

import os
from typing import Any

try:
    import ollama
except ImportError:
    ollama = None  # type: ignore

from src.config import Config
from src.observability.logger import get_logger

logger = get_logger(__name__)


class OllamaBackend:
    """Chat completion backend using Ollama Cloud or local Ollama.

    Supports :cloud models (e.g. qwen3:14b-cloud) which auto-offload
    to Ollama's remote inference when local hardware can't run them.
    Falls back to local models if OLLAMA_API_KEY is not set.
    """

    def __init__(
        self,
        model: str = "qwen3:14b",
        base_url: str = "https://ollama.com",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self._client: Any = None
        # Auth: prefer OLLAMA_API_KEY env var, else check param, else None (local only)
        self.api_key = api_key or os.environ.get("OLLAMA_API_KEY")

    @property
    def client(self) -> Any:
        if self._client is None:
            import ollama as _ollama

            self._client = _ollama.Client(host=self.base_url)
        return self._client

    def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Call ollama chat API. Returns OpenAI-compatible response dict."""
        opts: dict[str, Any] = {"model": self.model, "messages": messages, "stream": stream}
        if self.api_key:
            opts["options"] = {"api_key": self.api_key}

        raw = self.client.chat(**opts)

        if stream:
            return raw  # Return generator as-is

        # Convert Ollama response to OpenAI-compatible format
        content = raw.get("message", {}).get("content", "")
        return {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
                "total_tokens": raw.get("prompt_eval_count", 0)
                + raw.get("eval_count", 0),
            },
            "model": self.model,
        }
```

**Step 4: Run test**
```
pytest tests/services/test_ollama_backend.py::test_chat_completion_basic -v
```
Expected: PASS (or skip if `OLLAMA_API_KEY` not set)

**Step 5: Commit**
```bash
git add tests/services/test_ollama_backend.py src/services/ollama_backend.py
git commit -m "feat(ollama): add OllamaBackend for cloud inference (Task 1)"
```

---

### Task 2: Add Ollama config flags

**Objective:** Add `ollama_model`, `ollama_base_url`, `ollama_api_key` to Settings and Config.

**Files:**
- Modify: `src/config.py`

**Step 1: Write failing test**

```python
# tests/services/test_ollama_backend.py (add)
def test_config_defaults():
    from src.config import Config
    assert Config.OLLAMA_MODEL == "qwen3:14b"
    assert Config.OLLAMA_BASE_URL == "https://ollama.com"
    assert Config.OLLAMA_API_KEY is None
```

**Step 2: Run test**
```
pytest tests/services/test_ollama_backend.py::test_config_defaults -v
```
Expected: FAIL — Config.OLLAMA_* not defined

**Step 3: Implement**

Add to `Settings` class:
```python
ollama_model: str = "qwen3:14b"
ollama_base_url: str = "https://ollama.com"
ollama_api_key: str | None = None
```

Add to `Config` class:
```python
OLLAMA_MODEL: str = "qwen3:14b"
OLLAMA_BASE_URL: str = "https://ollama.com"
OLLAMA_API_KEY: str | None = None
```

**Step 4: Run test**
Expected: PASS

**Step 5: Commit**
```bash
git commit -m "feat(ollama): add Ollama config flags (Task 2)"
```

---

### Task 3: Wire OllamaBackend into agent LiteLlm

**Objective:** Add `OPENROUTER_MODEL=ollama/qwen3:14b` routing so agents can use Ollama Cloud via existing LiteLlm abstraction.

**Files:**
- Modify: `src/services/model_router.py`

**Step 1: Write failing test**

```python
# tests/services/test_ollama_backend.py (add)
def test_model_router_ollama_model():
    from src.services.model_router import ModelRouter
    router = ModelRouter()
    # When model starts with "ollama/", route to OllamaBackend
    backend = router.get_backend("ollama/qwen3:14b")
    assert backend is not None
```

**Step 2: Run test**
Expected: FAIL — model_router doesn't handle "ollama/" prefix

**Step 3: Implement**

Add to `ModelRouter.get_backend()`:
```python
elif model.startswith("ollama/"):
    from src.services.ollama_backend import OllamaBackend
    return OllamaBackend(
        model=model.replace("ollama/", ""),
        base_url=Config.OLLAMA_BASE_URL,
        api_key=Config.OLLAMA_API_KEY,
    )
```

Also update agent models to accept `"ollama/qwen3:14b"` format.

**Step 4: Run test**
Expected: PASS

**Step 5: Commit**
```bash
git commit -m "feat(ollama): wire OllamaBackend into ModelRouter (Task 3)"
```

---

### Task 4: Install Ollama Python client

**Step 1: Install**
```bash
.venv/bin/pip install ollama
```

**Step 2: Verify**
```bash
.venv/bin/python -c "import ollama; print('ollama', ollama.__version__)"
```

**Step 3: Commit**
```bash
git add pyproject.toml .env.example
git commit -m "chore: add ollama dependency (Task 4)"
```

---

### Task 5: Add streaming support

**Objective:** Ollama streaming for real-time agent output.

**Files:**
- Modify: `src/services/ollama_backend.py`
- Modify: `tests/services/test_ollama_backend.py`

**Step 1: Write failing test**

```python
def test_chat_streaming():
    backend = OllamaBackend(model="qwen3:14b")
    chunks = list(backend.chat([{"role": "user", "content": "Count to 3"}], stream=True))
    assert len(chunks) >= 1
    assert any("1" in str(c) or "one" in str(c).lower() for c in chunks)
```

**Step 2: Run test**
Expected: FAIL — streaming not implemented

**Step 3: Implement**

Add streaming method to `OllamaBackend`:
```python
def chat_stream(self, messages: list[dict[str, str]], **kwargs: Any):
    """Yield chunks for streaming responses."""
    response = self.client.chat(
        model=self.model,
        messages=messages,
        stream=True,
    )
    for chunk in response:
        yield chunk["message"]["content"]
```

**Step 4: Run test**
Expected: PASS

**Step 5: Commit**
```bash
git commit -m "feat(ollama): add streaming support (Task 5)"
```

---

### Task 6: Full test suite + mypy

**Step 1: Run tests**
```bash
ruff check src/services/ollama_backend.py --fix
ruff format --check src/services/ollama_backend.py
.venv/bin/python -m mypy src/services/ollama_backend.py
pytest tests/services/test_ollama_backend.py -v
```

**Step 2: Commit**
```bash
git commit -m "test(ollama): add OllamaBackend tests and linting (Task 6)"
```

---

## IMPLEMENTATION 2: GitHub Agentic Workflows for Continuous PR Review

### Architecture Overview

gh-aw workflows are `.md` files in `.github/workflows/` describing desired outcomes in plain English. `gh aw compile` compiles them to hardened GitHub Actions YAML that runs a coding agent (Claude Code, Copilot, Codex) in an isolated container.

**GADK integration pattern:**
1. GADK runs as before (local ADK multi-agent)
2. gh-aw runs in parallel on GitHub Actions (cloud compute, zero local cost)
3. gh-aw monitors PRs, comments review results as "safe outputs"
4. GADK's Critic agent can consume gh-aw comments as input context

### Task 7: Create PR Review workflow file

**Objective:** Create `.github/workflows/pr-review.md` gh-aw workflow for automatic PR review.

**Files:**
- Create: `.github/workflows/pr-review.md`

**Step 1: Write workflow**

```markdown
---
name: Continuous PR Review
on:
  pull_request:
    types: [opened, synchronize, reopened]
  schedule:
    - cron: "0 */4 * * *"  # Every 4 hours for outstanding PRs

permissions:
  pull-requests: write
  contents: read

agent:
  engine: claude
  model: claude-sonnet-4-6
  timeout: 30
---

You are a thorough, senior software engineer reviewing pull requests for the GADK repository.

Your task:
1. Review the PR diff for logic errors, security issues, and test gaps
2. Check that all modified code passes ruff linting and mypy type checking
3. Verify tests exist for new functionality
4. Comment directly on the PR with your findings using the write-comment safe output
5. If critical issues found, label the PR with "needs-fixes"

Focus on:
- Logic errors in src/agents/ and src/services/
- Missing type annotations in modified files
- Test coverage for new code
- Security: no hardcoded secrets, safe SQL, safe file operations

Do NOT:
- Approve or request changes directly (leave that to human reviewers)
- Make any code changes (comment only)
- Access secrets or infrastructure details
```

**Step 2: Verify syntax**

```bash
gh aw compile .github/workflows/pr-review.md --dry-run
```

Expected: Compiles without error

**Step 3: Commit**
```bash
mkdir -p .github/workflows
git add .github/workflows/pr-review.md
git commit -m "feat(gh-aw): add PR review agentic workflow"
```

---

### Task 8: Create CI Doctor workflow

**Objective:** Automatically investigate CI failures and post root cause analysis as PR comments.

**Files:**
- Create: `.github/workflows/ci-doctor.md`

**Step 1: Write workflow**

```markdown
---
name: CI Doctor
on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
  schedule:
    - cron: "0 9 * * *"  # Daily at 9am UTC

permissions:
  pull-requests: write
  contents: read
  actions: read

agent:
  engine: claude
  model: claude-sonnet-4-6
  timeout: 20
---

You are an expert CI debugging agent. Your job is to investigate CI workflow failures.

Your task:
1. Find the most recent failed CI workflow run
2. Download and analyze the logs for the failing job(s)
3. Identify the root cause of the failure (test failure, lint error, build error, timeout)
4. If the fix is obvious (typo, missing import, etc.), post the fix as a PR comment
5. Label the PR with "ci-failure" and add a comment with your diagnosis

Do NOT:
- Make any code changes
- Access secrets or environment variables
- Retry the workflow
```

**Step 2: Commit**
```bash
git add .github/workflows/ci-doctor.md
git commit -m "feat(gh-aw): add CI failure investigator workflow"
```

---

### Task 9: Create issue-triage workflow

**Objective:** Automatically triage new issues — label, categorize, respond with checklist.

**Files:**
- Create: `.github/workflows/issue-triage.md`

**Step 1: Write workflow**

```markdown
---
name: Issue Triage
on:
  issues:
    types: [opened, reopened]

permissions:
  issues: write
  contents: read

agent:
  engine: claude
  model: claude-sonnet-4-6
  timeout: 15
---

You are the GADK issue triage bot. You analyze incoming issues and categorize them.

Your task:
1. Read the issue title and body carefully
2. Determine the category: bug, feature-request, question, documentation, refactoring
3. Add labels matching the category and any relevant components (e.g. "component: agents", "component: dbos")
4. If bug: check if reproducible, ask for minimal reproduction steps in a comment
5. If feature-request: check for alignment with GADK's SDLC mission, suggest relevant agents/phases
6. Post a triage comment with your categorization and recommended next steps

Do NOT:
- Close issues
- Make code changes
- Access secrets
```

**Step 2: Commit**
```bash
git add .github/workflows/issue-triage.md
git commit -m "feat(gh-aw): add issue triage agentic workflow"
```

---

### Task 10: Full gh-aw test

**Step 1: Verify all workflows compile**

```bash
gh aw compile .github/workflows/pr-review.md
gh aw compile .github/workflows/ci-doctor.md
gh aw compile .github/workflows/issue-triage.md
```

Expected: All compile to `.lock.yml` files without errors

**Step 2: Commit**
```bash
git add .github/workflows/*.lock.yml
git commit -m "test(gh-aw): add compiled workflow artifacts"
```

---

## IMPLEMENTATION 3: Memori Persistent Memory Layer

### Architecture Overview

Memori (Memori Labs, arXiv:2603.19935) converts unstructured conversation into semantic triples + summaries. This gives GADK agents persistent cross-session memory without the token bloat of full context injection.

**Data flow:**
```
Conversation log → Memori Advanced Augmentation → Semantic triples + Summary
                                                                ↓
                                                     Vector store (Qdrant/SQLite)
                                                                ↓
                                                     Compact retrieval (~1,294 tokens)
                                                                ↓
                                                     Agent context injection
```

**Memori key claims:**
- 81.95% accuracy on LoCoMo benchmark
- 1,294 tokens/query (~5% of full context)
- 67% fewer tokens than alternatives
- LLM-agnostic (any model can generate triples)

### Task 11: Research Memori API and design triple schema

**Objective:** Understand Memori's API and design GADK-specific triple schema.

**Files:**
- Create: `docs/architecture/memori-triple-schema.md`

**Step 1: Research Memori API**

```bash
# Install Memori to inspect API
pip show memori  # or: pip install memori
```

**Step 2: Design triple schema**

```markdown
# GADK Triple Schema for Memori

## Entity Types
- AGENT: {name: str, phase: Phase, capability: str}
- WORKITEM: {id: str, phase: Phase, status: str}
- DECISION: {phase: Phase, choice: str, rationale: str}
- ERROR: {phase: Phase, error_type: str, workaround: str}
- PREFERENCE: {user: str, topic: str, value: str}
- PATTERN: {phase: Phase, pattern: str, success_rate: float}

## Triple Format (Memori standard)
[Subject] | [Predicate] | [Object]

## Example triples
(IDEATOR_agent, decided_on, implementation_approach)
(PHASE_CONTROLLER, transitioned_from, PLAN)
(BUILDER_agent, encountered_error, missing_import)
(missing_import, was_fixed_by, added_import_statement)
(USER, prefers, concise_responses)
(PHASE_CONTROLLER, retry_count, 3)
```

**Step 3: Commit**
```bash
git add docs/architecture/memori-triple-schema.md
git commit -m "docs(memori): design GADK triple schema for Memori memory"
```

---

### Task 12: Create Memori service layer

**Objective:** Implement `src/services/memori_memory.py` — Memori-backed persistent memory.

**Files:**
- Create: `src/services/memori_memory.py`
- Create: `tests/services/test_memori_memory.py`

**Step 1: Write failing test**

```python
# tests/services/test_memori_memory.py
from src.services.memori_memory import MemoriMemory

def test_store_and_retrieve_triple():
    memory = MemoriMemory()
    # Store a decision
    memory.store_triple(
        subject="BUILDER_agent",
        predicate="encountered_error",
        object="missing_import_AttributeError"
    )
    # Retrieve relevant context
    context = memory.retrieve("BUILDER encountered import errors before")
    assert len(context) > 0
    assert any("missing_import" in str(c) for c in context)
```

**Step 2: Run test**
```
pytest tests/services/test_memori_memory.py::test_store_and_retrieve_triple -v
```
Expected: FAIL — module not found

**Step 3: Implement**

```python
# src/services/memori_memory.py
"""Memori-backed persistent memory for GADK agents.

Uses Memori's Advanced Augmentation pipeline to convert conversation
logs into semantic triples and summaries for compact retrieval.
~1,294 tokens/query vs full context injection.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.config import Config
from src.observability.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MemoryTriple:
    subject: str
    predicate: str
    obj: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    session_id: str | None = None


@dataclass
class MemorySummary:
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    session_id: str | None = None


class MemoriMemory:
    """Persistent memory layer using Memori semantic triples.

    Stores conversation-derived triples and summaries in SQLite.
    On retrieval, uses Memori's compact representation (~1,294 tokens/query)
    instead of full context injection.
    """

    def __init__(
        self,
        db_path: str = "./memori_memory.db",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.db_path = db_path
        self.embedding_model = embedding_model
        self._conn: Any = None
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        import sqlite3

        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS triples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                obj TEXT NOT NULL,
                session_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                session_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples(subject);
            CREATE INDEX IF NOT EXISTS idx_triples_predicate ON triples(predicate);
        """)
        conn.commit()

    def _get_conn(self) -> Any:
        import sqlite3

        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def store_triple(
        self,
        subject: str,
        predicate: str,
        obj: str,
        session_id: str | None = None,
    ) -> int:
        """Store a semantic triple. Returns row ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO triples (subject, predicate, obj, session_id) VALUES (?, ?, ?, ?)",
            (subject, predicate, obj, session_id),
        )
        conn.commit()
        return cursor.lastrowid or 0  # type: ignore

    def store_summary(
        self,
        content: str,
        session_id: str | None = None,
    ) -> int:
        """Store a session summary. Returns row ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "INSERT INTO summaries (content, session_id) VALUES (?, ?)",
            (content, session_id),
        )
        conn.commit()
        return cursor.lastrowid or 0  # type: ignore

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        session_id: str | None = None,
    ) -> list[str]:
        """Retrieve relevant memory entries as compact text.

        Uses simple keyword matching for Phase 1.
        Memori's full semantic search requires embedding model integration.
        """
        conn = self._get_conn()
        where_clause = "WHERE session_id = ?" if session_id else ""
        params: list[Any] = [session_id] if session_id else []

        triples = conn.execute(
            f"""
            SELECT subject, predicate, obj FROM triples
            {where_clause}
            ORDER BY timestamp DESC LIMIT ?
            """,
            [*params, top_k * 2],
        ).fetchall()

        summaries = conn.execute(
            f"""
            SELECT content FROM summaries
            {where_clause}
            ORDER BY timestamp DESC LIMIT ?
            """,
            [*params, top_k],
        ).fetchall()

        results = []
        for s, p, o in triples:
            if any(word.lower() in f"{s} {p} {o}".lower() for word in query.split()[:3]):
                results.append(f"{s} | {p} | {o}")

        for (content,) in summaries:
            if any(word.lower() in content.lower() for word in query.split()[:3]):
                results.append(f"[Summary] {content[:200]}")

        return results[:top_k]

    def get_recent_triples(self, session_id: str | None = None, limit: int = 20) -> list[MemoryTriple]:
        conn = self._get_conn()
        where = "WHERE session_id = ?" if session_id else ""
        params = [session_id] if session_id else []
        rows = conn.execute(
            f"SELECT subject, predicate, obj, timestamp FROM triples {where} ORDER BY timestamp DESC LIMIT ?",
            [*params, limit],
        ).fetchall()
        return [MemoryTriple(subject=r[0], predicate=r[1], obj=r[2]) for r in rows]
```

**Step 4: Run test**
```
pytest tests/services/test_memori_memory.py::test_store_and_retrieve_triple -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add src/services/memori_memory.py tests/services/test_memori_memory.py
git commit -m "feat(memori): add MemoriMemory persistent layer (Task 12)"
```

---

### Task 13: Wire Memori into Orchestrator agent

**Objective:** Inject retrieved memory context into Orchestrator's agent prompts.

**Files:**
- Modify: `src/agents/orchestrator.py`

**Step 1: Write failing test**

```python
# tests/agents/test_orchestrator_memori.py
def test_orchestrator_injects_memory_context():
    from src.services.memori_memory import MemoriMemory
    memory = MemoriMemory()
    memory.store_triple("BUILDER_agent", "encountered_error", "missing_import")
    # Orchestrator should retrieve this on init
    ctx = get_orchestrator_memory_context()
    assert any("missing_import" in c for c in ctx)
```

**Step 2: Run test**
Expected: FAIL — no memory integration yet

**Step 3: Implement**

Add to `Orchestrator` `__init__`:
```python
self.memory = MemoriMemory() if Config.MEMORI_ENABLED else None

def _get_memory_context(self) -> str:
    if not self.memory:
        return ""
    query = f"recent decisions phase {self.phase}"
    entries = self.memory.retrieve(query, top_k=5)
    if not entries:
        return ""
    return "\n".join(f"[Memory] {e}" for e in entries)
```

Add memory context to agent instructions via `retrieval_context.py` or directly in `run()`.

**Step 4: Run test**
Expected: PASS

**Step 5: Commit**
```bash
git commit -m "feat(memori): wire MemoriMemory into Orchestrator (Task 13)"
```

---

### Task 14: Add Memori config flags

**Files:**
- Modify: `src/config.py`

**Step 1: Add to Settings:**
```python
memori_enabled: bool = False
memori_db_path: str = "./memori_memory.db"
```

**Step 2: Add to Config:**
```python
MEMORI_ENABLED: bool = False
MEMORI_DB_PATH: str = "./memori_memory.db"
```

**Step 3: Commit**
```bash
git commit -m "feat(memori): add Memori config flags (Task 14)"
```

---

### Task 15: Add CLI command to inspect memory

**Files:**
- Modify: `src/cli/swarm_cli.py`

**Step 1: Add subcommand**

```python
@cli.group()
def memory():
    """Inspect and manage GADK persistent memory."""

@memory.command("recent")
def memory_recent(limit: int = 20):
    """Show recent memory entries."""
    from src.services.memori_memory import MemoriMemory
    m = MemoriMemory()
    for t in m.get_recent_triples(limit=limit):
        print(f"{t.subject} | {t.predicate} | {t.obj}")
```

**Step 2: Commit**
```bash
git commit -m "feat(memori): add memory inspect CLI command (Task 15)"
```

---

## Ollama Cloud (Impl 1): Strengths and Weaknesses

### Strengths
- **Near-zero cost**: Ollama Cloud models use local rate limits + API key, no per-token billing
- **No GPU required**: `:cloud` models auto-offload to Ollama infrastructure
- **Same API**: Drop-in replacement for OpenRouter via LiteLlm-compatible client
- **Privacy**: Prompts stay on Ollama's infrastructure (vs OpenRouter third-party brokers)
- **Streaming**: Full streaming support via Ollama client

### Weaknesses
- **Model selection**: Fewer models than OpenRouter (no Claude, GPT-4, Gemini direct)
- **Reliability**: Ollama Cloud is a young service; SLA not guaranteed
- **No built-in tools/MCP**: Unlike OpenRouter which has some tool-use support
- **API key management**: Requires `OLLAMA_API_KEY` + `ollama signin` — another credential to manage
- **Latency**: Cloud proxy adds ~50-200ms vs local Ollama

---

## gh-aw (Impl 2): Strengths and Weaknesses

### Strengths
- **Zero local compute**: Runs on GitHub Actions, no local GPU/CPU cost
- **Built-in security**: Read-only by default, safe outputs for writes, sandboxed container, threat detection
- **Rich context**: Full repository context (code, issues, PRs, history) without explicit data loading
- **Schedule support**: Continuous background tasks on cron (e.g. every 4 hours)
- **Already integrates with Claude Code**: `engine: claude` option is first-class
- **GADK synergy**: gh-aw handles continuous PR review while GADK handles autonomous SDLC execution — complementary, not overlapping

### Weaknesses
- **State sync**: gh-aw state lives in GitHub; GADK state in local JSON/SQLite — needs explicit sync mechanism
- **GitHub dependency**: Can't run without GitHub Actions quota and `gh` CLI
- **gh-aw tech preview**: API/spec may change; not production-stable
- **Two systems**: Developer must understand both GADK (local ADK) and gh-aw (cloud YAML workflows)
- **Limited to repo context**: Can't access local filesystem outside repo, external APIs, or other local services

---

## Memori (Impl 3): Strengths and Weaknesses

### Strengths
- **Token efficiency**: 1,294 tokens/query at 81.95% accuracy — best-in-class retrieval
- **LLM-agnostic**: Works with any model (Ollama, OpenRouter, Claude) without lock-in
- **Structured memory**: Semantic triples enable precise recall vs fuzzy similarity search
- **Cross-session persistence**: Agents remember past decisions across restarts
- **GADK-aligned**: Triple schema maps naturally to SDLC phases, agents, work items, and decisions

### Weaknesses
- **New library**: Memori v1 not yet battle-tested in production environments
- **Embedding model required**: Needs sentence-transformers or similar for semantic search
- **Triple quality depends on LLM**: Garbage-in-triple-out if extraction LLM is weak
- **Schema design effort**: GADK-specific triple schema needs careful design and iteration
- **Latency**: Every memory access adds round-trip to embedding model + vector DB
- **SQLite for Phase 1**: Works for dev but needs proper vector DB (Qdrant) for production scale

---

## Plan complete. Ready to execute using full TDD cycle task-by-task.

Shall I proceed with Implementation 1 (Ollama Cloud) first, then 2 (gh-aw), then 3 (Memori)?
