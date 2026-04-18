# GADK — Cognitive Foundry Swarm

Multi-agent SDLC system on Google ADK. Agents discover, plan, build, review, and govern work against a target repository (default: `project-chimera`) via GitHub.

## Agents

| Role | File | Phase |
|---|---|---|
| Orchestrator | `src/agents/orchestrator.py` | routing |
| Ideator | `src/agents/ideator.py` | PLAN |
| Architect | `src/agents/architect.py` *(planned)* | ARCHITECT |
| Builder | `src/agents/builder.py` | IMPLEMENT |
| Critic | `src/agents/critic.py` | REVIEW |
| Governor | `src/agents/governor.py` *(planned)* | GOVERN |
| Pulse | `src/agents/pulse.py` | OPERATE |
| FinOps | `src/agents/finops.py` | OPERATE |

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"         # dev tooling (ruff, mypy, pip-audit, bandit, pre-commit)
pre-commit install
```

Copy `.env.example` to `.env` and populate `OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `REPO_NAME`.

## Run

```bash
python3 -m src.main                       # start the swarm
python3 -m src.cli.swarm_cli status       # health check
python3 -m src.cli.swarm_cli tasks        # list tracked tasks
python3 -m src.cli.swarm_cli queue        # inspect prompt queue
```

## Test

```bash
pytest -q                                 # full suite
pytest tests/services -q                  # scoped
ruff check src tests                      # lint
mypy src                                  # typecheck
pip-audit                                 # dependency CVE scan
```

## Architecture

See `docs/` and `.github/copilot-instructions.md`. Key entry points:

- `src/main.py` — swarm runtime, registers tools, processes `prompt_queue.jsonl`
- `src/autonomous_sdlc.py` — discover → plan → build → review → deliver loop
- `src/services/workflow_graphs.py` — bounded review→rework cycles (LangGraph-optional)
- `src/services/phase_controller.py` — SDLC phase-gate orchestration *(Phase 1)*
- `src/services/quality_gates.py` — gate abstractions *(Phase 1)*
- `src/services/self_prompt.py` — gap-driven self-prompting loop *(Phase 4)*
- `src/mcp/server.py` — FastMCP stdio surface (`swarm.status`, `repo.*`)

Task state lives in `state.json`, events in `events.jsonl`, session data in `sessions.db`, pending prompts in `prompt_queue.jsonl`. The swarm shuts down cleanly when `.swarm_shutdown` appears in the working directory.

## Contributing

- Branch from `main`; open PRs early.
- All changes must pass `pre-commit run --all-files` and `pytest -q` before merge.
- Add structured logs via `src/observability/logger.py`; do not use `print()` in library code.
- New gates extend `QualityGate` in `src/services/quality_gates.py`; new agent phases go through `PhaseController`.
