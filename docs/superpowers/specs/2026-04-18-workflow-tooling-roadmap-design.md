# Design Specification: Workflow Tooling Roadmap for ADK + LiteLLM

**Date:** 2026-04-18
**Status:** Approved
**Framework:** Google ADK + LiteLLM/OpenRouter Python runtime
**Topic:** Phased roadmap for repo-local workflow tooling spanning capability contracts, a local MCP server, skills/agent helpers, and plugin or extension surfaces

## 1. Executive Summary

The current repo already exposes several workflow surfaces:

1. **runtime tool registration** in `src/main.py`
2. **shared concurrent tool execution** in `src/tools/dispatcher.py`
3. **agent orchestration** in `src/agents/orchestrator.py`
4. **operator-facing CLI and command surfaces** in `src/cli/swarm_cli.py` and `.claude/commands/swarm/*.md`
5. **external tool bridging** in `src/tools/smithery_bridge.py`

The goal of this roadmap is to unify those surfaces under a single internal capability model, then expose that model through a repo-local Python stdio MCP server as the first delivery. Later phases should extend the same capability layer to repo-local skills and agent helpers, then to plugin or extension packaging, without duplicating logic across transport surfaces.

## 2. Goals

- Create one phased roadmap covering:
  - repo-local skills and agent helpers
  - plugin or extension tooling
  - MCP support
- Prioritize a **repo-local Python stdio MCP server** as the first implementation phase
- Keep the system ready for a later **MCP bridge or client layer**
- Make the repo's own ADK/LiteLLM swarm runtime the first consumer
- Prevent logic drift across ADK tools, CLI commands, command markdown, MCP handlers, skills, and plugins by introducing one shared capability layer

## 3. Current-State Findings

### 3.1 Existing Strong Seams

- `src/main.py` already acts as a central registration point for tool functions
- `src/tools/dispatcher.py` already provides a global concurrency boundary for independent tool work
- `src/tools/smithery_bridge.py` proves the runtime already needs a backend abstraction for externally sourced tools
- `src/agents/orchestrator.py` already contains a high-level instruction layer that can benefit from capability-backed tool contracts
- `.claude/commands/swarm/*.md` and `src/cli/swarm_cli.py` already represent separate operational surfaces that risk duplicating workflow logic

### 3.2 Primary Structural Risk

The repo is at risk of **surface sprawl**:

- ADK tool registration
- direct Python tool functions
- CLI subcommands
- command markdown
- Smithery-backed tools
- future MCP endpoints
- future skills and plugins

Without a shared capability contract, each surface could develop its own naming, result shapes, retries, and routing logic.

## 4. Recommended Approach

### 4.1 Chosen Strategy: Capability-First, Transport-Thin

The recommended strategy is to introduce a single internal capability layer and treat all outward-facing surfaces as adapters.

This means:

- the **capability layer** owns canonical capability names, typed input/output contracts, backend selection, and execution policy
- the **MCP server** becomes a thin transport adapter over the capability layer
- the **ADK runtime**, **CLI**, **command markdown**, **future skills**, and **future plugins/extensions** all consume the same capability contracts

This is preferred because the repo already has multiple execution surfaces but does not yet have a shared abstraction to keep them aligned.

## 5. Target Architecture

### 5.1 Layer Model

```text
Consumers
├─ ADK swarm runtime / orchestrator
├─ local CLI (`swarm_cli`)
├─ command markdown (`.claude/commands/swarm/*.md`)
├─ future skills / agent helpers
└─ future plugins / extensions / MCP clients

        ↓

Capability Layer
├─ capability contracts / schemas
├─ capability registry
├─ execution policy
└─ backend routing

        ↓

Execution Backends
├─ local Python tools
├─ dispatcher-mediated concurrent execution
├─ Smithery-backed external tools
└─ future MCP bridge/client backend

        ↓

Transport Surfaces
├─ Phase 1: repo-local Python stdio MCP server
└─ Later: MCP bridge/client layer and packaging surfaces
```

### 5.2 Capability Layer Responsibilities

The capability layer should be the single source of truth for:

- capability names
- input and output contracts
- backend selection
- retryability metadata
- source backend attribution
- access policy and execution rules

The capability layer should decide whether a request runs:

- through a local tool
- through dispatcher-governed concurrent execution
- through Smithery
- through a future MCP bridge or client backend

### 5.3 Transport Responsibilities

Transport surfaces must not own business logic.

- the MCP server should only validate incoming requests, invoke the capability layer, and return standardized responses
- the CLI and command surfaces should only translate user input or display concerns
- future plugins and extensions should package and expose the same capabilities rather than define new ones

## 6. Phase Roadmap

### 6.1 Phase 1 — Capability Foundation + Local stdio MCP Server

This is the first implementation phase.

#### In Scope

- introduce capability contracts and a capability registry
- wrap a small set of existing workflow operations behind capability interfaces
- build a repo-local Python stdio MCP server
- use the repo's own ADK/LiteLLM swarm runtime as the first consumer
- expose low-risk operational capabilities first

#### Initial Capability Set

The initial MCP-capable capability set should be limited to read-only or low-risk operations:

- swarm status, task, event, and queue views
- guarded repo file listing and reads that align with current filesystem policies
- a narrow workflow helper shortlist such as status-style inspection helpers and repo-context helpers that already align with current runtime guardrails
- controlled Smithery-backed capabilities exposed through the capability layer only where they can return the standard capability envelope

During Phase 1, the swarm runtime should act as a **narrow initial consumer** of the new capability layer so the contracts can be proven without broad refactoring of every existing runtime path.

#### Out of Scope

- remote hosted MCP deployment
- broad external marketplace packaging
- exposing every existing tool immediately
- adding business logic directly in MCP handlers

### 6.2 Phase 2 — Swarm Runtime Integration

- expand from the narrow Phase 1 consumer path into broader runtime integration
- update the runtime to prefer capability-backed tools where practical
- align orchestrator-facing tool contracts with the capability registry
- route concurrent capability work through `src/tools/dispatcher.py`
- make Smithery one backend behind the capability layer rather than a separate top-level surface

### 6.3 Phase 3 — Shared Surface Unification

- refactor `src/cli/swarm_cli.py` and `.claude/commands/swarm/*.md` toward capability-backed entrypoints
- add a thin helper API for future skills and agent helpers
- reduce duplicated formatting, routing, and result-shape logic across operator surfaces

### 6.4 Phase 4 — MCP Bridge or Client Layer

- add an abstraction for out-of-process MCP consumption
- preserve the same capability contracts and envelopes
- allow future configuration-based routing between local tools, Smithery, and MCP-backed execution

### 6.5 Phase 5 — Plugin or Extension Packaging

- package workflow surfaces for plugin or extension-style distribution
- keep these surfaces thin and packaging-focused
- avoid adding new domain logic in this phase

## 7. Result Contract

All capability-backed calls should converge on a standard result envelope before broad rollout.

Recommended fields:

- `status`
- `payload`
- `error`
- `source_backend`
- `retryable`

This is important because the current codebase mixes strings and dict-like outputs across different tool paths. A standard envelope is required before MCP, CLI, commands, and skills can safely share one execution model.

## 8. Safety and Execution Rules

### 8.1 Safety Rules

- keep Phase 1 focused on read-only or low-risk operations
- preserve existing filesystem guardrails instead of widening them
- avoid direct write or mutation capabilities until contracts and policies are stable
- keep transport layers thin so later bridge/client work does not require a rewrite

### 8.2 Execution Rules

- parallelizable capability work should still flow through `src/tools/dispatcher.py` where concurrency policy matters
- Smithery-backed behavior should be normalized as one backend path rather than its own user-facing workflow surface
- CLI commands, command markdown, ADK tools, and MCP tools should not invent different result shapes or retries

## 9. Validation Strategy

Each phase should land with targeted tests for the affected seam.

### Phase 1 Validation

- contract tests for capability schemas and result envelopes
- registry tests for capability lookup and backend routing
- MCP server tests for tool exposure, schema validation, and response shape

### Phase 2 Validation

- focused runtime integration tests for capability-backed orchestrator and tool registration paths
- concurrency-aware tests proving capability execution still respects dispatcher behavior

### Phase 3 Validation

- CLI and command-surface tests proving operator views continue to work while reusing shared capability-backed entrypoints

### Phase 4+ Validation

- compatibility tests that prove local and bridge/client modes preserve the same capability contracts

## 10. Risks and Mitigations

### Risk: result-shape drift across surfaces

- **Mitigation:** define a standard envelope at the capability layer before broad rollout

### Risk: MCP handlers become a second implementation stack

- **Mitigation:** keep MCP transport thin and capability-driven

### Risk: concurrency limits are bypassed by new surfaces

- **Mitigation:** route parallelizable work through `src/tools/dispatcher.py`

### Risk: Smithery remains a side path instead of a backend

- **Mitigation:** move Smithery-backed calls behind capability routing rather than exposing them as an unrelated integration surface

### Risk: plugins or extensions fork the workflow model

- **Mitigation:** delay packaging until after the capability layer and MCP contracts are stable

## 11. Scope Boundaries

### In Scope

- a single phased roadmap covering capabilities, a local MCP server, later skills/agent helpers, and later plugin/extension surfaces
- a repo-local Python stdio MCP server as the first implementation phase
- capability contracts and backend-routing design
- runtime-first consumption by the repo's own ADK/LiteLLM swarm

### Out of Scope

- replacing Google ADK or LiteLLM
- broad unrelated refactors
- immediate support for every existing tool surface
- direct implementation of all plugin or extension packaging details in the first phase
- remote hosted MCP deployment in the first phase

## 12. Planning Handoff

This spec is ready for implementation planning as a single phased workflow-tooling roadmap.

Planning should:

1. start with the capability layer and local stdio MCP server
2. define the first capability set and its contracts
3. identify how `src/main.py`, `src/agents/orchestrator.py`, `src/tools/dispatcher.py`, and `src/tools/smithery_bridge.py` will be integrated without duplicating logic
4. attach targeted tests to each rollout phase
5. defer broad plugin or extension packaging until capability and MCP seams are stable

Known files and directories to carry into planning:

- `src/main.py`
- `src/agents/orchestrator.py`
- `src/tools/dispatcher.py`
- `src/tools/smithery_bridge.py`
- `src/cli/swarm_cli.py`
- `.claude/commands/swarm/`
- `src/config.py`
- `src/tools/`
- `tests/`
- planned additions under `src/capabilities/`, `src/mcp/`, `tests/capabilities/`, and `tests/mcp/`
