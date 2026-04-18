# GADK — Cognitive Foundry Swarm

Multi-agent SDLC system on Google ADK. Agents discover, plan, build, review, and govern work against a target repository (default: `project-chimera`) via GitHub.

Work items traverse an explicit phase ledger — **PLAN → ARCHITECT → IMPLEMENT → REVIEW → GOVERN → OPERATE** — under pluggable quality gates, with a REVIEW↔IMPLEMENT rework edge for bounded retry. An opt-in self-prompting loop synthesizes gap signals (coverage holes, blocked transitions, stale backlog) into new prompts.

## Agents

| Role | File | Phase |
|---|---|---|
| Orchestrator | `src/agents/orchestrator.py` | routing |
| Ideator | `src/agents/ideator.py` | PLAN |
| Architect | `src/agents/architect.py` | ARCHITECT |
| Builder | `src/agents/builder.py` | IMPLEMENT |
| Critic | `src/agents/critic.py` | REVIEW |
| Governor | `src/agents/governor.py` | GOVERN |
| Pulse | `src/agents/pulse.py` | OPERATE |
| FinOps | `src/agents/finops.py` | OPERATE |

Phase ownership is registered in `src/services/specialist_registry.py::DEFAULT_PHASE_OWNERS`.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"           # dev tooling (ruff, mypy, pip-audit, bandit, pre-commit)
pip install -e ".[memory]"        # (optional) sqlite-vec for vector retrieval
pre-commit install
```

Copy `.env.example` to `.env` and populate `OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `REPO_NAME`.

## Run

```bash
python3 -m src.main                              # start the swarm
python3 -m src.cli.swarm_cli status              # health check
python3 -m src.cli.swarm_cli tasks                # list tracked tasks
python3 -m src.cli.swarm_cli queue                # inspect prompt queue

# Phase-gate operations
python3 -m src.cli.swarm_cli phase status <id>            # current phase + history
python3 -m src.cli.swarm_cli phase advance <id> ARCHITECT # advance a work item
python3 -m src.cli.swarm_cli phase advance <id> REVIEW --force --reason "override"

# Self-prompt loop (opt-in, dry-run by default)
python3 -m src.cli.swarm_cli self-prompt --dry-run        # preview synthesized prompts
python3 -m src.cli.swarm_cli self-prompt --write          # append to prompt_queue.jsonl
```

## Configuration knobs

Settings resolve from env → `.env` → pydantic defaults. Non-obvious ones:

| Flag | Default | Effect |
|---|---|---|
| `GITHUB_MOCK_ALLOWED` | `false` | Allow the in-process `GitHubTool` mock when PyGithub is missing. **Production must keep this off.** |
| `TEST_MODE` | `false` | Uses `MockLiteLlm` and the GitHub mocks; skips the default embedder. |
| `PROJECT_ID` | `chimera` | Single-tenant scope placeholder; future multi-tenant work namespaces state by this. |
| `SELF_PROMPT_ENABLED` | `false` | Runs the background gap-signal synthesizer. Stop with `.swarm_shutdown` or `.swarm_self_prompt_off`. |
| `SELF_PROMPT_MAX_PER_HOUR` | `6` | Rate-limits self-prompt writes. |
| `SDLC_MCP_ENABLED` | `false` | Governor may forward gate verdicts to the external `chimera_*` / `sdlc_*` MCP server. Dormant by default. |
| `RETRIEVAL_BACKEND` | `keyword` | Set to `vector` / `sqlite-vec` to enable the sqlite-vec retrieval path. Falls back to keyword on any failure with a `retrieval.degraded` log. |
| `EMBED_MODEL` | `openrouter/openai/text-embedding-3-small` | Model used by `LiteLLMEmbedder`. |
| `EMBED_DAILY_TOKEN_CAP` | `200000` | Daily token budget enforced by `EmbedQuota`; over-cap calls raise `VectorBackendUnavailable`. |

## Test

```bash
pytest -q                                 # full suite
pytest tests/services -q                  # scoped
ruff check src tests                      # lint
ruff format --check src tests             # format check
mypy src                                  # typecheck (advisory)
pip-audit                                 # dependency CVE scan
coverage run -m pytest -q && coverage report --fail-under=35
```

CI (`.github/workflows/ci.yml`) runs lint + typecheck + tests (py3.11 + 3.12) + security scans on every PR.

## Architecture

See `docs/` and `.github/copilot-instructions.md`. Key entry points:

- `src/main.py` — swarm runtime, registers tools, processes `prompt_queue.jsonl`, runs the opt-in `_self_prompt_tick` coroutine.
- `src/autonomous_sdlc.py` — discover → plan → build → review → deliver loop.
- `src/services/workflow_graphs.py` — bounded review→rework cycles (LangGraph-optional).
- `src/services/sdlc_phase.py` — `Phase` enum, `WorkItem`, transition rules (`ALLOWED_TRANSITIONS`).
- `src/services/phase_controller.py` — `PhaseController.advance(item, target)` evaluates gates per transition and emits `phase.transition` events.
- `src/services/quality_gates.py` — `QualityGate` ABC plus `ContentGuardGate`, `LintGate`, `TypecheckGate`, `SecurityScanGate`, `TestCoverageGate`, `CriticReviewGate`.
- `src/services/phase_store.py` — `WorkItem` persistence on top of `StateManager` (used by the CLI `phase` subcommands).
- `src/services/self_prompt.py` — gap-driven self-prompting loop (coverage, event log, stale backlog).
- `src/services/vector_index.py` — `VectorIndex` protocol + `NullVectorIndex` + `SqliteVecBackend`.
- `src/services/embedder.py` — `LiteLLMEmbedder` with `build_default_embedder()` factory.
- `src/services/embed_quota.py` — `EmbedQuota` daily token tracker.
- `src/mcp/server.py` — FastMCP stdio surface (`swarm.status`, `repo.*`).
- `src/mcp/sdlc_client.py` — dormant adapter for the external SDLC MCP server.

Task state lives in `state.json`, events in `events.jsonl`, session data in `sessions.db`, pending prompts in `prompt_queue.jsonl`. `StateManager` performs atomic JSON writes (`tempfile` + `os.replace`) and advisory-locked appends (`fcntl.flock` on POSIX) so concurrent writers from the SDLC loop, self-prompt tick, and CLI commands don't corrupt state. The swarm shuts down cleanly when `.swarm_shutdown` appears in the working directory.

## Contributing

- Branch from `main`; open PRs early.
- All changes must pass `pre-commit run --all-files`, `ruff check src tests`, `ruff format --check src tests`, and `pytest -q` before merge.
- Add structured logs via `src/observability/logger.py`; do not use `print()` in library code (CLI commands are the one exception).
- New gates extend `QualityGate` in `src/services/quality_gates.py`.
- Work items flow through `PhaseController`; never mutate a `WorkItem.phase` directly.
- New agents follow the Architect/Governor pattern: pure tool functions at module scope, ADK wrapper behind a conditional import so the module stays testable without `google-adk`.
