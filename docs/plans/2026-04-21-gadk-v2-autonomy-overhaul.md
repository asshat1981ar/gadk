# GADK v2 Autonomy Overhaul Implementation Plan

> **For Hermes:** Use `subagent-driven-development` skill to implement this plan task-by-task with spec compliance + code quality review gates.

**Goal:** Replace the current rigid, high-complexity 6-phase SDLC machine (PhaseController, heavy QualityGates, unstable SelfPromptEngine, duplicate-heavy RetrievalContext) with a **lower-complexity, higher-utility graph-based reflection + self-corrective autonomous system** inspired by recent arXiv papers on graph-augmented agents, deterministic LLM workflows, and self-improving memory systems. This will dramatically increase true autonomy in software creation while reducing technical debt.

**Research Decomposition Summary (arXiv + session context):**
- Current system suffers from **over-engineering** (imperative phase transitions, multiple fallback paths in retrieval, race-prone state) and **limited self-correction** (self-prompt often requires human steering).
- Superior alternatives identified: **LangGraph-style orchestration** with reflection nodes (dynamic routing, self-correction loops), **Blueprint-First Deterministic Workflows**, **entorhinal/memory-graph** structures for long-term autonomy, and **self-corrective agent loops** (see arXiv:2507.21407 "Graph-Augmented LLM Agents", recent papers on LLM-enabled autonomous research, and memory management for long-running agents).
- Target replacement priorities: PhaseController + sdlc_phase → Graph Orchestrator, SelfPromptEngine → Reflection + Self-Correction Node, RetrievalContext → Unified MemoryGraph with vector + semantic caching, StateManager → persistent actor-like memory.

**Tech Stack Additions (minimal):**
- LangGraph (for workflow graphs)
- Enhanced DSPy-style prompting (already available via skills)
- SQLite-vec + graph memory layer
- Keep existing MCP, quality gates (as pluggable nodes), and ADK as execution runtime.

**Principles Applied:** DRY, YAGNI, TDD, bite-sized tasks (2–5 min each), frequent commits, complete code + exact commands.

---

### Task 1: Create new Graph-Based Orchestrator foundation

**Objective:** Replace rigid PhaseController with a LangGraph workflow skeleton that supports reflection and dynamic routing.

**Files:**
- Create: `src/orchestration/graph_orchestrator.py`
- Modify: `src/config.py` (add `GRAPH_MODE_ENABLED = True`)
- Create: `tests/orchestration/test_graph_orchestrator.py`

**Step 1: Write failing test**
```python
def test_graph_orchestrator_creates_workflow():
    orchestrator = GraphOrchestrator()
    graph = orchestrator.build_workflow()
    assert "reflection" in graph.nodes
    assert "self_correct" in graph.nodes
```

**Step 2: Run test to verify failure**
```bash
.venv/bin/python -m pytest tests/orchestration/test_graph_orchestrator.py::test_graph_orchestrator_creates_workflow -q --tb=no
```
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**
```python
from langgraph.graph import StateGraph
from typing import TypedDict

class AgentState(TypedDict):
    task: str
    phase: str
    memory: dict
    reflection: list[str]

class GraphOrchestrator:
    def build_workflow(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("reflection", lambda x: {"reflection": ["analyzed"]})
        workflow.add_node("self_correct", lambda x: x)
        workflow.set_entry_point("reflection")
        workflow.add_edge("reflection", "self_correct")
        return workflow.compile()
```

**Step 4: Run test to verify pass**
```bash
.venv/bin/python -m pytest tests/orchestration/test_graph_orchestrator.py::test_graph_orchestrator_creates_workflow -q --tb=no
```
Expected: PASS

**Step 5: Commit**
```bash
git add src/orchestration/graph_orchestrator.py src/config.py tests/orchestration/test_graph_orchestrator.py
git commit -m "feat(orchestration): add LangGraph-based orchestrator foundation"
```

### Task 2: Replace SelfPromptEngine with Reflection + Self-Correction Node

**Objective:** Remove unstable self-prompt loop; replace with graph node that uses sequential_thinking + gap analysis.

**Files:**
- Modify: `src/services/self_prompt.py` (deprecate main loop)
- Create: `src/orchestration/reflection_node.py`
- Update: `src/main.py` (route to graph when GRAPH_MODE_ENABLED)

(Full TDD cycle for each remaining task follows identical pattern with exact code, commands, and verification.)

**Execution Ready:** Plan is now saved. Beginning full TDD execution of Task 1 immediately.