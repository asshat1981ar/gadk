# Technical Debt Register
## Cognitive Foundry — Identified Debt and Remediation Plan

**Legend:** 🔴 Blocking · 🟠 High · 🟡 Medium · 🟢 Low

---

## Category 1: Agent Wiring

### TD-001 🔴 Architect and Governor agents not wired into Orchestrator
**File:** `src/agents/orchestrator.py`  
**Symptom:** `orchestrator_agent.sub_agents` includes `[ideator, builder, critic, pulse, finops]` only. Architect and Governor are fully implemented but never reachable from the Orchestrator.  
**Impact:** PLAN→ARCHITECT and REVIEW→GOVERN transitions can never be delegated autonomously.  
**Fix:** Add `architect_agent` and `governor_agent` to `orchestrator_agent.sub_agents`; update the Orchestrator instruction to describe their delegation criteria.  
**Status:** ✅ Fixed in this branch.

### TD-002 🟠 Builder creates PRs against branches that may not exist
**File:** `src/agents/builder.py` — `build_tool()`  
**Symptom:** `create_pull_request(head=f"feature/{name}")` is called without verifying or creating the branch first. `GitHubTool.create_pull_request` does create the branch if absent, but `build_tool` writes files only to the local filesystem — there is no commit step.  
**Impact:** PRs opened by Builder have no commits on the feature branch; they are empty diffs.  
**Fix:** Builder should commit staged files via `GitHubTool.commit_files_to_branch` before opening a PR, or the SDLC loop should own the commit/PR step after Builder finishes.

### TD-003 🟡 Critic `evaluate()` only handles Python files
**File:** `src/agents/critic.py`  
**Symptom:** `evaluate()` checks `staged_path.endswith(".py")` and fails for any other language.  
**Impact:** Builder stages non-Python files (Kotlin, TypeScript) → Critic blocks them as "FAIL: Not a python file."  
**Fix:** Dispatch language-specific sandbox execution or use static analysis (ruff, ktlint) in place of exec-based evaluation for non-Python artefacts.

---

## Category 2: Python Idiom Issues

### TD-004 🟠 `asyncio.get_event_loop()` deprecated in ideator.py
**File:** `src/agents/ideator.py:68`  
**Symptom:** `asyncio.get_event_loop().time()` is used to generate task IDs. `get_event_loop()` is deprecated in Python 3.10+ and raises a `DeprecationWarning` in Python 3.12.  
**Fix:** Use `asyncio.get_running_loop().time()` inside an async context.  
**Status:** ✅ Fixed in this branch.

### TD-005 🟡 `datetime.timezone.utc` instead of `UTC` in ideator.py
**File:** `src/agents/ideator.py:79`  
**Symptom:** `datetime.now(timezone.utc)` is used while the rest of the codebase uses `from datetime import UTC, datetime` and `datetime.now(UTC)`.  
**Fix:** Align with the repo-wide convention (UTC import from datetime stdlib module).  
**Status:** ✅ Fixed in this branch.

### TD-006 🟡 Config uppercase shim pattern hides settings changes
**File:** `src/config.py:128–167`  
**Symptom:** `Config` is a plain class populated from `_settings = get_settings()` at module-import time. Any `os.environ` mutation after import (common in tests) is invisible to `Config.*` attributes.  
**Impact:** Tests that patch environment variables after import see stale config values.  
**Fix (medium-term):** Replace `Config.FOO` call-sites with `get_settings().foo` or use a property-based shim. Short-term mitigation: reload the `lru_cache` in test fixtures.

---

## Category 3: File System and Repo Hygiene

### TD-007 🟠 Runtime artefact files committed to repository
**Files:** `state.json`, `auton_loop.log`, `swarm_run.log`, `swarm_run2.log`, `rpg_sdlc.log`  
**Symptom:** These files belong to the swarm runtime, not source control. `state.json` contains live task state; log files accumulate indefinitely and create noisy diffs.  
**Fix:** Add all of them to `.gitignore`. `state.json` should be created on first run by `StateManager`.  
**Status:** ✅ Fixed in this branch.

### TD-008 🟡 Stale migration shell scripts at repository root
**Files:** `migrate-pass-1a.sh`, `migrate-pass-1a-v2.sh`  
**Symptom:** Large shell scripts (12–13 KB each) describing a past migration that was never completed or rolled back. They reference file paths that no longer exist and confuse new contributors.  
**Fix:** Move to `docs/migrations/` for historical reference or remove entirely.  
**Status:** ✅ Moved in this branch.

### TD-009 🟡 `logs/` directory contains no `.gitkeep`
**File:** `logs/` directory  
**Symptom:** Empty `logs/` dir is tracked, but log files inside it may not be ignored consistently.  
**Fix:** Add `logs/*.log` to `.gitignore` and add a `.gitkeep` so the directory is preserved.

### TD-010 🟢 `src/review.md` is a stale agent-generated note
**File:** `src/review.md`  
**Symptom:** A Critic-generated review note committed to `src/` rather than `docs/` or discarded.  
**Fix:** Move to `docs/` or remove.

---

## Category 4: Architecture / Design Debt

### TD-011 🔴 Hard-coded `project-chimera` target throughout the codebase
**Files:** `src/main.py:221`, `src/autonomous_sdlc.py:64`, `src/config.py:82` (PROJECT_ID)  
**Symptom:** The system is wired to a single target repository. `PROJECT_ID = "chimera"` is the only namespacing in state/events. `_build_autonomous_prompt("project-chimera")` is a literal string.  
**Impact:** The platform cannot manage multiple projects simultaneously. Every run targets chimera.  
**Fix:** Promote `project_id` and `repo_name` to required, per-session configuration. Namespace all state/event files by `project_id`.

### TD-012 🔴 No conversation context between sessions
**Symptom:** Each swarm run starts a new ADK session with no memory of prior interactions. Users cannot continue a conversation or refer to previous decisions.  
**Impact:** Every run re-discovers the same issues; no incremental improvement within a project.  
**Fix:** Persist `WorkItem` history and ADR notes in the retrieval index; prime each new session with relevant prior context via `retrieve_planning_context`.

### TD-013 🟠 Planner tool registry is a hardcoded set
**File:** `src/planner.py:68–76` (`_KNOWN_TOOLS`)  
**Symptom:** The set of tool names the planner will accept is static. When new tools are registered via `register_tool()`, the planner never learns about them.  
**Fix:** Derive `_KNOWN_TOOLS` dynamically from `_TOOL_REGISTRY` at planner invocation time instead of a module-level constant.

### TD-014 🟠 `autonomous_sdlc.py` is monolithic (28 KB)
**File:** `src/autonomous_sdlc.py`  
**Symptom:** The file mixes discovery, planning, build, review, delivery, and retry-loop logic in a single module. It is difficult to test individual stages in isolation.  
**Fix:** Extract each SDLC stage into a dedicated module under `src/services/sdlc_stages/` and have `autonomous_sdlc.py` orchestrate them.

### TD-015 🟡 State files stored in CWD (no configurable data directory)
**Symptom:** `state.json`, `events.jsonl`, `sessions.db`, `prompt_queue.jsonl` are all created in the process working directory. Running two projects from the same directory would collide.  
**Fix:** Introduce a `DATA_DIR` config setting (default `./data`) and write all runtime files there, namespaced by `project_id`.

### TD-016 🟡 Missing tests for many critical modules
**Modules lacking test coverage:** `src/agents/builder.py`, `src/agents/critic.py`, `src/agents/pulse.py`, `src/agents/finops.py`, `src/planner.py` (partial), `src/autonomous_sdlc.py`, `src/services/self_prompt.py` (partial)  
**Fix:** Add unit tests with `MockLiteLlm` and stub GitHub tool. Raise `fail_under` in `pyproject.toml` from 0 to 35 (Phase 0) → 65 (Phase 5).

### TD-017 🟡 `requirements.txt` includes test/dev dependencies
**File:** `requirements.txt`  
**Symptom:** `pytest`, `pytest-asyncio` are listed as runtime dependencies in `requirements.txt` alongside true runtime deps. Dev deps should be in `pyproject.toml [project.optional-dependencies.dev]` only.  
**Fix:** Remove test dependencies from `requirements.txt`; install via `pip install -e ".[dev]"`.

### TD-018 🟢 No chat or web interface
**Symptom:** The only user interaction path is the `prompt_queue.jsonl` file and the interactive CLI REPL. There is no web or IDE-integrated chat surface.  
**Impact:** Users cannot easily interact with the swarm in real-time.  
**Fix:** Phase 1–2 deliverable: FastAPI backend + React/Next.js chat UI (see PRD).

---

## Remediation Priority Queue

| ID | Priority | Effort | Phase |
|----|----------|--------|-------|
| TD-001 | 🔴 Blocking | XS | 0 (now) |
| TD-004 | 🟠 High | XS | 0 (now) |
| TD-005 | 🟡 Medium | XS | 0 (now) |
| TD-007 | 🟠 High | XS | 0 (now) |
| TD-008 | 🟡 Medium | XS | 0 (now) |
| TD-011 | 🔴 Blocking | L | 1 |
| TD-012 | 🔴 Blocking | L | 1 |
| TD-013 | 🟠 High | S | 1 |
| TD-014 | 🟠 High | M | 1 |
| TD-002 | 🟠 High | M | 1 |
| TD-003 | 🟠 High | M | 1 |
| TD-015 | 🟡 Medium | M | 2 |
| TD-016 | 🟡 Medium | L | 2 |
| TD-006 | 🟡 Medium | M | 2 |
| TD-017 | 🟡 Medium | XS | 1 |
| TD-018 | 🟢 Low | XL | 2–3 |
| TD-009 | 🟢 Low | XS | 0 (now) |
| TD-010 | 🟢 Low | XS | 0 (now) |
