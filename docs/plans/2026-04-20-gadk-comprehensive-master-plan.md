# GADK Comprehensive Implementation Plan: v0.1.0 → v2.0

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
> Use `.venv/bin/python` for all commands in this plan.

**Goal:** Evolve GADK from a working multi-agent SDLC shell (v0.1.0) into a fully autonomous cognitive foundry (v2.0) by implementing the roadmap through all 5 phases — Phase 2 Intelligence, Phase 3 Scale, Phase 4 Autonomy, and Phase 5 Ecosystem.

**Architecture:** Google ADK remains the sole control plane. All integrations (PydanticAI, LangGraph, LlamaIndex, Pydantic) are supporting layers. Phase transitions are managed by PhaseController. State is atomic JSON + SQLite. Self-prompting loop provides gap-driven autonomous task generation.

**Tech Stack:** Python 3.11, Google ADK, LiteLLM/OpenRouter, PydanticAI 0.0.30+, LangGraph 0.2+, LlamaIndex 0.11+, Pydantic 2.5+, SQLite, pytest, ruff, mypy.

**Current Baseline:** 344 tests pass, 1 failing (swarm_e2e), 16 skipped, 22 import errors when not using venv. Use `.venv/bin/python` for all test runs.

**Critical Path:** Phase 2.1 (PydanticAI) → 2.2 (LangGraph) → 2.3 (Vector) → Phase 3 (Scale) → Phase 4 (Autonomy) → Phase 5 (Ecosystem).

---

## PHASE 0: Pre-flight — Fix Baseline Tests

### Task 0.1: Fix swarm_e2e Test Failure

**Objective:** Get all tests to green before starting new work.

**Files:**
- Modify: `tests/test_swarm_e2e.py`

**Step 1: Identify root cause**

Run:
```bash
cd /home/westonaaron675/gadk
.venv/bin/python -m pytest tests/test_swarm_e2e.py::test_swarm_state_update_on_ideation -v --tb=short 2>&1
```

Expected: FAIL with specific assertion or state error.

**Step 2: Fix the failing assertion or mock**

Fix the identified issue. Common causes: state not persisted, mock returning wrong shape, async timing issue.

**Step 3: Verify all tests pass**

Run: `.venv/bin/python -m pytest -q --tb=no 2>&1 | tail -5`
Expected: `344 passed, 16 skipped`

**Step 4: Commit**

```bash
git add tests/test_swarm_e2e.py
git commit -m "fix: resolve swarm_e2e test failure"
```

---

## PHASE 1: Foundation Verification (already complete — tasks here validate and document)

### Task 1.1: Document Phase 1 completion in README

**Objective:** Lock in Phase 1 as done and update version markers.

**Files:**
- Modify: `README.md`, `CLAUDE.md`

**Step 1: Update version to v0.1.0**

Set current version to v0.1.0 with all Phase 1 checkboxes ticked.

**Step 2: Verify all foundation docs are consistent**

Check: README.md, CLAUDE.md, docs/product/roadmap.md all agree on v0.1.0 state.

---

## PHASE 2: Intelligence (v0.2.0–v0.5.0)

### 2.1 PydanticAI Integration (Weeks 1-4)

#### Task 2.1.1: Verify pydantic-ai in venv

**Objective:** Confirm pydantic-ai 0.0.30+ is installed and importable.

**Files:**
- None (verification only)

Run: `.venv/bin/python -c "import pydantic_ai; print(pydantic_ai.__version__)" 2>&1`
Expected: `0.0.30` or higher

#### Task 2.1.2: Complete `AgentDecision` base model

**Objective:** Ensure all agents use the Pydantic `AgentDecision` contract.

**Files:**
- Modify: `src/services/agent_contracts.py`
- Modify: `src/services/agent_decisions.py`
- Create: `tests/services/test_agent_contracts.py`

**Step 1: Review existing agent_contracts.py**

Read `src/services/agent_contracts.py` (128 lines total). Confirm these models exist:
- `DelegationDecision` ✅
- `TaskProposal` ✅
- `ReviewVerdict` ✅
- `SpecialistRegistration` (partial)

**Step 2: Add missing `AgentDecision` base model**

Add to `src/services/agent_contracts.py`:
```python
class ActionType(str, Enum):
    DELEGATE = "delegate"
    IMPLEMENT = "implement"
    REVIEW = "review"
    WAIT = "wait"
    ESCALATE = "escalate"

class AgentDecision(BaseModel):
    """Structured decision output for all agents."""
    model_config = ConfigDict(extra="forbid")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    action: ActionType
    payload: dict[str, Any] = Field(default_factory=dict)
    estimated_cost_usd: float = Field(ge=0.0)
    required_approvals: list[str] = Field(default_factory=list)
```

**Step 3: Add `BuildBrief` contract**

Add to `src/services/agent_contracts.py`:
```python
class BuildBrief(BaseModel):
    """Validated build brief for the Builder agent."""
    model_config = ConfigDict(extra="forbid")
    task_id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    adr_path: str | None = None
    files_to_modify: list[str] = Field(default_factory=list)
    estimated_tokens: int = 0
```

**Step 4: Write contract validation tests**

Create `tests/services/test_agent_contracts.py`:
```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.services.agent_contracts import (
    AgentDecision, ActionType, DelegationDecision,
    TaskProposal, ReviewVerdict, BuildBrief, SpecialistRegistration,
)

def test_delegation_decision_valid():
    d = DelegationDecision(target_agent="Builder", reason="needs code")
    assert d.target_agent == "Builder"
    assert d.required_capabilities == []

def test_delegation_decision_rejects_empty():
    with pytest.raises(ValidationError):
        DelegationDecision(target_agent="", reason="")

def test_task_proposal_requires_fields():
    with pytest.raises(ValidationError):
        TaskProposal(title="", summary="", description="", recommended_agent="")

def test_review_verdict_status_values():
    v = ReviewVerdict(status="pass", summary="looks good")
    assert v.status == "pass"

def test_build_brief_optional_adr():
    brief = BuildBrief(task_id="t1", title="Fix bug", description="...", acceptance_criteria=[])
    assert brief.adr_path is None

def test_agent_decision_confidence_bounds():
    with pytest.raises(ValidationError):
        AgentDecision(confidence=1.5, reasoning="too confident", action=ActionType.WAIT)

def test_agent_decision_all_actions():
    for action in ActionType:
        d = AgentDecision(confidence=0.5, reasoning="test", action=action)
        assert d.action == action
```

**Step 5: Run contract tests**

Run: `.venv/bin/python -m pytest tests/services/test_agent_contracts.py -v`
Expected: 7 passed

**Step 6: Commit**

```bash
git add src/services/agent_contracts.py tests/services/test_agent_contracts.py
git commit -m "feat(contracts): add AgentDecision and BuildBrief models"
```

#### Task 2.1.3: Migrate Orchestrator to typed DelegationDecision

**Objective:** Replace free-form routing strings with typed DelegationDecision.

**Files:**
- Modify: `src/agents/orchestrator.py`

**Step 1: Read orchestrator.py**

```bash
cat src/agents/orchestrator.py
```

**Step 2: Update delegate() to return DelegationDecision**

Change orchestrator to use `choose_delegate()` from agent_decisions.py and return typed decisions.

**Step 3: Write integration test**

Add test to `tests/agents/test_orchestrator.py` (create if not exists):
```python
def test_delegate_returns_typed_decision():
    from src.services.agent_decisions import choose_delegate
    result = choose_delegate("fix the login bug", ["Ideator", "Builder", "Critic"])
    assert isinstance(result, DelegationDecision)
    assert result.target_agent in ["Ideator", "Builder", "Critic"]
```

**Step 4: Run orchestrator tests**

```bash
.venv/bin/python -m pytest tests/agents/ -v
```

**Step 5: Commit**

```bash
git add src/agents/orchestrator.py tests/agents/test_orchestrator.py
git commit -m "feat(orchestrator): typed DelegationDecision routing"
```

#### Task 2.1.4: Migrate Ideator to structured TaskProposal

**Objective:** Ensure Ideator always emits validated TaskProposal.

**Files:**
- Modify: `src/agents/ideator.py`
- Modify: `tests/agents/test_ideator.py` (if exists)

**Step 1: Read ideator.py**

Inspect current Ideator implementation.

**Step 2: Add structured output validation**

Use `parse_task_proposal` from `src/services/structured_output.py` to validate Ideator output.

**Step 3: Update Ideator agent instruction to require structured output**

Add to system prompt: "Always respond with a valid TaskProposal JSON schema."

**Step 4: Add test**

```python
def test_ideator_produces_valid_task_proposal():
    # Mock LLM returning structured output
    result = propose_task("user wants a login screen")
    assert isinstance(result, TaskProposal)
    assert result.title
    assert result.recommended_agent in ["Builder", "Architect", "Ideator"]
```

**Step 5: Run tests**

```bash
.venv/bin/python -m pytest tests/agents/test_ideator.py -v
```

**Step 6: Commit**

```bash
git add src/agents/ideator.py tests/agents/test_ideator.py
git commit -m "feat(ideator): structured TaskProposal output"
```

#### Task 2.1.5: Migrate Critic to typed ReviewVerdict

**Objective:** Critic always returns pass/retry/block typed verdict.

**Files:**
- Modify: `src/agents/critic.py`
- Modify: `tests/agents/test_critic.py` (if exists)

**Step 1: Read critic.py**

**Step 2: Ensure parse_review_verdict validates Critic output**

Ensure Critic uses `normalize_review_verdict` before returning.

**Step 3: Update Critic system prompt**

Add: "Return a ReviewVerdict with status in ['pass', 'retry', 'block']."

**Step 4: Write tests**

```python
def test_critic_returns_pass_verdict():
    result = critic_review(code="def foo(): pass", criteria=["has tests"])
    assert isinstance(result, ReviewVerdict)
    assert result.status == "pass"

def test_critic_returns_retry_with_concerns():
    result = critic_review(code="", criteria=["not empty"])
    assert isinstance(result, ReviewVerdict)
    assert result.status == "retry"
    assert len(result.concerns) > 0
```

**Step 5: Run tests**

```bash
.venv/bin/python -m pytest tests/agents/test_critic.py -v
```

**Step 6: Commit**

```bash
git add src/agents/critic.py tests/agents/test_critic.py
git commit -m "feat(critic): typed ReviewVerdict output"
```

#### Task 2.1.6: Migrate Builder to structured BuildBrief

**Objective:** Builder receives typed BuildBrief, not free-form text.

**Files:**
- Modify: `src/agents/builder.py`
- Create: `tests/agents/test_builder.py`

**Step 1: Read builder.py**

**Step 2: Accept BuildBrief as input**

Builder should validate incoming BuildBrief. Add:
```python
def build_from_brief(brief: BuildBrief) -> dict:
    """Execute build from typed brief."""
    # implementation
    pass
```

**Step 3: Write tests**

```python
def test_builder_accepts_build_brief():
    brief = BuildBrief(
        task_id="t1", title="Add tests", description="...",
        acceptance_criteria=["test passes"], files_to_modify=["src/foo.py"]
    )
    result = build_from_brief(brief)
    assert result["status"] in ["success", "partial"]
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/agents/test_builder.py -v
```

**Step 5: Commit**

```bash
git add src/agents/builder.py tests/agents/test_builder.py
git commit -m "feat(builder): BuildBrief input contract"
```

### 2.2 LangGraph Workflow Engine (Weeks 3-6)

#### Task 2.2.1: Add langgraph dependency verification

**Objective:** Confirm langgraph is installed and functional.

**Files:**
- None (verification)

Run: `.venv/bin/python -c "import langgraph; from langgraph.graph import StateGraph; print('langgraph ok')" 2>&1`
Expected: `langgraph ok`

#### Task 2.2.2: Read existing workflow_graphs.py

**Objective:** Understand current workflow implementation.

**Files:**
- Read: `src/services/workflow_graphs.py`

#### Task 2.2.3: Implement bounded review-rework state machine

**Objective:** Replace ad hoc review loops with LangGraph state machine.

**Files:**
- Modify: `src/services/workflow_graphs.py`

**Step 1: Define WorkflowState**

```python
from typing import TypedDict
from src.services.sdlc_phase import Phase

class WorkflowState(TypedDict):
    work_item_id: str
    phase: Phase
    attempts: int
    max_attempts: int
    verdict: ReviewVerdict | None
    approved: bool | None
    evidence: dict
```

**Step 2: Build review graph**

```python
from langgraph.graph import StateGraph, END

def build_review_graph():
    graph = StateGraph(WorkflowState)
    graph.add_node("review", critic_review_node)
    graph.add_node("evaluate", evaluate_verdict_node)
    graph.add_node("rework", builder_rework_node)
    graph.add_node("approve", governor_approve_node)

    graph.set_entry_point("review")
    graph.add_edge("review", "evaluate")

    def should_rework(state: WorkflowState) -> str:
        if state["verdict"] and state["verdict"].status == "retry":
            if state["attempts"] < state["max_attempts"]:
                return "rework"
        return "approve"

    graph.add_conditional_edges(
        "evaluate",
        should_rework,
        {"rework": "rework", "approve": "approve"}
    )
    graph.add_edge("rework", "review")
    graph.add_edge("approve", END)
    return graph.compile()
```

**Step 3: Implement nodes**

```python
async def critic_review_node(state: WorkflowState) -> WorkflowState:
    # Use Critic agent to review current work item
    # Return updated state with verdict
    pass

async def evaluate_verdict_node(state: WorkflowState) -> WorkflowState:
    # Evaluate the critic verdict and set approved flag
    pass

async def builder_rework_node(state: WorkflowState) -> WorkflowState:
    # Increment attempts and route back to Builder for rework
    state["attempts"] += 1
    return state

async def governor_approve_node(state: WorkflowState) -> WorkflowState:
    state["approved"] = True
    return state
```

**Step 4: Write tests**

Create `tests/services/test_workflow_graphs.py`:
```python
import pytest
from src.services.workflow_graphs import build_review_graph, WorkflowState
from src.services.sdlc_phase import Phase

def test_review_graph_compiles():
    graph = build_review_graph()
    assert graph is not None

def test_review_graph_initial_state():
    state = WorkflowState(
        work_item_id="t1", phase=Phase.REVIEW, attempts=0,
        max_attempts=3, verdict=None, approved=None, evidence={}
    )
    assert state["attempts"] == 0
    assert state["approved"] is None

def test_bounded_retry_stops_at_max():
    graph = build_review_graph()
    # Run with attempts=3, max_attempts=3, verdict=retry
    # Should route to approve, not rework
    pass
```

**Step 5: Run workflow tests**

```bash
.venv/bin/python -m pytest tests/services/test_workflow_graphs.py -v
```

**Step 6: Commit**

```bash
git add src/services/workflow_graphs.py tests/services/test_workflow_graphs.py
git commit -m "feat(workflow): bounded review-rework LangGraph state machine"
```

#### Task 2.2.4: Add conditional branching support

**Objective:** Support multi-path workflows (PLAN→ARCHITECT vs PLAN→IMPLEMENT direct).

**Files:**
- Modify: `src/services/workflow_graphs.py`

**Step 1: Add branch node**

```python
def build_planner_graph():
    """Multi-path planning: direct to implement or full architecture."""
    graph = StateGraph(WorkflowState)
    graph.add_node("triage", triage_node)
    graph.add_node("plan_full", architect_plan_node)
    graph.add_node("plan_fast", fast_implement_node)

    graph.set_entry_point("triage")
    graph.add_conditional_edges(
        "triage",
        lambda s: "fast" if s.get("fast_track") else "full",
        {"fast": "plan_fast", "full": "plan_full"}
    )
    return graph.compile()
```

**Step 2: Write test**

```python
def test_triage_fast_track():
    state = WorkflowState(work_item_id="t1", phase=Phase.PLAN, attempts=0, max_attempts=3, verdict=None, approved=None, evidence={})
    state["fast_track"] = True
    # Verify routes to plan_fast
    pass

def test_triage_full_path():
    state = WorkflowState(work_item_id="t1", phase=Phase.PLAN, attempts=0, max_attempts=3, verdict=None, approved=None, evidence={})
    state["fast_track"] = False
    # Verify routes to plan_full
    pass
```

**Step 3: Run tests**

```bash
.venv/bin/python -m pytest tests/services/test_workflow_graphs.py -v
```

**Step 4: Commit**

```bash
git add src/services/workflow_graphs.py tests/services/test_workflow_graphs.py
git commit -m "feat(workflow): conditional branching for fast/full paths"
```

#### Task 2.2.5: Add parallel execution paths

**Objective:** Support parallel BUILD_STEP_N tasks.

**Files:**
- Modify: `src/services/workflow_graphs.py`

**Step 1: Add parallel executor node**

```python
async def parallel_build_node(state: WorkflowState) -> WorkflowState:
    """Execute multiple build tasks in parallel."""
    tasks = state.get("parallel_tasks", [])
    results = await asyncio.gather(*[execute_build_task(t) for t in tasks])
    state["evidence"]["parallel_results"] = results
    return state
```

**Step 2: Write test**

**Step 3: Run tests and commit**

### 2.3 Vector Retrieval System (Weeks 5-8)

#### Task 2.3.1: Verify sqlite-vec backend works

**Objective:** Confirm vector retrieval is operational.

**Files:**
- Read: `src/services/vector_index.py`
- Read: `src/services/embedder.py`

**Step 1: Check embedder and vector index**

Run: `.venv/bin/python -c "from src.services.vector_index import SqliteVecBackend; print('vec ok')" 2>&1`

#### Task 2.3.2: Implement code indexing pipeline

**Objective:** Index codebase into vector store for semantic search.

**Files:**
- Create: `src/services/code_indexer.py`
- Create: `tests/services/test_code_indexer.py`

**Step 1: Create code indexer**

```python
"""Code indexing pipeline for semantic search."""
from __future__ import annotations

from pathlib import Path
from src.services.embedder import build_default_embedder

IGNORED_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", ".mypy_cache", ".ruff_cache"}
IGNORED_EXTS = {".pyc", ".so", ".dll", ".dylib", ".jpg", ".png", ".gif"}

def index_repository(repo_path: Path) -> dict:
    """Index all code files in repository."""
    embedder = build_default_embedder()
    chunks = []

    for file_path in repo_path.rglob("*"):
        if file_path.is_file():
            if any(ignored in file_path.parts for ignored in IGNORED_DIRS):
                continue
            if file_path.suffix in IGNORED_EXTS:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if len(content) > 50:
                    chunks.append({"path": str(file_path), "content": content[:2000]})
            except Exception:
                continue

    # Batch embed and store
    # ... (implementation)
    return {"indexed_files": len(chunks), "status": "ok"}
```

**Step 2: Write tests**

```python
from src.services.code_indexer import index_repository
from pathlib import Path

def test_indexer_excludes_ignored_dirs(tmp_path):
    ignored = tmp_path / ".git" / "config"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("ignored content")
    result = index_repository(tmp_path)
    assert "indexed_files" in result
```

**Step 3: Run tests**

```bash
.venv/bin/python -m pytest tests/services/test_code_indexer.py -v
```

**Step 4: Commit**

```bash
git add src/services/code_indexer.py tests/services/test_code_indexer.py
git commit -m "feat(indexer): code indexing pipeline for vector retrieval"
```

#### Task 2.3.3: Add semantic search API

**Objective:** Enable natural language code search.

**Files:**
- Modify: `src/services/retrieval_context.py`

**Step 1: Add semantic search**

```python
async def semantic_search(query: str, top_k: int = 5) -> list[RetrievedChunk]:
    """Search codebase using natural language query."""
    embedder = build_default_embedder()
    query_embedding = embedder.embed([query])

    index = VectorIndex.from_backend()
    results = index.search(query_embedding, top_k=top_k)
    return results
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

#### Task 2.3.4: Integrate embedding quota tracking

**Objective:** Ensure daily token cap is enforced.

**Files:**
- Read: `src/services/embed_quota.py`

**Step 1: Verify EmbedQuota works**

```bash
.venv/bin/python -c "from src.services.embed_quota import EmbedQuota; q = EmbedQuota(); print(q.get_remaining())" 2>&1
```

**Step 2: Add quota check to code indexer**

**Step 3: Write test for quota enforcement**

**Step 4: Run tests and commit**

### 2.4 Enhanced Quality Gates (Weeks 7-10)

#### Task 2.4.1: Add TestCoverageGate

**Objective:** Gate transitions on test coverage thresholds.

**Files:**
- Create: `src/services/gates/test_coverage_gate.py` (or add to `quality_gates.py`)
- Create: `tests/services/test_quality_gates.py`

**Step 1: Implement gate**

```python
class TestCoverageGate(QualityGate):
    name = "test_coverage"
    blocking = True
    applies_to = frozenset({Phase.REVIEW})

    def __init__(self, min_coverage: float = 65.0) -> None:
        self._min_coverage = min_coverage

    def evaluate(self, item: WorkItem) -> GateResult:
        # Run coverage and parse report
        # Return GateResult with evidence
        pass
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

#### Task 2.4.2: Implement CriticReviewGate

**Objective:** Formalize the critic review gate with typed verdict.

**Files:**
- Modify: `src/services/quality_gates.py`

**Step 1: Add gate**

```python
class CriticReviewGate(QualityGate):
    name = "critic_review"
    blocking = True
    applies_to = frozenset({Phase.REVIEW})

    def evaluate(self, item: WorkItem) -> GateResult:
        from src.services.agent_decisions import normalize_review_verdict
        verdict = normalize_review_verdict(item.payload.get("verdict", {}))
        return GateResult(
            gate=self.name,
            passed=verdict.status in ("pass", "retry"),
            blocking=True,
            evidence={"status": verdict.status, "concerns": verdict.concerns}
        )
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

#### Task 2.4.3: Add parallel gate execution

**Objective:** Run independent gates concurrently.

**Files:**
- Modify: `src/services/phase_controller.py`

**Step 1: Identify independent gate groups**

Lint, typecheck, and content guard can run in parallel.

**Step 2: Implement parallel evaluation**

```python
async def evaluate_gates_parallel(gates: list[QualityGate], item: WorkItem) -> list[GateResult]:
    """Run independent gates in parallel."""
    import asyncio
    tasks = [g.evaluate_async(item) if hasattr(g, 'evaluate_async') else asyncio.to_thread(g.evaluate, item) for g in gates]
    return await asyncio.gather(*tasks)
```

**Step 3: Write tests**

**Step 4: Run tests and commit**

### 2.5 Self-Prompting v2 (Weeks 9-12)

#### Task 2.5.1: Add gap detection algorithms

**Objective:** Enhanced coverage and pattern gap detection.

**Files:**
- Modify: `src/services/self_prompt.py`

**Step 1: Read current self_prompt.py**

**Step 2: Add coverage gap detection**

```python
def detect_coverage_gaps(events: list[dict]) -> list[str]:
    """Identify phases with low coverage."""
    # Analyze events.jsonl for untested paths
    pass

def detect_stale_backlog(state: dict) -> list[str]:
    """Find work items stuck in same phase > threshold."""
    pass
```

**Step 3: Write tests and commit**

#### Task 2.5.2: Add prompt effectiveness tracking

**Objective:** Track which prompts produce good outcomes.

**Files:**
- Modify: `src/services/self_prompt.py`

**Step 1: Add effectiveness scoring**

**Step 2: Implement A/B variant generation**

**Step 3: Write tests and commit**

---

## PHASE 3: Scale (v0.6.0–v0.8.0)

### 3.1 Fleet Manager

#### Task 3.1.1: Design fleet data model

**Objective:** Multi-repository registry schema.

**Files:**
- Create: `src/services/fleet_manager.py`
- Create: `src/models/fleet.py`

```python
from pydantic import BaseModel

class RepositoryConfig(BaseModel):
    name: str
    url: str
    default_branch: str = "main"
    enabled: bool = True
    owned_by: str | None = None

class FleetRegistry:
    """Registry of all repositories under management."""
    def __init__(self):
        self._repos: dict[str, RepositoryConfig] = {}

    def register(self, repo: RepositoryConfig) -> None:
        self._repos[repo.name] = repo

    def get(self, name: str) -> RepositoryConfig | None:
        return self._repos.get(name)

    def list_all(self) -> list[RepositoryConfig]:
        return list(self._repos.values())
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

#### Task 3.1.2: Implement cross-repo dependency tracking

**Objective:** Track dependencies between repositories.

**Files:**
- Modify: `src/services/fleet_manager.py`

**Step 1: Add dependency graph**

```python
from collections import defaultdict

class DependencyGraph:
    def __init__(self):
        self._deps: dict[str, set[str]] = defaultdict(set)

    def add_dependency(self, repo: str, depends_on: str) -> None:
        self._deps[repo].add(depends_on)

    def get_dependents(self, repo: str) -> list[str]:
        return [r for r, deps in self._deps.items() if repo in deps]

    def topological_sort(self) -> list[str]:
        # Return repos in dependency order
        pass
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

#### Task 3.1.3: Add bulk operations framework

**Objective:** Run operations across multiple repos.

**Files:**
- Modify: `src/services/fleet_manager.py`

**Step 1: Add bulk operation**

```python
async def bulk_operation(
    self,
    selector: FleetSelector,
    operation: str,
    **kwargs
) -> dict[str, Any]:
    """Execute operation on selected repos."""
    repos = self.select(selector)
    results = await asyncio.gather(*[self.execute_op(r, operation, **kwargs) for r in repos])
    return {"total": len(repos), "results": dict(zip([r.name for r in repos], results))}
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

### 3.2 Web Dashboard

#### Task 3.2.1: Create FastAPI backend scaffold

**Objective:** API for dashboard data.

**Files:**
- Create: `src/api/dashboard_api.py`

```python
from fastapi import FastAPI

app = FastAPI(title="GADK Dashboard API")

@app.get("/api/status")
async def get_status():
    # Return swarm health, active agents, queue depth
    pass

@app.get("/api/work-items")
async def list_work_items():
    # Return all work items with phase info
    pass
```

**Step 1: Install fastapi**

```bash
.venv/bin/pip install fastapi uvicorn 2>&1 | tail -3
```

**Step 2: Write tests with TestClient**

**Step 3: Run tests and commit**

#### Task 3.2.2: Add real-time work item status endpoint

**Files:**
- Modify: `src/api/dashboard_api.py`

**Step 1: Add websocket or SSE endpoint**

**Step 2: Write tests and commit**

### 3.3 Database Migration

#### Task 3.3.1: Design PostgreSQL schema

**Objective:** Relational schema for work items, events, agents.

**Files:**
- Create: `docs/database/schema.sql`

```sql
CREATE TABLE work_items (
    id UUID PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    phase VARCHAR(50) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    work_item_id UUID REFERENCES work_items(id),
    event_type VARCHAR(100) NOT NULL,
    evidence JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

**Step 2: Write migration script**

**Step 3: Test migration from JSON/SQLite and commit**

### 3.4 Redis Cache Layer

#### Task 3.4.1: Add Redis session caching

**Objective:** Sub-10ms session lookups.

**Files:**
- Create: `src/services/session_cache.py`

```python
import redis
from src.config import Config

class SessionCache:
    def __init__(self):
        self._client = redis.Redis(host="localhost", port=6379, decode_responses=True)

    def get(self, key: str) -> str | None:
        return self._client.get(f"session:{key}")

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        self._client.setex(f"session:{key}", ttl, value)
```

**Step 2: Write tests**

**Step 3: Commit**

### 3.5 IDE Integration

#### Task 3.5.1: Create VS Code extension scaffold

**Objective:** Agent trigger from IDE.

**Files:**
- Create: `vscode-extension/`

```json
{
  "name": "gadk-agent",
  "displayName": "GADK Agent",
  "activationEvents": ["onCommand:gadk.trigger"],
  "commands": [{
    "command": "gadk.trigger",
    "title": "Trigger GADK Agent"
  }]
}
```

**Step 2: Implement agent trigger command**

**Step 3: Test and commit**

---

## PHASE 4: Autonomy (v0.9.0–v1.0.0)

### 4.1 Agent Memory System

#### Task 4.1.1: Implement vector-based memory store

**Objective:** Persistent cross-session agent memory.

**Files:**
- Create: `src/services/agent_memory.py`

```python
from pydantic import BaseModel

class MemoryEntry(BaseModel):
    agent_id: str
    memory_type: str  # "context", "learning", "preference"
    content: dict
    embedding: list[float]
    timestamp: datetime
    ttl: datetime | None

class AgentMemoryStore:
    def store(self, entry: MemoryEntry) -> None:
        # Store in vector DB with metadata
        pass

    def recall(self, agent_id: str, memory_type: str | None = None) -> list[MemoryEntry]:
        # Query vector store
        pass
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

### 4.2 Self-Directed Ideation

#### Task 4.2.1: Add GitHub trend mining

**Objective:** Mine GitHub for trending repos/issues.

**Files:**
- Create: `src/services/trend_miner.py`

```python
async def mine_github_trends(topic: str, limit: int = 20) -> list[dict]:
    """Mine GitHub for trending repos/issues in topic."""
    # Use GitHub API to search trending repos
    pass
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

### 4.3 Predictive Operations

#### Task 4.3.1: Add metrics anomaly detection

**Objective:** Detect metric anomalies before they cause issues.

**Files:**
- Create: `src/services/anomaly_detector.py`

```python
from collections import deque

class AnomalyDetector:
    def __init__(self, window: int = 100):
        self._window = deque(maxlen=window)

    def add(self, metric: float) -> bool:
        """Return True if anomaly detected."""
        if len(self._window) < self._window.maxlen:
            self._window.append(metric)
            return False
        # Simple z-score anomaly detection
        mean = sum(self._window) / len(self._window)
        std = (sum((x - mean) ** 2 for x in self._window) / len(self._window)) ** 0.5
        z = abs(metric - mean) / std if std > 0 else 0
        self._window.append(metric)
        return z > 3.0
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

### 4.4 Knowledge Graph

#### Task 4.4.1: Add entity extraction from code

**Objective:** Build code entity knowledge graph.

**Files:**
- Create: `src/services/knowledge_graph.py`

```python
class CodeKnowledgeGraph:
    def extract_entities(self, file_path: str) -> list[Entity]:
        """Extract functions, classes, imports from code."""
        pass

    def add_relationships(self, entities: list[Entity]) -> None:
        """Add entity relationships to graph."""
        pass
```

**Step 2: Write tests**

**Step 3: Run tests and commit**

---

## PHASE 5: Ecosystem (v2.0.0)

### 5.1 Agent Marketplace

#### Task 5.1.1: Design marketplace architecture

**Objective:** Agent listing and one-click install.

**Files:**
- Create: `src/marketplace/`

**Step 1: Create marketplace models**

```python
class AgentListing(BaseModel):
    id: str
    name: str
    description: str
    author: str
    rating: float
    install_count: int
    capabilities: list[str]
```

**Step 2: Implement one-click install**

**Step 3: Write tests and commit**

### 5.2 Enterprise Features

#### Task 5.2.1: Add SSO/OAuth integration

**Objective:** Enterprise authentication.

**Files:**
- Create: `src/auth/sso.py`

**Step 1: Implement OAuth2 flow**

**Step 2: Write tests and commit**

### 5.3 Meta-Learning

#### Task 5.3.1: Add self-optimization engine

**Objective:** System that improves itself based on outcomes.

**Files:**
- Create: `src/services/self_optimizer.py`

```python
class SelfOptimizer:
    async def analyze_outcomes(self) -> dict[str, float]:
        """Analyze success/failure patterns."""
        pass

    async def suggest_improvements(self) -> list[str]:
        """Generate improvement suggestions."""
        pass
```

**Step 2: Write tests and commit**

---

## Final Integration

### Task F1: Run full test suite

Run: `.venv/bin/python -m pytest -q --tb=no 2>&1 | tail -5`
Expected: All tests pass (coverage > 65%)

### Task F2: Run quality gates

```bash
ruff check src tests
ruff format --check src tests
.venv/bin/python -m mypy src
```

### Task F3: Update version to v2.0.0

Modify: `README.md`, `CLAUDE.md`, `src/config.py`

### Task F4: Final commit

```bash
git add -A
git commit -m "feat: complete GADK v2.0.0 — fully autonomous cognitive foundry"
git tag v2.0.0
git push --tags
```

---

## Delegation Map

| Phase | Task Group | Primary Delegate | Reviewer |
|-------|-----------|-----------------|----------|
| 0 | Baseline fix | claude-code | github-code-review |
| 2.1 | PydanticAI contracts | claude-code | github-code-review |
| 2.2 | LangGraph workflows | claude-code | github-code-review |
| 2.3 | Vector retrieval | claude-code | github-code-review |
| 2.4 | Quality gates | claude-code | github-code-review |
| 2.5 | Self-prompting v2 | claude-code | github-code-review |
| 3.1 | Fleet manager | claude-code | github-code-review |
| 3.2 | Dashboard | claude-code | github-code-review |
| 3.3 | DB migration | claude-code | github-code-review |
| 3.4 | Redis cache | claude-code | github-code-review |
| 3.5 | IDE integration | claude-code | github-code-review |
| 4.1 | Memory system | claude-code | github-code-review |
| 4.2 | Trend mining | claude-code | github-code-review |
| 4.3 | Anomaly detection | claude-code | github-code-review |
| 4.4 | Knowledge graph | claude-code | github-code-review |
| 5.1 | Marketplace | claude-code | github-code-review |
| 5.2 | Enterprise | claude-code | github-code-review |
| 5.3 | Meta-learning | claude-code | github-code-review |

---

## Key File Landmarks

| File | Purpose |
|------|---------|
| `src/main.py` | Swarm runtime entry point |
| `src/config.py` | All feature flags and settings |
| `src/services/sdlc_phase.py` | Phase enum, WorkItem, ALLOWED_TRANSITIONS |
| `src/services/phase_controller.py` | PhaseController.advance() with gate evaluation |
| `src/services/quality_gates.py` | QualityGate ABC + concrete gates |
| `src/services/agent_contracts.py` | Pydantic models for all handoffs |
| `src/services/agent_decisions.py` | PydanticAI decision helpers |
| `src/services/workflow_graphs.py` | LangGraph state machines |
| `src/services/vector_index.py` | VectorIndex protocol + SqliteVecBackend |
| `src/services/embedder.py` | LiteLLMEmbedder factory |
| `src/services/self_prompt.py` | Gap-driven autonomous prompting |
| `src/services/retrieval_context.py` | LlamaIndex-backed retrieval |
| `src/agents/orchestrator.py` | Top-level routing |
| `src/agents/ideator.py` | PLAN phase — task proposals |
| `src/agents/architect.py` | ARCHITECT phase — ADR creation |
| `src/agents/builder.py` | IMPLEMENT phase — code writing |
| `src/agents/critic.py` | REVIEW phase — review verdicts |
| `src/agents/governor.py` | GOVERN phase — release decisions |
| `src/agents/pulse.py` | OPERATE phase — health monitoring |
| `src/agents/finops.py` | OPERATE phase — cost tracking |
| `src/state.py` | StateManager with atomic JSON writes |
| `src/mcp/server.py` | FastMCP stdio server |

---

## Test Commands Reference

```bash
# Full test suite (ALWAYS use venv python)
cd /home/westonaAaron675/gadk
.venv/bin/python -m pytest -q --tb=no

# Service tests
.venv/bin/python -m pytest tests/services/ -q

# Specific test file
.venv/bin/python -m pytest tests/services/test_agent_contracts.py -v

# Lint
ruff check src tests

# Format check
ruff format --check src tests

# Type check
.venv/bin/python -m mypy src
```

---

## Verification Checklist

Before each commit, verify:
- [ ] `.venv/bin/python -m pytest tests/ -q` passes
- [ ] `ruff check src tests` clean
- [ ] `ruff format --check src tests` clean
- [ ] No new `print()` statements in library code
- [ ] All new modules have `from __future__ import annotations`
- [ ] All new functions have docstrings
- [ ] State transitions go through PhaseController
- [ ] No direct WorkItem.phase mutation
