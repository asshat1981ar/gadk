# GADK Code Style & Conventions

## Python Style
- **Line length**: 100 characters (configured in pyproject.toml)
- **Quotes**: Double quotes preferred
- **Indent**: 4 spaces
- **Target**: Python 3.11+

## Import Organization
- Use `from __future__ import annotations` for forward references
- Group imports: stdlib → third-party → local
- Local imports use `src.` prefix (e.g., `from src.config import Config`)

## Type Hints
- Required for all new code in Phase 1+ modules
- Strict typing enabled for: `sdlc_phase.py`, `quality_gates.py`, `phase_controller.py`
- Use `| None` instead of `Optional[]`
- Use built-in generics: `list[str]` instead of `List[str]`

## Docstrings
- Use Google-style docstrings
- Module-level docstrings explain the file's purpose
- Function docstrings describe args and returns

## Naming Conventions
- **Functions/variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`

## Agent Pattern
New agents follow the Architect/Governor pattern:
1. Pure tool functions at module scope (testable without ADK)
2. ADK agent wrapper behind conditional import
3. Config-gated imports for test mode (MockLiteLlm vs LiteLlm)

## Error Handling
- Use structured logging via `src.observability.logger.get_logger()`
- No `print()` in library code (CLI commands are exception)
- Custom exceptions inherit from appropriate built-ins

## Testing
- All modules must be testable without `google-adk` installed
- Use `Config.TEST_MODE` to swap real/mocked dependencies
- Tests use `MockLiteLlm` and GitHub mocks