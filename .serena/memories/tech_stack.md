# GADK Tech Stack

## Core Framework
- **Google ADK** — Agent runtime and orchestration
- **LiteLLM** — Unified LLM interface via OpenRouter
- **Pydantic** — Schema validation and settings management
- **Pydantic Settings** — Environment-based configuration

## Language & Runtime
- **Python 3.11+** — Primary language
- **Async/await** — Concurrency model throughout

## AI/LLM Integration
- **OpenRouter** — LLM routing ( Elephant Alpha, GPT-4o, Gemini, Claude)
- **LiteLLMEmbedder** — Text embeddings for retrieval
- Optional integrations:
  - **PydanticAI** — Typed agent decisions (planned)
  - **Instructor** — Schema enforcement
  - **LangGraph/LangChain** — Workflow graphs for retry/branch logic
  - **LlamaIndex** — RAG and memory (optional)

## Data Persistence
- **state.json** — Task state (atomic JSON writes)
- **events.jsonl** — Event log (advisory-locked appends)
- **sessions.db** — SQLite session data
- **prompt_queue.jsonl** — Pending prompts

## Development Tools
- **ruff** — Linting and formatting (v0.5.7 pinned)
- **mypy** — Type checking
- **pytest** — Testing with asyncio support
- **pre-commit** — Git hooks
- **pip-audit** — Security scanning
- **bandit** — Security linting
- **coverage** — Test coverage

## External Integrations
- **GitHub API** — PRs, issues, code review
- **Smithery** — Tool marketplace
- **MCP (Model Context Protocol)** — SDLC server integration (optional)