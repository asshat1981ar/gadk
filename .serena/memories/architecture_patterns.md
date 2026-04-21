# GADK Architecture Patterns

## SDLC Phase System
Six-phase lifecycle with explicit transitions:
- **PLAN** → Ideator creates structured tasks
- **ARCHITECT** → Architect produces ADR-style architecture notes
- **IMPLEMENT** → Builder writes code
- **REVIEW** → Critic evaluates with bounded rework cycles
- **GOVERN** → Governor checks release readiness
- **OPERATE** → Pulse/FinOps monitor and optimize

Transition rules defined in `src/services/sdlc_phase.py::ALLOWED_TRANSITIONS`

## Quality Gates
Pluggable gate system in `src/services/quality_gates.py`:
- `ContentGuardGate` — Content quality checks
- `LintGate` — Code linting
- `TypecheckGate` — Type checking
- `SecurityScanGate` — Security scanning
- `TestCoverageGate` — Coverage requirements
- `CriticReviewGate` — Code review

Gates evaluated by `PhaseController.advance()` before phase transitions.

## Agent Communication
- **Orchestrator** — Central router, delegates to specialists
- **Tools** — Shared capabilities via `src/tools/dispatcher.py`
- **Events** — Structured logging to `events.jsonl`
- **State** — Centralized in `StateManager` with atomic writes

## Self-Prompting Loop
Opt-in background process (`src/services/self_prompt.py`):
- Monitors coverage holes
- Detects blocked transitions
- Identifies stale backlog
- Synthesizes new prompts automatically
- Rate-limited (default: 6/hour)

## Retrieval & Memory
- **Keyword retrieval** — Default, no dependencies
- **Vector retrieval** — Optional sqlite-vec backend
- **Embedder** — LiteLLMEmbedder with daily quota tracking
- **Context** — `retrieve_planning_context()` for local specs

## MCP Integration
- **MCP Server** — FastMCP stdio surface for external tools
- **SDLC Client** — External SDLC MCP server adapter (optional)

## File Organization
```
src/
  agents/           # ADK agent definitions
  services/         # Core business logic (phases, gates, retrieval)
  tools/            # Tool implementations (GitHub, filesystem, sandbox)
  observability/    # Logging, metrics, cost tracking
  cli/              # Command-line interface
  testing/          # Mocks and test utilities
  capabilities/     # Capability definitions
  mcp/              # MCP server/client
  extensions/       # Extension points
  utils/            # Shared utilities
```

## Key Entry Points
- `src/main.py` — Swarm runtime
- `src/autonomous_sdlc.py` — Discovery → plan → build → review → deliver
- `src/planner.py` — Planning and task decomposition
- `src/config.py` — Settings and configuration