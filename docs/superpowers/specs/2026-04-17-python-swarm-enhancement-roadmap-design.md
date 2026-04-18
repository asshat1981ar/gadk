# Design Specification: Python Swarm Enhancement Roadmap

**Date:** 2026-04-17
**Status:** Approved
**Framework:** Google ADK + LiteLLM/OpenRouter
**Topic:** Phased enhancement roadmap for the Python multi-agent SDLC system

## 1. Executive Summary

The current Python system is a hybrid multi-agent SDLC platform centered on `src/main.py`, `src/agents/`, `src/tools/`, and the repo-local state/metrics/session files. Its main architectural weakness is that it currently has **two overlapping execution models**:

1. an ADK-native runtime in `src/main.py` using `Runner`, ADK agents, callbacks, and registered tools
2. a planner-driven runtime in `src/planner.py` and `src/planned_main.py` that exists to compensate for unreliable tool calling from the configured LiteLLM/OpenRouter model

This roadmap keeps the existing strengths — ADK runner orchestration, `batch_execute()`, session persistence, local state/events, and observability — while reducing runtime drift. The design is intentionally phased so the system can improve in place instead of requiring a rewrite.

## 2. Goals

- Keep **Google ADK** as the official control plane for agent execution
- Preserve **LiteLLM/OpenRouter** model flexibility without allowing planner fallbacks to become a second unofficial product
- Unify task lifecycle semantics across the swarm CLI, dashboard, state files, autonomous loop, and agent workflows
- Harden tool execution, review gates, and delivery flows for safer autonomous SDLC behavior
- Improve planning readiness for future implementation by defining clear module boundaries and ownership

## 3. Current-State Findings

### 3.1 Strengths

- `src/main.py` already provides a clean ADK-based runtime with session persistence, callbacks, prompt queue handling, and autonomous vs single-run modes.
- `src/tools/dispatcher.py` already gives the system a practical concurrency primitive through `batch_execute()`.
- `src/state.py`, `src/cli/swarm_ctl.py`, and `src/observability/` provide a coherent local control plane built on JSON, JSONL, and SQLite-backed session storage.
- The agent split in `src/agents/` is conceptually sound: Orchestrator, Ideator, Builder, Critic, Pulse, and FinOps are already separated by role.

### 3.2 Gaps

- `src/planner.py` and `src/planned_main.py` duplicate runtime responsibilities instead of acting as a controlled compatibility layer.
- Task lifecycle rules are spread across `src/agents/ideator.py`, `src/autonomous_sdlc.py`, direct state writes, and CLI/dashboard readers.
- Builder, Critic, and delivery logic mix artifact creation, review, GitHub operations, and state updates without one authoritative coordinator.
- Tool APIs return inconsistent shapes (plain strings, dicts, mock strings, error-prefixed strings), which complicates agent reasoning and fallback behavior.
- Autonomous SDLC flow in `src/autonomous_sdlc.py` behaves like a partially separate system rather than a driver using the same contract as the interactive swarm.

## 4. Recommended Approach

### 4.1 Chosen Strategy: Hybrid Phased Roadmap

The recommended approach is to keep ADK as the top-level runtime and formalize the planner as a **fallback execution adapter** only where model/tool-calling reliability is weak.

This is preferred over:

- **ADK-only consolidation immediately**, which is cleaner long-term but riskier because the planner exists for a real compatibility reason
- **Planner-first architecture**, which may improve short-term reliability but would move the system farther away from the intended ADK design

## 5. Target Architecture

### 5.1 Runtime and Execution

- `src/main.py` remains the **single production entrypoint**
- ADK `Runner` remains the **official orchestration runtime**
- `src/planner.py` is refactored into an **execution backend adapter** used behind a narrow interface
- `src/planned_main.py` is demoted into a migration harness, demo path, or removed after the adapter is integrated

### 5.2 Coordination Model

Introduce a dedicated coordination module (for example `src/services/task_coordinator.py`) that owns:

- task creation and update rules
- state transition validation
- roadblock and retry policy
- synchronization between `state.json`, `events.jsonl`, GitHub issue state, and CLI/dashboard consumers

This coordinator becomes the authoritative workflow surface that the Orchestrator, autonomous loop, Builder, Critic, Pulse, and CLI read from or write through.

### 5.3 Agent Responsibilities

#### Orchestrator

- remains the top-level router
- decides which specialized agent or service path should handle the request
- routes execution through the unified coordinator and execution adapter instead of mixing direct workflow semantics into its own module

#### Ideator

- focuses on identifying opportunities and proposing structured tasks
- does not own long-term persistence policy beyond handing structured task proposals to the coordinator

#### Builder

- produces staged artifacts and structured build results
- no longer performs implicit delivery actions as part of raw artifact creation

#### Critic

- produces structured review verdicts (`pass`, `retry`, `block`, `reason`)
- becomes the review gate for staged artifacts, sandbox results, and policy checks

#### Pulse and FinOps

- read unified coordinator and observability data
- stop inferring lifecycle state independently

### 5.4 Tool Layer

Keep `batch_execute()` as the concurrency primitive and standardize tool contracts around structured results where practical:

- success/failure status
- provider or backend used
- typed payload or artifact reference
- retryability and roadblock reason when relevant

Filesystem guardrails remain intact and the same safety mindset is extended to:

- GitHub writes and PR actions
- scraper access and content limits
- sandbox execution policy
- Smithery/MCP calls

## 6. Phased Roadmap

### Phase 1: Execution Architecture Unification

- introduce the execution backend boundary used by agents and orchestration logic
- integrate planner fallback behind that boundary
- remove `planned_main.py` as a parallel production workflow
- keep ADK session/callback/runner behavior as the default path

### Phase 2: Task Lifecycle and Coordination

- centralize task creation/update logic behind the coordinator
- define explicit statuses and legal transitions
- separate short-lived runtime state from durable backlog/roadmap state
- make Pulse, CLI, dashboard, and autonomous logic consume the same lifecycle contract

### Phase 3: Safety, Evaluation, and Delivery Hardening

- add structured review gates for Builder output
- tighten tool contracts and fallback semantics
- implement explicit roadblock reporting for external dependency failures
- require Critic/coordinator approval before delivery actions

## 7. Task Lifecycle Contract

The implementation plan should assume a single shared lifecycle model. The exact status names may be refined during implementation, but the flow must cover:

- `PENDING`
- `IN_PROGRESS`
- `BUILT`
- `REVIEWED`
- `DELIVERED`
- stalled, retry, and failed variants

The important requirement is not the spelling of the statuses but that:

- transitions are validated centrally
- all user-facing status surfaces render from the same underlying model
- roadblocks and retry reasons are visible, not hidden in free-form logs

## 8. Error Handling and Roadblock Policy

The redesign must distinguish between:

### 8.1 Execution Fallback

Cases where the system can continue by switching backend behavior, for example:

- ADK-native tool call failed due to model behavior
- planner fallback can still complete the operation safely

### 8.2 Workflow Failure

Cases where the business workflow itself failed, for example:

- Builder produced an invalid artifact
- Critic blocked the change
- budget exceeded
- GitHub delivery unavailable
- scraper access denied or sandbox timed out

These outcomes should be recorded as first-class coordinator events so Pulse, dashboard, CLI, and future eval flows can report *why* work stalled.

## 9. Testing Strategy

The redesign should preserve targeted tests already present in the repo and add focused tests around the new seams:

1. execution adapter chooses ADK-native vs planner fallback correctly
2. coordinator enforces valid task status transitions
3. roadblock events propagate consistently to state, CLI, dashboard, and Pulse
4. Builder and Critic structured results feed one delivery path
5. autonomous SDLC path and interactive swarm path share the same lifecycle contract

The plan should bias toward targeted `pytest` coverage instead of relying only on full end-to-end orchestration to verify core workflow semantics.

## 10. Scope Boundaries

### In Scope

- Python runtime architecture under `src/main.py`, `src/planner.py`, `src/autonomous_sdlc.py`, `src/agents/`, `src/tools/`, `src/services/`, and `src/observability/`
- task lifecycle and coordination behavior
- tool safety and structured evaluation/delivery behavior
- roadmap structure covering all three enhancement areas as phases

### Out of Scope

- rewriting the Kotlin/Android game code under `src/main/java/`
- replacing Google ADK with a different framework
- redesigning unrelated UI or non-Python assets
- speculative new agent personas not required for the phased roadmap

## 11. Planning Handoff

This spec is ready for implementation planning as a **single roadmap with phased execution**, not as unrelated independent projects.

The implementation plan should:

- start with execution-architecture unification
- then define the coordinator and lifecycle contract
- then harden tool safety, review, and delivery gates

Known directories to carry forward into planning:

- `src/`
- `src/agents/`
- `src/tools/`
- `src/services/`
- `src/observability/`
- `src/cli/`
- `tests/`
