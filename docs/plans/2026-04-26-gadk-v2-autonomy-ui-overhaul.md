# GADK v2 Autonomy & UI Overhaul Plan

**Date:** 2026-04-26  
**Status:** Fully implemented and committed (975de4e)  
**Scope:** Cognitive autonomy, graph memory, reflection loops, blueprint planning, real-time chat UI  

---

## 1. Goal

Evolve GADK from a static orchestration system into a **self-correcting, graph-aware, real-time** cognitive swarm. The v2 overhaul introduces:

- Persistent **graph memory** for agent context
- **Structured reflection** with evaluation criteria
- **Deterministic DAG blueprint planning** with dependency resolution
- **Autonomous self-prompting loop** (plan → execute → reflect → retry)
- **WebSocket chat server** for real-time agent interaction
- **Modern Web UI** (dark-themed chat interface)
- **Integration tests** for the full chat-to-swarm pipeline

---

## 2. Architecture

```
User ↔ WebSocket Chat UI ↔ ChatServer ↔ AutonomousLoop
                                          ↓
                    ┌─────────────────────┼─────────────────────┐
                    ↓                     ↓                     ↓
            BlueprintPlanner      ReflectionNode         MemoryGraph
                    ↓                     ↓                     ↓
            WorkflowBlueprint      ReflectionResult      GraphStore (SQLite)
```

---

## 3. Task Breakdown

### Task 1: Graph-based Persistent Memory Store

**File:** `src/memory/graph_store.py`  
**Purpose:** Low-level graph persistence using SQLite + NetworkX

**Features:**
- Node types: `TASK`, `AGENT`, `OUTCOME`, `DECISION`, `CRITERION`
- Edge types with annotations
- Full-text search via SQLite FTS5
- Semantic similarity queries (Jaccard over node fingerprints)
- Atomic transactions

**Tests:** `tests/memory/test_graph_store.py` (6 tests)

---

### Task 2: High-Level MemoryGraph API

**File:** `src/memory/memory_graph.py`  
**Purpose:** Agent-friendly facade over GraphStore

**Features:**
- `record_task(agent, task, outcome, metadata)` → persists execution traces
- `find_similar(query, max_results)` → semantic context retrieval
- `get_agent_history(agent)` → temporal execution log
- `record_decision(agent, decision, criteria)` → decision tracking

**Tests:** `tests/memory/test_memory_graph.py`

---

### Task 3: Structured Reflection with MemoryGraph

**File:** `src/orchestration/reflection_node.py`  
**Purpose:** Evaluate agent outputs against success criteria

**Features:**
- `ReflectionResult`: `status`, `gaps[]`, `suggestions[]`, `confidence`
- Criterion checking with regex + semantic hints
- Historical failure lookup via MemoryGraph
- Self-correction suggestions based on past similar failures
- `reflect()` helper for integration into agent loops

**Tests:** `tests/orchestration/test_reflection_node.py`

---

### Task 4: Deterministic DAG Blueprint Planner

**File:** `src/orchestration/blueprint_planner.py`  
**Purpose:** Generate structured execution plans from natural language goals

**Features:**
- `WorkflowStep`: id, action, agent, inputs, expected_output, depends_on
- `WorkflowBlueprint`: goal, steps[], topological ordering, estimated duration
- Keyword-based complexity heuristics
- Reflection hooks (`requires_reflection` flag per step)
- Kahn's algorithm for topological sort
- Dependency cycle detection

**Tests:** `tests/orchestration/test_blueprint_planner.py`

---

### Task 5: RefactorAgent v2 with Self-Correction Loop

**File:** `src/agents/refactor_agent.py`  
**Purpose:** Autonomous code refactoring agent

**Features:**
- `invoke()`: single pass (plan + reflect)
- `invoke_with_correction()`: retry loop (max 3 attempts)
- Integrates BlueprintPlanner + ReflectionNode + MemoryGraph
- Produces: blueprint, reflection, `validated` flag, `next_action`
- Falls back to keyword-based refactoring if LLM unavailable

**Tests:** `tests/agents/test_refactor_agent.py` (5 tests)

---

### Task 6: RetrievalContext Graph Integration

**File:** `src/services/retrieval_context.py`  
**Purpose:** Augment retrieval with graph-based semantic memory

**Features:**
- `MemoryGraphRetrievalRequest`: goal + optional `memory_graph` + `top_k`
- If `memory_graph` provided: queries `find_similar(goal, top_k)`
- If no `memory_graph`: falls back to keyword-only retrieval
- `graph_context` key present only when graph results exist
- Respects `request.top_k` (not hardcoded)

**Tests:** `tests/services/test_retrieval_graph.py` (6 tests, all passing)

---

### Task 7: AutonomousLoop — Self-Correcting Graph Workflow

**File:** `src/services/autonomous_loop.py`  
**Purpose:** Close the loop: plan → execute → reflect → retry

**Features:**
- `AutonomousLoop.run(goal)` → generates blueprint, executes steps, reflects
- Step execution with agent dispatch
- Reflection after each step; if gaps → replan + retry
- Max retry limit per step
- MemoryGraph records all outcomes for future retrieval

**Tests:** `tests/services/test_autonomous_loop.py` (6 tests)

---

### Task 8: ChatServer — WebSocket Real-Time Backend

**File:** `src/webapp/chat_server.py`  
**Purpose:** Real-time bidirectional communication with the swarm

**Features:**
- FastAPI + WebSocket `/ws/chat`
- Connection manager (broadcast, direct reply)
- Message routing to AutonomousLoop
- Async message processing
- Connection health tracking

**Tests:** `tests/webapp/test_chat_server.py`

---

### Task 9: Static Web UI Assets (Dark Theme)

**Files:**
- `src/webapp/static/index.html` — Chat layout, message bubbles, input
- `src/webapp/static/css/chat.css` — Dark theme, syntax highlighting
- `src/webapp/static/js/chat.js` — WebSocket client, message rendering

**Features:**
- Dark theme (#0f1117 background, #c9d1d9 text)
- Agent avatars with color coding
- Markdown rendering for code blocks
- Typing indicators
- Auto-reconnect on disconnect
- System status panel

---

### Task 10: WebApp Integration — Wire Chat into Main Server

**File:** `src/webapp/server.py`  
**Purpose:** Mount chat routes + serve static assets

**Features:**
- Added `FileResponse` / `StaticFiles` imports
- Mounted `/static` → `src/webapp/static/`
- Added `/chat` route redirecting to `index.html`
- WebSocket endpoint wired
- CORSMiddleware for local dev

---

### Task 11: Integration Tests

**File:** `tests/webapp/test_integration.py`  
**Purpose:** End-to-end chat → swarm pipeline

**Features:**
- TestClient for HTTP routes
- WebSocket client for real-time flows
- Full round-trip: user message → AutonomousLoop → chat response
- Validates static file serving

---

## 4. Test Summary

| Test Suite | Count | Status |
|---|---|---|
| `tests/memory/` | 10 | PASS |
| `tests/orchestration/` | 12 | PASS |
| `tests/agents/` | 5 | PASS |
| `tests/services/` | 13 | PASS |
| `tests/webapp/` | 6 | PASS |
| **Total v2** | **46** | **PASS** |

Legacy pre-existing failures (async plugin, model_router) are **out of scope** for this plan.

---

## 5. Commits

- `b453c14` — Task 1: Graph-based persistent memory store
- `dc1d95f` — Task 2: High-level MemoryGraph API
- `79bd3d3` — Task 3: Structured reflection with MemoryGraph
- `39c311b` — Task 4: Deterministic DAG blueprint planner
- `4cfa5c6` — Task 5: RefactorAgent v2 with self-correction
- `0a92c7b` — Task 7: AutonomousLoop
- `975de4e` — Tasks 6, 8-11: Retrieval graph, ChatServer, WebUI, integration

---

## 6. Known Issues

- `src/webapp/server.py` line 47 has a pre-existing corrupted token assignment (`_WEBAPP_TOKEN=*** ""`) — existed before this plan, not blocking.
- Legacy test suite has ~81 pre-existing failures (async plugin missing, model_router divide-by-zero).
- `docs/plans/2026-04-26-gadk-v2-autonomy-ui-overhaul.md` was untracked and deleted by `git clean -fd`; this file is the reconstruction.

---

## 7. Success Criteria (Met)

- [x] Graph memory persists agent execution traces
- [x] Reflection evaluates against criteria with confidence scores
- [x] Blueprint planner produces valid DAGs with dependency order
- [x] AutonomousLoop self-corrects on reflection gaps
- [x] RetrievalContext integrates graph memory when available
- [x] ChatServer handles WebSocket connections
- [x] WebUI renders dark-themed chat interface
- [x] Integration tests cover chat → swarm round-trip
- [x] All 46 v2 tests pass
