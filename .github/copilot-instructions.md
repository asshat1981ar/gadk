# Copilot instructions for `gadk`

## Commands

- Install Python dependencies: `python3 -m pip install -r requirements.txt`
- Run the swarm CLI status command: `python3 -m src.cli.swarm_cli status`
- Start the main swarm entrypoint: `python3 -m src.main`
- Run the Python test suite under `tests/`: `python3 -m pytest tests -q`
- Run a single test file: `python3 -m pytest tests/cli/test_dashboard.py -q`
- Run a single test case: `python3 -m pytest tests/test_dispatcher.py::test_batch_execute_success -q`

Use targeted `pytest` paths by default. A bare `pytest` also collects `test_llm.py` and `src/test_cicd.py` from the repo root and `src/`, so it exercises more than the maintained `tests/` tree.

`src.main` and the ADK-backed agent tests expect the environment variables shown in `.env.example`, especially `OPENROUTER_API_KEY`; GitHub-backed flows also depend on `GITHUB_TOKEN` and `REPO_NAME`.

## High-level architecture

This repo is primarily a Python "Cognitive Foundry" swarm built on Google ADK, with a separate Kotlin/Gradle game subtree living under the same top-level `src/` directory. Treat `src/` as mixed-purpose: Python runtime modules sit directly under `src/*.py`, while the game code lives under `src/main/java/com/chimera/rpg/...`.

The Python runtime starts in `src/main.py`. That module loads env config, registers tool functions, creates the ADK `Runner`, wraps it with `ObservabilityCallback`, and processes queued prompts. The queue/control plane is file-based: `src/cli/swarm_ctl.py` manages `.swarm_shutdown`, `prompt_queue.jsonl`, and `swarm.pid`; `src/state.py` persists task state to `state.json` and appends audit events to `events.jsonl`; `src/services/session_store.py` wraps ADK's SQLite session service for `sessions.db`; and `src/observability/` provides structured logging plus persisted metrics in `metrics.jsonl`.

The agent graph is assembled in `src/agents/orchestrator.py`. The Orchestrator is the hub and owns five sub-agents: Ideator, Builder, Critic, Pulse, and FinOps. Shared tool fan-out happens through `src/tools/dispatcher.py`, whose `batch_execute()` applies a global concurrency semaphore (`MAX_CONCURRENCY = 10`) and is the expected path for independent parallel tool work.

## Key conventions

- Prefer module execution (`python3 -m src...`) over running files directly. The CLI modules are written around module-style imports and, in a few places, patch `sys.path` to support that workflow.
- `Config.TEST_MODE` is a real code path, not just a flag for pytest. Agent modules switch from Google ADK LiteLlm to `src.testing.mock_llm.MockLiteLlm` when it is enabled.
- Repo-root artifacts are part of the normal runtime contract: `.swarm_shutdown`, `prompt_queue.jsonl`, `swarm.pid`, `state.json`, `events.jsonl`, `metrics.jsonl`, `sessions.db`, and `.swarm_history`.
- Preserve the existing persistence/observability helpers when changing runtime behavior: use `StateManager`, `swarm_ctl`, `get_logger`, and the metrics registry instead of ad hoc file or logging code.
- `src/tools/filesystem.py` intentionally enforces guardrails. It blocks access to secrets-like files and only permits writes under `src`, `tests`, `docs`, and `staged_agents`.
- Generated build artifacts are staged under `src/staged_agents/`. The Builder writes there first, and the Critic reviews staged Python by executing it through the sandbox tool rather than importing it directly.
- Task status values are uppercase strings shared across state, dashboard rendering, and CLI reporting (`PENDING`, `PLANNED`, `COMPLETED`, `STALLED`, `FAILED`).
- When adding or debugging agent behavior, remember that the Orchestrator instructions explicitly prefer `batch_execute()` for independent reads/searches/tool calls rather than serial tool use.
