# Design Specification: Prompt Optimization System

**Date:** 2026-04-17
**Status:** Approved
**Framework:** Google ADK + LiteLLM/OpenRouter
**Topic:** Automatic prompt optimization for code-generation and related orchestration prompts

## 1. Executive Summary

The Python swarm currently stores critical prompts directly inside runtime modules such as `src/agents/*.py`, `src/planner.py`, `src/planned_main.py`, and `src/autonomous_sdlc.py`. Those prompts drive code generation, task planning, tool-call formatting, and workflow behavior, but the system has no structured way to improve them over time.

This design introduces a **Prompt Optimization System** that can:

1. discover prompt-bearing code sites
2. generate prompt variants
3. evaluate baseline versus candidate behavior on fixed scenarios
4. automatically rewrite source prompts when a candidate demonstrably improves performance
5. preserve history, scores, and rollback safety

The system is designed to optimize prompt text as code, not as undocumented runtime state.

## 2. Goals

- Improve prompts that influence code generation and adjacent orchestration behavior
- Support v1 prompt targets in:
  - `src/planner.py`
  - `src/planned_main.py`
  - `src/autonomous_sdlc.py`
- Keep the design extensible so agent system prompts in `src/agents/*.py` can be onboarded in a later phase
- Automatically rewrite prompts in source when a promotion gate proves improvement
- Keep optimization measurable, repeatable, and reversible
- Make prompt improvement compatible with the broader swarm roadmap around evaluation and lifecycle hardening

## 3. Scope

### In Scope

- prompt discovery/extraction from the approved Python prompt surfaces
- candidate prompt generation
- scenario-based evaluation for baseline vs candidate prompts
- promotion rules for automatic source rewrite
- rollback behavior when post-rewrite verification fails
- prompt history and evaluation artifact tracking

### Out of Scope

- optimizing arbitrary free-form user prompts at runtime
- optimizing non-Python assets
- rewriting unrelated business logic alongside prompts
- uncontrolled self-editing during live task execution

## 4. Target Prompt Surfaces

### 4.1 Version 1 Scope

The first implementation must optimize prompt-bearing code in:

- `src/planner.py`
- `src/planned_main.py`
- `src/autonomous_sdlc.py`

These are the highest-value prompt families for v1 because they directly affect code generation, tool-call formatting, and workflow execution.

### 4.2 Deferred Scope

Agent system prompts in `src/agents/*.py` are **not** part of v1 promotion scope. The system architecture should be designed so those prompts can be onboarded later, but v1 planning, implementation, and acceptance criteria should focus only on:

- planner prompt templates in `src/planner.py`
- Builder and code-generation-adjacent prompts in `src/planned_main.py`
- workflow prompts in `src/autonomous_sdlc.py`

## 5. Recommended Approach

### 5.1 Chosen Strategy

Use a dedicated **offline optimizer pipeline** that operates outside normal task execution. The optimizer analyzes prompt-bearing modules, generates candidate prompt variants, runs an evaluation harness, and rewrites source only when a candidate beats the current prompt.

### 5.2 Why This Approach

This approach is preferred over self-optimizing live agents because:

- it isolates prompt mutation from live workflow execution
- it makes regressions easier to detect
- it matches the repo’s existing staged/eval mindset
- it allows the optimizer to evolve later into a prompt registry/template system without requiring that refactor up front

## 6. Architecture

### 6.1 Core Components

The system should be structured around the following modules:

- `src/services/prompt_targets.py`
  - discovers and models prompt-bearing code sites
  - records file path, symbol/context, prompt type, and rewrite eligibility

- `src/services/prompt_optimizer.py`
  - orchestrates end-to-end optimization runs
  - coordinates discovery, candidate generation, evaluation, and promotion

- `src/services/prompt_evaluator.py`
  - runs baseline and candidate prompts against the same scenario set
  - produces structured scores and hard-gate results

- `src/services/prompt_history.py`
  - stores prompt versions, run metadata, scores, decisions, and rollback history

- optional supporting fixtures under `tests/` and/or `tests/fixtures/`
  - hold deterministic scenarios and expected evaluation contracts

### 6.2 Prompt Target Model

Each prompt target should capture:

- source file
- owning symbol or prompt name
- prompt category (`system`, `planner`, `workflow`, `code_generation`)
- required variables/placeholders
- evaluator type
- hard-gate checks
- whether source rewrite is allowed

This turns prompt optimization from “search and replace strings” into a typed workflow.

### 6.3 Optimizer Configuration

V1 should keep optimizer configuration in a single explicit location, for example `src/services/prompt_targets.py` or a small adjacent config module. That configuration should define:

- registered prompt targets
- evaluator type per target
- promotion threshold per target
- hard-gate requirements per target
- rewrite eligibility

Planners should treat this as one authoritative configuration surface rather than inventing multiple competing config stores.

## 7. Optimization Workflow

### 7.1 Discovery

The optimizer scans the approved Python files and extracts known prompt targets. Discovery should be whitelist-based rather than trying to mutate any string literal that looks prompt-like.

### 7.2 Candidate Generation

For each target prompt, the optimizer generates one or more prompt variants using prompt-engineering patterns appropriate to the target:

- stronger output constraints
- clearer role and scope framing
- better code-generation instructions
- more explicit verification guidance
- more reliable structured output instructions where relevant

Candidate generation should preserve required placeholders and variable references.

### 7.3 Evaluation

Each candidate must be evaluated against the current prompt using the same stable scenario set.

Example scenario types:

- Builder prompt -> generate a staged code artifact from a task specification
- planner prompt -> emit valid, parseable tool-call structures
- Orchestrator/Ideator prompt -> route or structure work correctly
- autonomous SDLC prompt -> produce decisive, parseable task output

### 7.4 Scoring

Scoring should combine hard gates and rubric scoring.

Hard gates:

- output must remain parseable where parsing is required
- prompt placeholders and required variables must remain valid
- prompt-generated code must satisfy required verification checks
- no required scenario may regress

Soft dimensions:

- correctness
- completeness
- consistency
- code-generation usefulness
- token or latency efficiency if tracked

### 7.5 Promotion

A candidate prompt is promoted only if:

- its overall score exceeds the baseline by a configurable threshold
- it passes all hard gates
- the rewritten source remains syntactically valid
- post-rewrite verification succeeds

If promoted, the system rewrites the prompt directly in source and records the result in history.

### 7.6 Rollback

If rewrite or post-rewrite verification fails, the system restores the prior prompt text and records the rollback with failure details.

### 7.7 Post-Rewrite Verification

For v1, post-rewrite verification must mean:

1. the edited Python file still parses successfully
2. the target prompt’s deterministic evaluation scenarios still pass using the rewritten source prompt
3. the prompt target remains discoverable and its placeholders/required variables remain valid

Full broad regression runs may be added later, but v1 promotion must at minimum pass this targeted verification set before the rewritten prompt is accepted.

## 8. Safety Rules

- Only registered prompt targets may be optimized
- Each target must declare the evaluator and promotion rules it uses
- Prompt mutation must never run implicitly during a normal production task
- Auto-promotion must require measurable improvement, not only qualitative preference
- Any malformed or non-comparable evaluation result must fail closed

## 9. Evaluation Strategy

The design should support both:

- deterministic local evaluation for stable regression checks
- optional richer judging for nuanced prompt quality

Recommended evaluation methods:

1. **Deterministic checks**
   - parseability
   - placeholder preservation
   - scenario contract validation

2. **Rubric-based scoring**
   - correctness
   - completeness
   - consistency
   - code usefulness

3. **LLM-as-judge where needed**
   - only for qualitative comparisons after deterministic gates pass
   - never as the only basis for promotion

## 10. Failure Modes

The system must explicitly handle:

- prompt extraction failure
- malformed candidate prompt
- evaluator parse failure
- incomparable baseline/candidate results
- failed source rewrite
- post-rewrite verification failure

In all of these cases, the baseline prompt remains authoritative and the failed attempt is logged.

## 11. Testing Strategy

The first implementation should emphasize deterministic tests around the optimizer pipeline itself.

### 11.1 Discovery Tests

Verify that prompt targets are discovered from the v1 prompt surfaces:

- `src/planner.py`
- `src/planned_main.py`
- `src/autonomous_sdlc.py`

### 11.2 Candidate Generation Tests

Verify that generated variants:

- preserve placeholders
- preserve required prompt roles or sections
- do not remove structured-output requirements when those are mandatory

### 11.3 Evaluation Harness Tests

Verify that:

- baseline and candidate prompts run against the same fixtures
- scores are structured and reproducible
- hard-gate failures block promotion

### 11.4 Promotion and Rollback Tests

Verify that:

- rewrite occurs only when threshold and hard gates pass
- equal-or-worse candidates are rejected
- failed post-rewrite verification triggers rollback

### 11.5 End-to-End Optimizer Test

Run one prompt target through:

1. discovery
2. candidate generation
3. evaluation
4. promotion or rejection

using mocked model behavior so the workflow remains deterministic.

## 12. Planning Handoff

This spec is ready for implementation planning as a single feature focused on prompt optimization infrastructure.

Planning should start with:

1. prompt target discovery and typing
2. deterministic evaluation harness for code-generation-critical prompts
3. promotion and rollback mechanics
4. extension to broader prompt families after the first path is stable

Known files and directories to carry into planning:

- `src/planner.py`
- `src/planned_main.py`
- `src/autonomous_sdlc.py`
- `src/services/`
- `tests/`

Agent system prompts in `src/agents/*.py` are explicitly deferred beyond v1 and should not be included in the first implementation plan except where planners need to preserve future extensibility.
