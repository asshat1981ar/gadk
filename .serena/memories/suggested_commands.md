# GADK Suggested Commands

## Development Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"
pip install -e ".[memory]"  # Optional: for sqlite-vec
pre-commit install
cp .env.example .env  # Edit with your keys
```

## Running the Swarm
```bash
python3 -m src.main                              # Start the swarm
python3 -m src.cli.swarm_cli status              # Health check
python3 -m src.cli.swarm_cli tasks               # List tracked tasks
python3 -m src.cli.swarm_cli queue               # Inspect prompt queue
```

## Phase Operations
```bash
python3 -m src.cli.swarm_cli phase status <id>            # Current phase + history
python3 -m src.cli.swarm_cli phase advance <id> ARCHITECT # Advance work item
python3 -m src.cli.swarm_cli phase advance <id> REVIEW --force --reason "override"
```

## Self-Prompt Loop
```bash
python3 -m src.cli.swarm_cli self-prompt --dry-run   # Preview prompts
python3 -m src.cli.swarm_cli self-prompt --write     # Append to queue
```

## Testing & Quality
```bash
pytest -q                                            # Full test suite
pytest tests/services -q                             # Scoped tests
ruff check src tests                                 # Lint
ruff format --check src tests                        # Format check
ruff format src tests                                # Auto-format
mypy src                                             # Type check
pip-audit                                            # Security scan
bandit -r src                                        # Security lint
coverage run -m pytest -q && coverage report         # Coverage
```

## Pre-commit
```bash
pre-commit run --all-files                           # Run all hooks
```

## Git Operations
```bash
git checkout -b feature/<name>                       # New branch
git add <files>                                      # Stage
git commit -m "type: description"                    # Commit (conventional commits)
```

## Shutdown
```bash
touch .swarm_shutdown                                # Graceful shutdown
```

## Environment Variables (in .env)
- `OPENROUTER_API_KEY` — Required for LLM calls
- `GITHUB_TOKEN` — Required for GitHub operations
- `REPO_NAME` — Target repository (default: project-chimera)
- `TEST_MODE=true` — Enable mocks for testing