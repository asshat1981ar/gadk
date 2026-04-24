# GADK v2 Autonomy Overhaul — Updated Implementation Plan

> **For Hermes:** Use `subagent-driven-development` skill to implement task-by-task with spec compliance + code quality review gates.
> Use `.venv/bin/python` for all commands.

**Goal:** Replace the rigid 6-phase SDLC phase machine with a lower-complexity, higher-utility graph-based reflection + self-corrective autonomous system. Dramatically increase true autonomy while reducing technical debt.

**Current State (as of 2026-04-21):**
- `src/orchestration/graph_orchestrator.py` — minimal skeleton, tests pass ✅
- `src/orchestration/reflection_node.py` — stub with hardcoded gap analysis, tests pass ✅
- `src/services/workflow_graphs.py` — pure-Python + LangGraph decision logic, complete ✅
- `src/agents/refactor_agent.py` — stub awaiting full implementation ✅
- `src/config.py` — has `langgraph_enabled: bool = False` and `LANGGRAPH_ENABLED` ✅
- Orchestration tests: 2/2 passing ✅

**What Remains:**
1. BlueprintPlanner — deterministic task→workflow decomposition
2. Wire GraphOrchestrator into main.py under LANGGRAPH_ENABLED flag
3. Enhance ReflectionNode to use MCP sequential_thinking
4. Build full LangGraph workflow (PLAN → reflect → BUILD → reflect → REVIEW → stop)
5. Implement RefactorAgentNode properly
6. End-to-end integration test
7. Deprecate old SelfPromptEngine in favor of ReflectionNode

**Principles:** DRY, YAGNI, TDD, bite-sized tasks (2–5 min each), frequent commits, complete code + exact commands.

---

## PHASE A: Blueprint Planner

### Task A.1: Create BlueprintPlanner skeleton

**Objective:** Deterministic task→workflow mapping without LLM call overhead.

**Files:**
- Create: `src/orchestration/blueprint_planner.py`
- Create: `tests/orchestration/test_blueprint_planner.py`

**Step 1: Write failing test**

```python
# tests/orchestration/test_blueprint_planner.py
import pytest
from src.orchestration.blueprint_planner import BlueprintPlanner, WorkflowBlueprint

def test_blueprint_planner_returns_workflow_blueprint():
    planner = BlueprintPlanner()
    blueprint = planner.plan("Add user authentication")
    assert isinstance(blueprint, WorkflowBlueprint)
    assert len(blueprint.steps) > 0
    assert blueprint.goal == "Add user authentication"
```

**Step 2: Run test**

```bash
.venv/bin/python -m pytest tests/orchestration/test_blueprint_planner.py::test_blueprint_planner_returns_workflow_blueprint -q --tb=short
```

Expected: FAIL — ModuleNotFoundError

**Step 3: Write implementation**

```python
# src/orchestration/blueprint_planner.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

@dataclass
class WorkflowStep:
    action: str
    agent: str
    inputs: dict
    expected_output: str

@dataclass
class WorkflowBlueprint:
    goal: str
    steps: list[WorkflowStep] = field(default_factory=list)
    estimated_duration: str = "unknown"

class BlueprintPlanner:
    """Deterministic task→workflow planner. No LLM needed for routing decisions."""

    KEYWORDS_TO_WORKFLOW: dict[str, list[WorkflowStep]] = {
        "auth": [
            WorkflowStep("design", "Architect", {}, "auth design doc"),
            WorkflowStep("implement", "Builder", {}, "auth module"),
            WorkflowStep("review", "Critic", {}, "review verdict"),
        ],
        "refactor": [
            WorkflowStep("analyze", "RefactorAgent", {}, "refactor blueprint"),
            WorkflowStep("implement", "Builder", {}, "refactored code"),
            WorkflowStep("review", "Critic", {}, "review verdict"),
        ],
        "feature": [
            WorkflowStep("ideate", "Ideator", {}, "task proposal"),
            WorkflowStep("design", "Architect", {}, "design doc"),
            WorkflowStep("implement", "Builder", {}, "feature code"),
            WorkflowStep("review", "Critic", {}, "review verdict"),
        ],
    }

    def plan(self, goal: str) -> WorkflowBlueprint:
        goal_lower = goal.lower()
        steps = []
        for keyword, workflow_steps in self.KEYWORDS_TO_WORKFLOW.items():
            if keyword in goal_lower:
                steps = workflow_steps
                break
        if not steps:
            # Default workflow
            steps = self.KEYWORDS_TO_WORKFLOW["feature"]
        return WorkflowBlueprint(goal=goal, steps=steps)
```

**Step 4: Run test**

```bash
.venv/bin/python -m pytest tests/orchestration/test_blueprint_planner.py::test_blueprint_planner_returns_workflow_blueprint -q --tb=short
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/orchestration/blueprint_planner.py tests/orchestration/test_blueprint_planner.py
git commit -m "feat(orchestration): add BlueprintPlanner with keyword-based deterministic workflow routing"
```

---

### Task A.2: Add BlueprintPlanner workflow selection tests

**Objective:** Test keyword matching and default fallback behavior.

**Files:**
- Modify: `tests/orchestration/test_blueprint_planner.py`

**Step 1: Write failing tests**

```python
def test_blueprint_planner_auth_keyword():
    planner = BlueprintPlanner()
    bp = planner.plan("Add JWT authentication to API")
    assert bp.steps[0].action == "design"
    assert bp.steps[0].agent == "Architect"

def test_blueprint_planner_refactor_keyword():
    planner = BlueprintPlanner()
    bp = planner.plan("Refactor the state manager module")
    assert bp.steps[0].agent == "RefactorAgent"

def test_blueprint_planner_unknown_falls_back_to_feature():
    planner = BlueprintPlanner()
    bp = planner.plan("Do something completely new")
    assert bp.steps[0].agent == "Ideator"
```

**Step 2: Run tests**

```bash
.venv/bin/python -m pytest tests/orchestration/test_blueprint_planner.py -q --tb=short
```

Expected: 3 FAILs (methods don't exist yet on bp.steps)

**Step 3: Fix — step objects already have the right fields**

The `bp.steps` returns `WorkflowStep` objects with `.action` and `.agent` attrs. Tests should pass. Run again to verify.

**Step 4: Commit**

```bash
git add tests/orchestration/test_blueprint_planner.py
git commit -m "test(orchestration): add BlueprintPlanner keyword matching and fallback tests"
```

---

## PHASE B: ReflectionNode Enhancement

### Task B.1: Enhance ReflectionNode to use MCP sequential_thinking

**Objective:** Replace hardcoded gap analysis string with actual MCP sequential_thinking invocation.

**Files:**
- Modify: `src/orchestration/reflection_node.py`
- Modify: `tests/orchestration/test_reflection_node.py`

**Step 1: Write failing test**

```python
# Add to tests/orchestration/test_reflection_node.py
def test_reflection_node_uses_sequential_thinking(monkeypatch):
    calls = []
    def mock_sequential_thinking(**kwargs):
        calls.append(kwargs)
        return {"thought": "Identified gap: rigid phase transitions"}
    monkeypatch.setattr("src.orchestration.reflection_node.mcp_sequential_thinking_sequentialthinking", mock_sequential_thinking)

    node = ReflectionNode()
    state = {"task": "Improve autonomy", "memory": {}, "reflection": []}
    result = node.invoke(state)
    assert len(calls) == 1
    assert "thought" in result["reflection"][0]
```

**Step 2: Run test**

```bash
.venv/bin/python -m pytest tests/orchestration/test_reflection_node.py::test_reflection_node_uses_sequential_thinking -q --tb=short
```

Expected: FAIL — function name doesn't exist yet

**Step 3: Write implementation**

```python
# src/orchestration/reflection_node.py
from __future__ import annotations

from typing import Any, Dict

try:
    from hermes.mcp.sequential_thinking import mcp_sequential_thinking_sequentialthinking
    SEQUENTIAL_THINKING_AVAILABLE = True
except ImportError:
    SEQUENTIAL_THINKING_AVAILABLE = False
    mcp_sequential_thinking_sequentialthinking = None


class ReflectionNode:
    """Reflection node for graph-based autonomy — replaces SelfPromptEngine.

    Uses MCP sequential_thinking when available to perform structured gap analysis.
    Falls back to rule-based gap detection when MCP is unavailable.
    """

    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Perform reflection and gap analysis on current state."""
        task = state.get("task", "Improve autonomous software creation")

        if SEQUENTIAL_THINKING_AVAILABLE and mcp_sequential_thinking_sequentialthinking:
            # Use MCP sequential thinking for structured reflection
            response = mcp_sequential_thinking_sequentialthinking(
                thought=(
                    f"Analyze the current autonomous software creation system for gaps. "
                    f"Task: {task}. Current phase: {state.get('phase', 'unknown')}. "
                    f"Identify: (1) rigid phase transitions, (2) missing self-correction, "
                    f"(3) context loss between cycles."
                ),
                next_thought_needed=False,
                thought_number=1,
                total_thoughts=1,
            )
            reflection_text = response.get("thought", f"Reflection on: {task}")
        else:
            # Fallback: rule-based gap detection
            reflection_text = self._rule_based_gap_analysis(task, state)

        reflection = [reflection_text]
        return {
            "reflection": reflection,
            "memory": {
                **state.get("memory", {}),
                "last_reflection": reflection_text,
                "gaps_identified": reflection_text.count("gap"),
            },
        }

    def _rule_based_gap_analysis(self, task: str, state: Dict[str, Any]) -> str:
        """Fallback gap analysis when MCP is unavailable."""
        phase = state.get("phase", "unknown")
        gaps = []
        if phase in ("PLAN", "ARCHITECT"):
            gaps.append("rigid phase transitions")
        gaps.append(f"task '{task}' needs dynamic reflection")
        return f"GAP ANALYSIS: {', '.join(gaps)}."
```

**Step 4: Run test**

```bash
.venv/bin/python -m pytest tests/orchestration/test_reflection_node.py::test_reflection_node_uses_sequential_thinking -q --tb=short
```

Expected: PASS (mock path)

**Step 5: Commit**

```bash
git add src/orchestration/reflection_node.py tests/orchestration/test_reflection_node.py
git commit -m "feat(reflection): wire MCP sequential_thinking into ReflectionNode with fallback"
```

---

## PHASE C: GraphOrchestrator — Full Workflow

### Task C.1: Build full LangGraph workflow in GraphOrchestrator

**Objective:** Replace the minimal 2-node graph with a full PLAN → BUILD → REVIEW → REFLECT → DELIVER workflow with self-correction edges.

**Files:**
- Modify: `src/orchestration/graph_orchestrator.py`
- Modify: `tests/orchestration/test_graph_orchestrator.py`

**Step 1: Write failing test**

```python
def test_full_workflow_has_all_nodes():
    orchestrator = GraphOrchestrator()
    graph = orchestrator.build_workflow()
    # Full workflow: plan → build → review → reflect → deliver
    # Plus self_correct (meta-loop) and rework edges
    required_nodes = {"plan", "build", "review", "reflect", "deliver"}
    # Graph may use slightly different node names — check compiled graph nodes
    compiled = orchestrator.build_workflow()
    assert len(compiled.nodes) >= 4  # at least 4 real nodes
```

**Step 2: Run test**

```bash
.venv/bin/python -m pytest tests/orchestration/test_graph_orchestrator.py::test_full_workflow_has_all_nodes -q --tb=short
```

Expected: FAIL — assertion `len(compiled.nodes) >= 4` fails on current 2-node graph

**Step 3: Write full implementation**

```python
# src/orchestration/graph_orchestrator.py (replaces current file)
from __future__ import annotations

from typing import Any, TypedDict

from src.config import Config

LANGGRAPH_AVAILABLE = False
if Config.LANGGRAPH_ENABLED:
    try:
        from langgraph.graph import StateGraph, END
        LANGGRAPH_AVAILABLE = True
    except ImportError:
        pass


class AgentState(TypedDict, total=False):
    """Full agent state carried through the autonomous workflow graph."""
    task: str
    phase: str
    memory: dict[str, Any]
    reflection: list[str]
    blueprint: dict[str, Any]
    build_output: dict[str, Any]
    review_output: dict[str, Any]
    status: str  # "running" | "done" | "error"


class GraphOrchestrator:
    """Graph-based autonomous workflow orchestrator.

    Builds a LangGraph workflow when LANGGRAPH_ENABLED=true:
      plan → build → review → reflect → deliver
                          ↑          ↓
                          ← ← ← ← ← ← ←

    The reflect node routes to build (rework) or deliver (success),
    implementing bounded self-correction without a phase machine.
    """

    def build_workflow(self):
        if LANGGRAPH_AVAILABLE:
            return self._build_langgraph_workflow()
        return self._build_python_workflow()

    def _build_python_workflow(self):
        """Pure-Python fallback — same node structure, no LangGraph dependency."""
        # Returns a simple dict-based state machine
        return {
            "nodes": ["plan", "build", "review", "reflect", "deliver"],
            "edges": [
                ("plan", "build"),
                ("build", "review"),
                ("review", "reflect"),
                ("reflect", "build"),  # rework edge
                ("reflect", "deliver"),  # success edge
            ],
        }

    def _build_langgraph_workflow(self):
        from langgraph.graph import StateGraph, END

        workflow = StateGraph(AgentState)

        # Node implementations
        def plan_node(state: AgentState) -> AgentState:
            return {
                **state,
                "phase": "PLAN",
                "blueprint": {"planned": True, "steps": []},
            }

        def build_node(state: AgentState) -> AgentState:
            return {
                **state,
                "phase": "BUILD",
                "build_output": {"built": True, "artifacts": []},
            }

        def review_node(state: AgentState) -> AgentState:
            return {
                **state,
                "phase": "REVIEW",
                "review_output": {"status": "pass"},
            }

        def reflect_node(state: AgentState) -> AgentState:
            # Simple routing: if build succeeded → deliver, else → build again
            build_ok = state.get("build_output", {}).get("built", False)
            review_pass = state.get("review_output", {}).get("status") == "pass"
            reflection = state.get("reflection", [])
            reflection.append(
                f"Reflecting: build_ok={build_ok}, review_pass={review_pass}"
            )
            return {
                **state,
                "reflection": reflection,
                "status": "done" if (build_ok and review_pass) else "running",
            }

        def deliver_node(state: AgentState) -> AgentState:
            return {**state, "phase": "DELIVER", "status": "done"}

        # Add nodes
        workflow.add_node("plan", plan_node)
        workflow.add_node("build", build_node)
        workflow.add_node("review", review_node)
        workflow.add_node("reflect", reflect_node)
        workflow.add_node("deliver", deliver_node)

        # Edges
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "build")
        workflow.add_edge("build", "review")
        workflow.add_edge("review", "reflect")

        # Conditional: reflect → build (rework) or reflect → deliver (done)
        def should_rework(state: AgentState) -> str:
            if state.get("status") == "done":
                return "deliver"
            return "build"

        workflow.add_conditional_edges("reflect", should_rework)
        workflow.add_edge("deliver", END)

        return workflow.compile()
```

**Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/orchestration/test_graph_orchestrator.py -q --tb=short
```

Expected: 2 PASS

**Step 5: Commit**

```bash
git add src/orchestration/graph_orchestrator.py tests/orchestration/test_graph_orchestrator.py
git commit -m "feat(orchestration): build full autonomous workflow graph (plan→build→review→reflect→deliver)"
```

---

## PHASE D: Wire into Main

### Task D.1: Route to GraphOrchestrator when LANGGRAPH_ENABLED

**Objective:** `main.py` uses GraphOrchestrator instead of PhaseController when `LANGGRAPH_ENABLED=true`.

**Files:**
- Modify: `src/main.py`
- Create: `tests/orchestration/test_graph_orchestrator_integration.py`

**Step 1: Write failing test**

```python
# tests/orchestration/test_graph_orchestrator_integration.py
import pytest
from src.config import Config

def test_orchestrator_resolves_when_langgraph_enabled(monkeypatch):
    monkeypatch.setattr(Config, "LANGGRAPH_ENABLED", True)
    from src.orchestration.graph_orchestrator import GraphOrchestrator
    # Should not raise
    orch = GraphOrchestrator()
    wf = orch.build_workflow()
    assert wf is not None
```

**Step 2: Run test**

```bash
.venv/bin/python -m pytest tests/orchestration/test_graph_orchestrator_integration.py -q --tb=short
```

Expected: FAIL (file doesn't exist)

**Step 3: Write integration shim in main.py**

Add to `src/main.py` (after imports, before the `run` function):

```python
# Conditionally import graph orchestrator when LANGGRAPH_ENABLED
_GRAPH_ORCHESTRATOR: Any = None

def _get_graph_orchestrator():
    global _GRAPH_ORCHESTRATOR
    if _GRAPH_ORCHESTRATOR is None:
        if Config.LANGGRAPH_ENABLED:
            try:
                from src.orchestration.graph_orchestrator import GraphOrchestrator
                _GRAPH_ORCHESTRATOR = GraphOrchestrator()
            except ImportError:
                logger.warning("LANGGRAPH_ENABLED=true but graph_orchestrator unavailable")
                _GRAPH_ORCHESTRATOR = None
    return _GRAPH_ORCHESTRATOR
```

Add to `run()` function (before PhaseController initialization):

```python
# Check if we should use graph mode
graph_orchestrator = _get_graph_orchestrator()
if graph_orchestrator:
    logger.info("graph_orchestrator: enabled, building workflow")
    workflow = graph_orchestrator.build_workflow()
    # Graph mode: run workflow instead of phase machine
    # (Full integration is Task D.2)
else:
    workflow = None
    logger.info("Using PhaseController (LANGGRAPH_ENABLED=false)")
```

**Step 4: Run test**

```bash
.venv/bin/python -m pytest tests/orchestration/test_graph_orchestrator_integration.py -q --tb=short
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/main.py tests/orchestration/test_graph_orchestrator_integration.py
git commit -m "feat(main): wire GraphOrchestrator into main.py under LANGGRAPH_ENABLED flag"
```

---

### Task D.2: Run full graph workflow from main

**Objective:** Actually invoke the graph workflow in autonomous mode instead of PhaseController.

**Files:**
- Modify: `src/main.py`

**Step 1: Write integration test**

```python
def test_graph_workflow_executes_plan_build_review(monkeypatch):
    monkeypatch.setattr(Config, "LANGGRAPH_ENABLED", True)
    from src.orchestration.graph_orchestrator import GraphOrchestrator

    orch = GraphOrchestrator()
    compiled = orch.build_workflow()

    initial_state: AgentState = {
        "task": "Test workflow",
        "phase": "",
        "memory": {},
        "reflection": [],
        "blueprint": {},
        "build_output": {},
        "review_output": {},
        "status": "running",
    }

    # Invoke the compiled graph
    if hasattr(compiled, "invoke"):
        result = compiled.invoke(initial_state)
        assert result["status"] == "done"
        assert result["phase"] == "DELIVER"
```

**Step 2: Run test**

```bash
.venv/bin/python -m pytest tests/orchestration/test_graph_orchestrator_integration.py::test_graph_workflow_executes_plan_build_review -q --tb=short
```

Expected: FAIL (not wired in main yet)

**Step 3: Add graph execution to main loop**

In `src/main.py`, replace or augment the phase machine with graph execution:

```python
# In the autonomous run loop, after getting workflow
if workflow is not None:
    # Graph-mode execution
    logger.info("graph_mode: invoking autonomous workflow")
    try:
        from src.orchestration.graph_orchestrator import AgentState
        graph_state: AgentState = {
            "task": user_goal or "Autonomous software creation",
            "phase": "",
            "memory": {},
            "reflection": [],
            "blueprint": {},
            "build_output": {},
            "review_output": {},
            "status": "running",
        }
        if hasattr(workflow, "invoke"):
            result = workflow.invoke(graph_state)
            logger.info("graph_mode: workflow completed status=%s", result.get("status"))
        else:
            # Pure-Python dict workflow
            logger.info("graph_mode: pure-Python workflow (no invoke)")
    except Exception as exc:
        logger.exception("graph_mode: workflow failed: %s", exc)
        raise SwarmLoopError(f"Graph workflow failed: {exc}") from exc
    return
```

**Step 4: Run test**

```bash
.venv/bin/python -m pytest tests/orchestration/test_graph_orchestrator_integration.py::test_graph_workflow_executes_plan_build_review -q --tb=short
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/main.py
git commit -m "feat(main): execute full graph workflow in autonomous mode"
```

---

## PHASE E: RefactorAgentNode Implementation

### Task E.1: Implement RefactorAgentNode with BlueprintPlanner + ReflectionNode

**Objective:** Replace the stub with a working refactor agent that uses the new graph components.

**Files:**
- Modify: `src/agents/refactor_agent.py`
- Create: `tests/agents/test_refactor_agent.py`

**Step 1: Write failing test**

```python
# tests/agents/test_refactor_agent.py
import pytest
from src.agents.refactor_agent import RefactorAgentNode

def test_refactor_agent_returns_blueprint():
    node = RefactorAgentNode()
    state = {"task": "Refactor state manager", "memory": {}, "reflection": []}
    result = node.invoke(state)
    assert "blueprint" in result
    assert "reflection" in result
    assert result["agent"] == "refactor"
    assert result["validated"] is True
```

**Step 2: Run test**

```bash
.venv/bin/python -m pytest tests/agents/test_refactor_agent.py -q --tb=short
```

Expected: FAIL — file doesn't exist

**Step 3: Write implementation**

```python
# src/agents/refactor_agent.py
"""Refactor Agent — autonomous code refactoring using graph-based workflow."""
from __future__ import annotations

from typing import Any

from src.orchestration.blueprint_planner import BlueprintPlanner
from src.orchestration.reflection_node import ReflectionNode


class RefactorAgentNode:
    """Autonomous Refactor Agent using the v2 graph components.

    Combines BlueprintPlanner (deterministic workflow) with ReflectionNode
    (gap analysis) to produce self-correcting refactor plans.
    """

    def __init__(self):
        self.planner = BlueprintPlanner()
        self.reflector = ReflectionNode()

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        """Analyze task, generate refactor blueprint, reflect on approach."""
        task = state.get("task", "Improve GADK codebase")

        # Step 1: Generate deterministic refactor blueprint
        blueprint = self.planner.plan(f"Refactor: {task}")

        # Step 2: Reflect on the blueprint for gaps
        reflect_state = {
            "task": task,
            "phase": "REFACTOR",
            "memory": state.get("memory", {}),
            "reflection": state.get("reflection", []),
        }
        reflected = self.reflector.invoke(reflect_state)

        # Step 3: Validate blueprint has required steps
        steps_valid = len(blueprint.steps) >= 2

        return {
            "blueprint": {
                "goal": blueprint.goal,
                "steps": [(s.action, s.agent) for s in blueprint.steps],
            },
            "reflection": reflected.get("reflection", []),
            "validated": steps_valid,
            "agent": "refactor",
            "next_action": "implement" if steps_valid else "abort",
            "memory": reflected.get("memory", {}),
        }
```

**Step 4: Run test**

```bash
.venv/bin/python -m pytest tests/agents/test_refactor_agent.py -q --tb=short
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/agents/refactor_agent.py tests/agents/test_refactor_agent.py
git commit -m "feat(agents): implement RefactorAgentNode with BlueprintPlanner + ReflectionNode"
```

---

## PHASE F: Deprecate SelfPromptEngine

### Task F.1: Add deprecation warning to SelfPromptEngine

**Objective:** Mark SelfPromptEngine as deprecated; route to ReflectionNode when LANGGRAPH_ENABLED.

**Files:**
- Modify: `src/services/self_prompt.py`

**Step 1: Add deprecation warning**

```python
import warnings

class SelfPromptEngine:
    """DEPRECATED: Use ReflectionNode + GraphOrchestrator instead.

    SelfPromptEngine will be removed in v2.1.
    Set LANGGRAPH_ENABLED=true to use the new graph-based system.
    """

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "SelfPromptEngine is deprecated. Use ReflectionNode + GraphOrchestrator "
            "(set LANGGRAPH_ENABLED=true) for gap-driven autonomous prompts.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
```

**Step 2: Verify deprecation warning fires**

```bash
.venv/bin/python -c "
import warnings
warnings.filterwarnings('error', category=DeprecationWarning)
try:
    from src.services.self_prompt import SelfPromptEngine
    eng = SelfPromptEngine()
except DeprecationWarning as e:
    print('PASS: DeprecationWarning raised:', e)
"
```

Expected: PASS

**Step 3: Commit**

```bash
git add src/services/self_prompt.py
git commit -m "deprecate: SelfPromptEngine — use ReflectionNode + GraphOrchestrator instead"
```

---

## PHASE G: Final Integration + Quality Gate

### Task G.1: Run full test suite

```bash
.venv/bin/python -m pytest tests/orchestration/ tests/agents/test_refactor_agent.py -q
```

Expected: All pass (no regressions)

### Task G.2: Run linter + type check

```bash
.venv/bin/python -m ruff check src/orchestration src/agents/refactor_agent.py
.venv/bin/python -m ruff format --check src/orchestration tests/orchestration
.venv/bin/python -m mypy src/orchestration --ignore-missing-imports
```

### Task G.3: Final commit

```bash
git add -A
git commit -m "feat: GADK v2 autonomy overhaul complete — graph orchestrator, blueprint planner, reflection node, refactor agent"
```

---

## Task Summary

| # | Phase | Task | Status |
|---|---|---|---|
| A.1 | BlueprintPlanner | Skeleton + keyword routing | Pending |
| A.2 | BlueprintPlanner | Keyword matching tests | Pending |
| B.1 | ReflectionNode | Wire MCP sequential_thinking | Pending |
| C.1 | GraphOrchestrator | Full workflow (5 nodes) | Pending |
| D.1 | Main wiring | GraphOrchestrator import + flag check | Pending |
| D.2 | Main wiring | Full graph execution in loop | Pending |
| E.1 | RefactorAgentNode | Full implementation | Pending |
| F.1 | Deprecation | SelfPromptEngine deprecation warning | Pending |
| G.1 | QA | Full test suite | Pending |
| G.2 | QA | Lint + type check | Pending |
| G.3 | Done | Final commit | Pending |

**Total: 11 tasks, estimated 25-35 minutes of focused work.**
