# Design Specification: Python Package Installation and Integration Roadmap

**Date:** 2026-04-18
**Status:** Approved
**Framework:** Google ADK + LiteLLM/OpenRouter Python runtime
**Topic:** Phased installation and integration of 10 Python packages to strengthen runtime reliability, planner correctness, observability, testing, caching, and persistence

## 1. Executive Summary

The current Python system centers on five connected seams:

1. **runtime orchestration** in `src/main.py`
2. **planner and prompt/tool-call parsing** in `src/planner.py`
3. **workflow automation** in `src/planned_main.py` and `src/autonomous_sdlc.py`
4. **tool adapters and external dependencies** in `src/tools/`
5. **logging, metrics, state, and sessions** across `src/observability/`, `src/state.py`, and `src/services/`

The goal of this roadmap is to install and integrate 10 additional Python packages in a way that strengthens those seams without turning the system into a large uncontrolled refactor. The rollout should prioritize the highest-leverage packages first, then phase in the remaining ones behind the same integration discipline.

## 2. Goals

- Provide a concrete installation and integration roadmap for 10 additional Python packages
- Tie each package to a real interaction seam in the current codebase
- Prioritize the top 3-5 packages for immediate installation while still covering all 10 in the roadmap
- Keep each package rollout additive, testable, and reversible
- Avoid package sprawl by giving every dependency a clear integration owner and test surface

## 3. Current-State Findings

### 3.1 Existing Dependency Baseline

The current `requirements.txt` is intentionally small and focused:

- Google ADK / Vertex stack
- LiteLLM
- Playwright
- PyGitHub
- dotenv
- pytest + pytest-asyncio
- rich
- prompt_toolkit
- duckduckgo-search

### 3.2 Highest-Value Seams

- `src/planner.py` is the most brittle part of the runtime because it depends on parsing imperfect LLM text into tool calls
- `src/config.py` is minimal and would benefit from typed configuration
- `src/tools/github_tool.py`, `src/tools/smithery_bridge.py`, `src/tools/web_search.py`, and scraper/network paths have retry-sensitive external dependency behavior
- `src/observability/` is functional but lightweight, making it a strong candidate for additive tracing improvements
- `tests/` already contains useful regression surfaces, so testing-oriented packages can be integrated with immediate value

## 4. Recommended Approach

### 4.1 Chosen Strategy: Capability-Layer Rollout

The recommended strategy is to roll packages out by subsystem capability rather than one-by-one or by pure risk tier.

This means grouping installations by the seam they improve:

- typed configuration and contracts
- planner/runtime hardening
- observability
- caching and deeper tests
- persistence and performance

This is preferred because the repo already separates these concerns across `src/main.py`, `src/planner.py`, `src/tools/`, `src/observability/`, and `tests/`.

## 5. Package Roadmap

### 5.1 Phase 1 — Immediate Installation

These are the highest-priority packages for immediate integration.

#### 1. `pydantic`

- **Primary seams:** `src/planner.py`, `src/tools/dispatcher.py`, future prompt/eval services, structured task payloads
- **Benefit:** replace loose dict/string contracts with validated models for tool calls, evaluation records, and structured system data

#### 2. `tenacity`

- **Primary seams:** LiteLLM calls in `src/planner.py`, external service calls in `src/tools/github_tool.py`, `src/tools/smithery_bridge.py`, `src/tools/web_search.py`, and scraping/network paths
- **Benefit:** centralized retry/backoff behavior for flaky external dependencies

#### 3. `json-repair`

- **Primary seams:** `src/planner.py`
- **Benefit:** recover malformed but near-valid JSON blocks before the planner gives up

#### 4. `pydantic-settings`

- **Primary seams:** `src/config.py`
- **Benefit:** typed environment/config loading for models, timeouts, retries, repo settings, and feature flags

#### 5. `opentelemetry-sdk`

- **Primary seams:** `src/observability/logger.py`, `src/observability/adk_callbacks.py`, `src/main.py`, and future eval/prompt optimization flows
- **Benefit:** real traces/spans for agent runs, tool calls, retries, and evaluation events while keeping current JSON logging/metrics initially intact

### 5.2 Phase 2 — Second Wave

#### 6. `jsonschema`

- **Primary seams:** planner tool-call validation and structured evaluation artifacts
- **Benefit:** explicit schema enforcement for parsed LLM outputs

#### 7. `diskcache`

- **Primary seams:** repeated planner/evaluation/search work
- **Benefit:** persistent local caching to reduce repeated expensive operations

#### 8. `hypothesis`

- **Primary seams:** parser, task/state transitions, structured contracts, placeholder preservation
- **Benefit:** property-based tests for edge cases that hand-written unit tests miss

### 5.3 Phase 3 — Third Wave

#### 9. `aiosqlite`

- **Primary seams:** new optimization/evaluation history, future coordinator state, async persistence needs
- **Benefit:** async SQLite storage for structured history instead of adding more scattered JSON files

#### 10. `orjson`

- **Primary seams:** high-churn JSON persistence paths such as metrics, costs, events, and future optimization history
- **Benefit:** faster serialization for heavy JSON read/write paths when benchmarking shows value

## 6. Installation and Integration Workflow

### Phase 1 Workflow

#### Step A — Configuration Foundation

- install `pydantic` and `pydantic-settings`
- refactor `src/config.py` into a typed settings object
- keep compatibility with the existing env variable contract

#### Step B — Planner and Runtime Hardening

- install `tenacity` and `json-repair`
- update `src/planner.py` so LLM output passes through:
  1. raw response capture
  2. optional repair
  3. Pydantic model validation
  4. retry/fallback behavior

This is the highest-value seam because `src/planned_main.py`, `src/autonomous_sdlc.py`, and future prompt optimization flows depend on planner correctness.

#### Step C — Observability Uplift

- install `opentelemetry-sdk`
- add spans around agent execution, tool calls, retries, and planner iterations
- keep current JSON logging/metrics intact at first

### Phase 2 Workflow

#### Step D — Caching and Test Depth

- install `jsonschema`, `diskcache`, and `hypothesis`
- add persistent caching where repeated planner/eval/search work is currently recomputed
- add explicit JSON Schema validation where planner-emitted or evaluator-emitted structured payloads need an additional contract layer beyond Pydantic
- add property-based tests for parser recovery, tool contracts, and placeholder preservation

### Phase 3 Workflow

#### Step E — Persistence and Performance

- install `aiosqlite` and `orjson`
- use `aiosqlite` first for new history/eval data instead of migrating all existing persistence at once
- adopt `orjson` selectively after benchmarking targeted JSON-heavy paths

## 7. Interaction Model

The system should treat each package rollout as a three-part unit:

1. **installation** in `requirements.txt`
2. **narrow integration** at the target seam
3. **tests** for that seam

This prevents dependency additions from becoming speculative or unowned.

## 8. Validation Strategy

Each package phase should land with:

- dependency installation/update
- focused integration edits in the actual seam
- targeted tests for the seam
- a small regression subset proving existing behavior still works

Examples:

- planner hardening -> parser/tool-call tests and focused planner scenarios
- config refactor -> config-loading tests
- telemetry -> callback/logging/metrics tests
- hypothesis -> property tests for parser and state transitions
- aiosqlite -> async history store tests

## 9. Risks and Mitigations

### Risk: planner complexity grows too quickly

- **Mitigation:** land repair, schema validation, and retry in narrow steps instead of a single broad planner rewrite

### Risk: observability gets heavier than current needs

- **Mitigation:** add OpenTelemetry as an additive export layer first; keep existing JSON metrics/logging during the transition

### Risk: too many storage formats at once

- **Mitigation:** delay `aiosqlite` until after higher-leverage runtime fixes and use it only for new structured history first

### Risk: package sprawl without ownership

- **Mitigation:** each package must map to a specific file seam and test surface in the implementation plan

## 10. Scope Boundaries

### In Scope

- installation and integration planning for the 10 packages listed in this spec
- planner/runtime, config, observability, caching, testing, persistence, and JSON performance seams
- phased rollout with immediate priority on the top 3-5 packages

### Out of Scope

- replacing Google ADK or LiteLLM
- broad unrelated refactors not driven by these package seams
- adding packages that do not directly strengthen the current Python runtime paths

## 11. Planning Handoff

This spec is ready for implementation planning as a single phased dependency-integration roadmap.

Planning should:

1. prioritize `pydantic`, `pydantic-settings`, `tenacity`, `json-repair`, and `opentelemetry-sdk`
2. define narrow integration steps per seam
3. attach tests and regression checks to each package phase
4. defer `jsonschema`, `aiosqlite`, and `orjson` until the higher-leverage runtime improvements are in place

Known files and directories to carry into planning:

- `requirements.txt`
- `src/config.py`
- `src/main.py`
- `src/planner.py`
- `src/planned_main.py`
- `src/autonomous_sdlc.py`
- `src/tools/`
- `src/observability/`
- `src/services/`
- `tests/`
