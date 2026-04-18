# Design Specification: PydanticAI and Graph-Oriented Swarm Integration

**Date:** 2026-04-18
**Status:** Approved
**Framework:** Google ADK + LiteLLM/OpenRouter
**Topic:** Integrating PydanticAI, Instructor, LangGraph/LangChain, and LlamaIndex into the current autonomous swarm without replacing the existing ADK control plane

## 1. Executive Summary

The current Python swarm already has a clear top-level control plane in `src/main.py`, `src/agents/orchestrator.py`, `src/tools/dispatcher.py`, and the newer capability layer. Its main risk is architectural drift: the repo already carries an ADK-native runtime plus planner-oriented compatibility logic, so any new framework integration must avoid creating another competing orchestration product inside the same codebase.

This design keeps **Google ADK** as the only top-level runtime and introduces four supporting layers:

1. **PydanticAI** for typed agent decisions and structured role handoffs
2. **Instructor + Pydantic** for schema enforcement on existing LiteLLM-driven paths that are not migrated immediately
3. **LangGraph/LangChain** for bounded branch/loop-heavy subflows only
4. **LlamaIndex** for capability-backed retrieval, memory, and RAG where additional context measurably improves orchestration quality

The goal is stronger autonomous team coordination, better decision quality, and safer extensibility for both current and future agents, including not-yet-named software-improvement specialists.

## 2. Goals

- Strengthen autonomous team orchestration and role coordination without replacing ADK
- Introduce typed, schema-validated handoffs between orchestration, planning, execution, review, and operational roles
- Add explicit support for workflow loops and branches where the current swarm needs retry, rework, or multi-lane execution logic
- Enable future software-focused specialist agents to join the swarm through typed contracts instead of ad hoc prompt additions
- Add optional retrieval and memory augmentation for planning and decision-making without forcing RAG into every workflow
- Produce a `/fleet`-ready planning surface with phase ordering, simulation gates, and impact score reporting

## 3. Current-State Findings

### 3.1 Strengths

- `src/main.py` remains a solid ADK-based swarm entrypoint with session services, callbacks, queue processing, and runtime tool registration.
- `src/agents/orchestrator.py` already centralizes top-level delegation and now prefers shared capability-backed operations.
- `src/tools/dispatcher.py` and `src/capabilities/` provide the right place to standardize tool and backend contracts.
- `src/planner.py`, `src/planned_main.py`, and `src/autonomous_sdlc.py` expose the exact seams where typed outputs, graph loops, and prompt hardening would have the most leverage.
- Existing agent roles are already separated conceptually into orchestration, ideation, building, critique, health, and cost concerns.

### 3.2 Gaps

- Agent handoffs still rely heavily on prompt text, free-form strings, and inconsistent result shapes.
- The planner compatibility path is still fragile enough that any new framework could accidentally become a second orchestration stack.
- Review, retry, and branch logic are distributed across prompts and ad hoc loops instead of being modeled as explicit state transitions.
- Retrieval and prior-run knowledge are available only indirectly; the system lacks a coherent RAG and memory strategy.
- There is no formal onboarding contract for future specialist agents, even though the swarm increasingly needs focused software-improvement roles.

## 4. Scope

### In Scope

- Python swarm architecture under `src/main.py`, `src/agents/`, `src/planner.py`, `src/planned_main.py`, `src/autonomous_sdlc.py`, `src/capabilities/`, `src/tools/`, `src/services/`, and `src/observability/`
- Typed role contracts and schema-enforced outputs
- Bounded workflow graph integration for loops, retries, and branches
- Capability-backed retrieval and memory integration
- Specialist-agent onboarding rules for current and future software-focused agents
- Simulation and impact-scoring surfaces needed to justify rollout
- A phased design suitable for conversion into a `/fleet` execution prompt

### Out of Scope

- Replacing Google ADK as the control plane
- Rewriting the Kotlin/Android code under `src/main/java/`
- Converting every existing prompt or agent to a new framework in one pass
- Forcing LlamaIndex or RAG into workflows that do not need retrieval
- Inventing specific future specialist personas before the contract for onboarding them exists

## 5. Recommended Approach

### 5.1 Chosen Strategy: ADK-Controlled Hybrid Integration

The recommended approach is a **hybrid integration model**:

- **ADK** remains the single owner of top-level session lifecycle, routing, and user-facing control flow
- **PydanticAI** becomes the preferred layer for typed decisions, structured agent outputs, and high-trust handoff contracts
- **Instructor** serves as a bridge for current LiteLLM/OpenRouter paths that still need schema enforcement before deeper migration
- **LangGraph/LangChain** are used only inside bounded subflows that need explicit branches, retries, or loops
- **LlamaIndex** is exposed through a capability-backed retrieval surface for RAG and memory when it improves decisions

### 5.2 Alternatives Considered

- **ADK-only extension:** lower dependency count, but weaker support for strict typed agent contracts and bounded graph workflows
- **LangChain-centric orchestration:** better graph expressiveness, but too likely to create a second competing runtime
- **PydanticAI-first full rewrite:** strong typing, but too disruptive for the current ADK- and capability-oriented codebase

The chosen hybrid path is preferred because it improves autonomy and decision quality while preserving existing architecture ownership.

## 6. Target Architecture

### 6.1 Runtime Ownership

- `src/main.py` remains the single production runtime entrypoint
- `src/agents/orchestrator.py` remains the top-level routing agent
- ADK `Runner` remains the authoritative execution runtime
- New frameworks operate as subordinate services behind explicit boundaries, not as new top-level runtimes

### 6.2 Concern Ownership by Framework

| Concern | Primary owner |
| --- | --- |
| Top-level orchestration, sessions, queue loop, CLI compatibility | Google ADK |
| Typed agent decisions, structured role contracts, validated tool/result schemas | PydanticAI + Pydantic |
| Schema enforcement on existing LiteLLM-driven prompt flows | Instructor |
| Review/rework loops, retry graphs, branch-heavy subflows | LangGraph / LangChain |
| Retrieval, memory, and RAG context assembly | LlamaIndex |
| Shared runtime operations, repo reads, backend routing | Existing capability layer and dispatcher |

### 6.3 Proposed Integration Units

- `src/services/agent_contracts.py`
  - shared Pydantic models for delegation, task proposals, build briefs, review verdicts, retry reasons, and specialist-agent registration
- `src/services/agent_decisions.py`
  - PydanticAI-backed decision helpers used by Orchestrator, Ideator, Critic, and autonomous coordination paths
- `src/services/workflow_graphs.py`
  - LangGraph-managed bounded subflows such as review-to-rework, triage-to-delegate, and autonomous retry sequences
- `src/services/retrieval_context.py`
  - LlamaIndex-backed retrieval and memory assembly behind the capability layer
- `src/services/specialist_registry.py`
  - typed onboarding surface for future unnamed software-focused agents
- tests under `tests/services/`, `tests/agents/`, and `tests/capabilities/`
  - focused contract, graph, and retrieval simulations

These file names are illustrative but intentionally narrow; the implementation plan may refine filenames while preserving the module boundaries and responsibilities.

## 7. Orchestrated Groups and Specialist Expansion

The system should be treated as five governed orchestration groups plus an open specialist lane:

### 7.1 Control Group

- primary role: top-level routing, policy checks, delegation decisions
- current owner: `Orchestrator`
- enhancement: typed routing policies, capability selection contracts, specialist-lane activation

### 7.2 Discovery Group

- primary role: ideation, research, task proposal, context assembly
- current owner: `Ideator` and research helpers
- enhancement: structured task proposal schemas, retrieval-assisted planning, specialist recommendations

### 7.3 Execution Group

- primary role: implementation, staging, iterative change production
- current owner: `Builder`
- enhancement: validated build briefs, bounded rework loops, clearer upstream/downstream contracts

### 7.4 Governance Group

- primary role: review, block/retry decisions, policy and quality gates
- current owner: `Critic`
- enhancement: typed verdict models (`pass`, `retry`, `block`), explicit failure reasons, rubric-backed judgments

### 7.5 Operations Group

- primary role: autonomous loops, health, cost, and status awareness
- current owners: `Pulse`, `FinOps`, `autonomous_sdlc`
- enhancement: typed telemetry events, graph-managed retries, retrieval over prior outcomes when useful

### 7.6 Specialist Lane

The design must support **additional yet unnamed software-focused agents**. These future agents may cover any engineering-improvement function that emerges later, including refactoring, workflow optimization, testing depth, architecture assistance, release readiness, evaluation, or domain-specific implementation work.

Requirements for specialist agents:

- they register through one typed onboarding contract
- they declare role, inputs, outputs, capability needs, and escalation rules
- they can be selected by Orchestrator and Discovery using the same validated delegation model as first-class agents
- they do not bypass ADK routing, capability boundaries, or review gates

## 8. High-Value Use Cases

### 8.1 Typed Delegation Loop

Orchestrator emits a validated delegation contract, Ideator or a specialist returns a validated task proposal, Builder receives a typed build brief, and Critic returns a structured verdict. This replaces free-form prompt coupling with explicit contracts.

### 8.2 Review-to-Rework Graph

When Critic returns `retry`, the system enters a LangGraph-managed bounded loop that can re-brief Builder, route to a specialist, or stop after policy-defined attempts. ADK still owns the outer execution lifecycle.

### 8.3 Retrieval-Backed Planning

Ideator, Orchestrator, and future specialists retrieve prior specs, plans, issues, or run summaries through a LlamaIndex-backed capability surface to improve planning quality and reduce repeated mistakes.

### 8.4 Specialist Activation

Discovery identifies a software-improvement opportunity and routes it to either a current agent or a specialist lane based on typed routing criteria rather than ad hoc prompt wording.

### 8.5 Autonomous Campaign Mode

The autonomous SDLC path uses a bounded graph of discovery, planning, build, review, and delivery checkpoints with explicit retry and stop semantics, typed scores, and retrieval-aware planning when necessary.

## 9. Phased Rollout

### Phase 0: Simulation and Contract Baseline

- define the first set of Pydantic contracts for role handoffs
- create simulation scenarios for orchestration, review loops, autonomous cycles, and retrieval-assisted planning
- establish baseline impact scores for each orchestrated group

### Phase 1: Decision Contract Layer

- introduce shared Pydantic/PydanticAI models for delegation, task proposals, verdicts, and specialist registration
- wrap remaining LiteLLM-only structured outputs with Instructor
- keep existing orchestration behavior stable while upgrading output safety

### Phase 2: Orchestration Uplift

- integrate typed decision helpers into Orchestrator, Ideator, Critic, and autonomous coordination paths
- let Discovery and Control decide whether to route work to core agents or specialist lanes
- preserve current capability-layer and dispatcher ownership

### Phase 3: Graph-Managed Subflows

- add LangGraph-managed loops for review-to-rework, research-to-delegate, and bounded autonomous retries
- keep graph logic subordinate to ADK routing and session control

### Phase 4: Retrieval and Memory

- add LlamaIndex-backed retrieval over approved sources such as specs, plans, history, and prior run artifacts
- expose retrieval through capabilities so all current and future agents use one consistent access surface

### Phase 5: Fleet Adoption

- convert the approved plan into a `/fleet` prompt with dependency-aware work packages
- add simulation gates and impact score reporting to each landing phase
- include a specialist-onboarding lane as part of the fleet execution model

## 10. Impact Score Model

Each orchestrated group should be evaluated on:

- **Reliability:** schema-valid outputs and fewer malformed handoffs
- **Autonomy Lift:** fewer manual interventions and less orchestration drift
- **Decision Quality:** better routing, review, and retry choices
- **Integration Effort:** complexity and risk required to land the improvement
- **Confidence:** strength of the evidence from simulations and targeted tests

The initial priority order for rollout should be:

1. Control Group
2. Governance Group
3. Discovery Group
4. Operations Group
5. Execution Group
6. Specialist Lane onboarding surface

Builder-specific graph complexity is intentionally not first even though Builder is important; routing and review contracts deliver more systemic leverage earlier.

## 11. Simulation and Evaluation Strategy

The design must define focused simulations before broad rollout:

1. **Delegation simulation**
   - compare baseline routing with typed routing across Orchestrator, Ideator, Specialist lane, and Builder
2. **Review-loop simulation**
   - model Critic `retry/block/pass` outcomes and verify bounded graph behavior
3. **Autonomous campaign simulation**
   - simulate backlog triage, build, review, and retry behavior over multiple cycles
4. **RAG-assisted planning simulation**
   - compare planning quality with and without retrieval context

Success criteria:

- structured outputs validate consistently
- branch and loop paths stop safely
- specialist activation follows explicit routing rules
- retrieval improves targeted decisions without contaminating unrelated workflows
- impact score deltas are explainable per group

## 12. Failure Modes and Guardrails

The implementation must explicitly guard against:

- a second competing runtime emerging beside ADK
- LangGraph graphs expanding into uncontrolled top-level orchestration
- LlamaIndex retrieval being used by default where no measurable gain exists
- specialist agents being added without typed contracts, escalation rules, or review policy
- structured output failures being hidden as free-form text success
- review or retry loops running without bounded stop criteria

Failures in any of these areas should fail closed and route through existing coordinator, capability, or review surfaces rather than silently degrading.

## 13. Testing Strategy

Implementation planning should favor focused tests around:

- Pydantic contract validation for all handoff types
- Instructor-guarded LiteLLM outputs for legacy prompt surfaces
- PydanticAI decision helpers used by orchestration and review
- LangGraph branch and retry semantics
- capability-backed retrieval and memory integration
- specialist registration and routing rules
- per-group simulation scoring and result reporting

The plan should prefer deterministic targeted tests and scenario simulations over broad uncontrolled end-to-end runs.

## 14. Planning Handoff

This spec is ready for implementation planning as a **single phased roadmap** whose final artifact includes a `/fleet` prompt.

The implementation plan should:

- preserve ADK as the only top-level runtime
- land typed contracts and Instructor bridges before graph and retrieval work
- treat LangGraph as bounded subflow logic, not global orchestration
- make LlamaIndex retrieval capability-backed and opt-in by use case
- define a typed onboarding surface for unnamed future specialist agents
- include simulation gates and impact score reporting in the final fleet handoff

Known files and directories to carry forward into planning:

- `src/main.py`
- `src/agents/`
- `src/planner.py`
- `src/planned_main.py`
- `src/autonomous_sdlc.py`
- `src/capabilities/`
- `src/tools/`
- `src/services/`
- `src/observability/`
- `tests/`
- `docs/superpowers/specs/`
- `docs/superpowers/plans/`
