# Design Specification: Dedicated Thin Harness Layer for the ADK Swarm

**Date:** 2026-04-18
**Status:** Approved for planning
**Topic:** Go/no-go recommendation on adopting a dedicated agent harness layer
**Decision:** **Go**, with a thin harness layer that remains subordinate to Google ADK

## 1. Executive Summary

This repository should adopt a **dedicated thin harness layer** around the existing ADK runtime. The current system already contains most of the ingredients of a production harness—session persistence, tool mediation, retrieval, guardrails, observability, and task state—but those concerns are scattered across the entrypoint and service modules instead of being owned by one explicit runtime boundary.

The recommendation is **not** to introduce a new top-level runtime, workflow engine, or competing orchestrator. The recommendation is to keep **Google ADK** as the control plane and add a harness layer beneath `src/main.py` and around the ADK `Runner` so production concerns are enforced consistently.

## 2. Problem Statement

The system currently behaves like a **partial harness** rather than a full one:

- `src/main.py` wires tools, capabilities, telemetry, session creation, and the ADK runner directly.
- `src/tools/dispatcher.py` and `src/capabilities/*` already form a tool/capability gateway, but they are not treated as the canonical runtime boundary.
- `src/state.py`, `src/services/session_store.py`, retrieval, cost tracking, and history each persist state independently.
- Guardrails and observability exist, but they are point solutions rather than centrally owned runtime policies.

This fragmentation makes it harder to reason about identity, policy enforcement, memory/state coordination, auditability, and long-running reliability.

## 3. Goals

- Make the swarm's production infrastructure explicit without replacing ADK.
- Centralize runtime context, state coordination, tool mediation, policy enforcement, and observability.
- Keep the orchestrator and specialist agents focused on reasoning and delegation rather than infrastructure concerns.
- Improve decision-grade clarity for future planning by defining what the harness owns and what it must never own.
- Preserve a medium-change migration path that does not require a new runtime or service boundary.

## 4. Non-Goals

- Replacing Google ADK as the control plane.
- Moving orchestration logic out of `src/agents/orchestrator.py`.
- Introducing a second top-level runner, external harness daemon, or sidecar runtime.
- Pulling prompts, delegation policy, or business logic into the harness layer.
- Solving enterprise-grade multi-tenancy in the first iteration.

## 5. Current-State Evidence

### 5.1 Harness-like capabilities already present

1. **ADK control plane exists now**
   - `src/main.py` boots the runtime, creates `SQLiteSessionService`, creates the ADK `Runner`, and executes the orchestrator.
   - `src/services/session_store.py` re-exports ADK's SQLite session service.

2. **Multi-agent routing already exists**
   - `src/agents/orchestrator.py` delegates work to specialist agents.

3. **Tool and capability mediation already exists**
   - `src/tools/dispatcher.py` provides tool registration, capability routing, standard result envelopes, and concurrency limits.
   - `src/capabilities/service.py` and `src/capabilities/registry.py` provide a narrow execution surface.

4. **Persistence already exists, but across multiple stores**
   - ADK session storage via SQLite.
   - JSON task/event state in `src/state.py`.
   - File-backed queue/control-plane state in `src/cli/swarm_ctl.py`.
   - Metrics, cost, and history in separate observability services.

5. **Retrieval and memory-like behavior already exists**
   - `src/services/retrieval_context.py` validates and exposes planning retrieval.

6. **Guardrails already exist**
   - Filesystem restrictions in `src/tools/filesystem.py`.
   - Output/content controls and sandboxing in related tool modules.

7. **Observability already exists**
   - `src/observability/adk_callbacks.py` and related telemetry/logger modules provide traces, metrics, and logging.

### 5.2 Current gaps

1. **Split-brain persistence**
   - State, session, queue, metrics, and audit concerns are persisted through separate mechanisms with no unified abstraction.

2. **Identity and authorization are not harness-owned**
   - Runtime ingress uses hardcoded or weakly propagated user identity today.

3. **Cross-cutting concerns are embedded in the entrypoint**
   - `src/main.py` owns too much runtime assembly and policy-adjacent behavior.

4. **Memory is narrow**
   - Retrieval is planning-focused and not yet a general runtime/session memory boundary.

5. **Reliability controls are local, not systemic**
   - File-based state writes and queueing are simple and effective for today, but not governed through one runtime contract.

6. **Observability is present, but not unified as a run envelope**
   - Logs, traces, metrics, and audit semantics are not coordinated through a single harness surface.

## 6. Recommendation

## **Go**

Adopt a **dedicated thin harness layer** because:

1. The repository already has most of the necessary ingredients.
2. The missing work is mostly consolidation and ownership, not invention.
3. A thin harness matches the user's medium-change tolerance.
4. The existing architecture already prefers ADK as the sovereign runtime.

## **No-go only if**

The desired outcome changes into one of these:

- a separate runtime or sidecar service becomes mandatory,
- the harness is expected to own agent reasoning or orchestration,
- or immediate hard-isolation/multi-tenant guarantees are required.

Under those conditions, the system would no longer be adding a thin harness; it would be replacing the current runtime shape.

## 7. Proposed Architecture

### 7.1 Placement

The harness should sit **under the entrypoint and around ADK runtime wiring**:

```text
prompt ingress
    |
src/main.py
    |
HarnessRuntime
    |
ADK Runner
    |
orchestrator + specialist agents
```

This keeps ADK as the only control plane while making the harness the explicit owner of runtime infrastructure.

### 7.2 Ownership boundaries

The harness should own:

1. **Runtime context**
   - run/session metadata
   - trace correlation
   - ingress identity and request metadata

2. **Persistence coordination**
   - ADK session persistence
   - task/event state coordination
   - audit and artifact write paths

3. **Tool mediation**
   - capability execution
   - concurrency limits
   - standard envelopes
   - policy checks before tool execution

4. **Memory and retrieval boundary**
   - retrieval adapters
   - future episodic/session memory
   - caching and corpus policy

5. **Guardrails and policy**
   - filesystem policy
   - output/content controls
   - future authn/authz, budget, and rate policies

6. **Observability**
   - callback setup
   - trace/log/metric correlation
   - audit linkage between runs, tools, and state changes

The harness should **not** own:

- agent prompts,
- delegation policy,
- business logic,
- or a second runtime loop.

### 7.3 Target module shape

One reasonable target is:

```text
src/
  harness/
    runtime.py
    ingress.py
    context.py
    persistence.py
    memory.py
    tool_gateway.py
    guardrails.py
    observability.py
```

This is a design target, not a requirement for a single-step refactor. The plan may keep some existing modules in place and place harness ownership over them before moving code physically.

## 8. Runtime Flow

The intended runtime flow is:

1. A prompt enters through CLI or queue ingestion.
2. The harness establishes a run context with identity, session, and trace metadata.
3. The harness builds or prepares the ADK runner and injects shared runtime services.
4. The orchestrator executes normally through ADK.
5. Tool calls, retrieval, and state-affecting operations pass through harness-owned mediation.
6. The harness emits consistent telemetry, audit information, and policy decisions for the run.

This flow keeps the orchestrator focused on reasoning while the harness becomes the production control surface around it.

## 9. Validation and Research Frame

This design is intentionally framed as a **decision-grade architecture recommendation**, not an immediate implementation plan. The next planning step should validate the recommendation through a bounded research frame:

1. **Responsibility inventory**
   - Map current harness-like responsibilities to concrete modules.

2. **Minimum viable harness surface**
   - Define the thinnest useful runtime contract that can wrap existing services without introducing a second control plane.

3. **Gap verification**
   - Confirm the most important missing capabilities: identity propagation, centralized policy, unified run context, persistence coordination, and audit consistency.

4. **Migration boundary checks**
   - Ensure prompts, orchestration logic, and agent business behavior remain outside the harness.

5. **Exit criteria for the recommendation**
   - If the thin layer can absorb cross-cutting runtime concerns without competing with ADK, the recommendation remains **go**.
   - If achieving those goals would require a separate runtime or major control-plane replacement, revisit the recommendation.

## 10. Risks and Trade-offs

### 10.1 Main risk: creating a shadow runtime

This is the architectural failure mode to avoid. The harness must never become a second orchestrator or a competing session engine.

### 10.2 Added indirection

The harness adds one more layer of abstraction, but that trade-off is justified because `src/main.py` currently mixes bootstrapping, runtime policy, and assembly concerns.

### 10.3 Migration complexity

The migration should be incremental. The harness should first consolidate runtime assembly, context propagation, and tool mediation before broader persistence or memory work.

## 11. Planning Readiness

This spec is intentionally scoped for a **single planning track**:

- decide the initial harness boundary,
- define what existing modules move under harness ownership first,
- and produce a phased migration sequence that keeps ADK as the top-level runtime.

The first plan should not include unrelated refactors or a second runtime architecture.
