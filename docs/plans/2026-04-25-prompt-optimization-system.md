# Prompt Optimization System Implementation Plan

> **Date:** 2026-04-25 | **Status:** Approved for autonomous execution | **Target branch:** main

---

## Goal

Build the v1 **Prompt Optimization System** for GADK that discovers prompt-bearing code sites, evaluates prompt variants against deterministic scenarios, and rewrites source only when a candidate beats the baseline and passes post-rewrite verification.

---

## Architecture

**Service layer under `src/services/`:**
- `prompt_targets.py` — prompt target discovery and source replacement helpers
- `prompt_history.py` — prompt version history and promotion log persistence  
- `prompt_evaluator.py` — deterministic baseline/candidate evaluation and scoring
- `prompt_optimizer.py` — end-to-end optimization orchestration, promotion gate, rollback

**Entrypoint:**
- `src/prompt_optimization.py` — runnable batch or single-target optimizer

---

## Planning Handoff

- **Approved spec path:** `docs/superpowers/specs/2026-04-17-prompt-optimization-system-design.md`
- **In scope:** `src/planner.py`, `src/planned_main.py`, `src/services/prompt_*.py`, new entrypoint, tests
- **Out of scope:** agent system prompts in `src/agents/*.py` (deferred to v2), runtime self-editing during live tasks
- **Explicit constraints:** auto-rewrite prompt text only after evaluation passes; use deterministic harnesses first; keep prompt targets whitelist-based; rollback on failed post-rewrite verification

---

## Task List

### Task 0: Harden optional dependency imports

**Objective:** Fix test collection errors caused by missing optional packages (`llama-index`, `json_repair`, `pytest-asyncio`) by adding graceful degrade guards.

**Files:**
- Modify: `src/services/retrieval_context.py` (guard llama-index import)
- Modify: `src/services/structured_output.py` (guard json_repair import)
- Modify: `pyproject.toml` (add pytest-asyncio + json-repair + llama-index optional deps)

**TDD Cycle:**
- Step 1: Run full suite, confirm 12+ errors
- Step 2: Add import guards
- Step 3: Run suite again, verify collection passes
- Step 4: Commit

---

### Task 1: Prompt Target Discovery (`src/services/prompt_targets.py`)

**Objective:** Discover prompt-bearing code sites in approved Python modules and provide safe source replacement.

**Files:**
- Create: `src/services/prompt_targets.py`
- Test: `tests/services/test_prompt_targets.py`

*TDD Cycle (full — failing test → implementation → passing test → commit)*

---

### Task 2: Prompt History (`src/services/prompt_history.py`)

**Objective:** Track prompt versions, scores, and promotion decisions with deterministic rollback.

**Files:**
- Create: `src/services/prompt_history.py`
- Test: `tests/services/test_prompt_history.py`

*TDD Cycle (full)*

---

### Task 3: Prompt Evaluator (`src/services/prompt_evaluator.py`)

**Objective:** Run deterministic evaluation harnesses (mock scenarios, regex checks, expected tool calls) and score baseline vs candidate prompts.

**Files:**
- Create: `src/services/prompt_evaluator.py`
- Test: `tests/services/test_prompt_evaluator.py`

*TDD Cycle (full)*

---

### Task 4: Prompt Optimizer (`src/services/prompt_optimizer.py`)

**Objective:** End-to-end orchestration: discover → evaluate → promote (with rollback if post-rewrite verification fails).

**Files:**
- Create: `src/services/prompt_optimizer.py`
- Test: `tests/services/test_prompt_optimizer.py`

*TDD Cycle (full)*

---

### Task 5: Entrypoint (`src/prompt_optimization.py`)

**Objective:** Runnable CLI entrypoint for batch optimization outside normal swarm execution.

**Files:**
- Create: `src/prompt_optimization.py`
- Test: `tests/test_prompt_optimization_e2e.py`

*TDD Cycle (full)*

---

### Task 6: Final Integration & Quality Gate

**Objective:** Run full test suite, lint, format, and commit.

**Commands:**
```bash
ruff check src tests
ruff format --check src tests
pytest -q
```

---

## Success Criteria

- [ ] `pytest tests/services/test_prompt_targets.py` → PASS
- [ ] `pytest tests/services/test_prompt_history.py` → PASS
- [ ] `pytest tests/services/test_prompt_evaluator.py` → PASS
- [ ] `pytest tests/services/test_prompt_optimizer.py` → PASS
- [ ] `pytest tests/test_prompt_optimization_e2e.py` → PASS
- [ ] `ruff check src/services/prompt_*.py` → PASS
- [ ] `ruff format --check src/services/prompt_*.py` → PASS

---

## Execution Handoff

> Plan complete and saved. Ready to execute using subagent-driven-development task-by-task with full TDD cycle. Type **'continue'** to proceed from Task 0.
