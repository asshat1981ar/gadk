from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_fallback_models() -> list[str]:
    """Return the fallback model chain.

    All entries MUST be prefixed with `openrouter/` so LiteLLM routes
    through OpenRouter (which uses an OpenAI-compatible /chat/completions
    endpoint) rather than dispatching to provider-native handlers
    (which use incompatible endpoint paths like Anthropic's /v1/messages
    and cause 404s against the OpenRouter api_base).
    """
    tool_model = os.getenv("OPENROUTER_TOOL_MODEL", "openrouter/openai/gpt-4o")
    # Defensive: if the env var was set without the openrouter/ prefix, add it
    if not tool_model.startswith("openrouter/"):
        tool_model = f"openrouter/{tool_model}"
    return [
        tool_model,
        "openrouter/google/gemini-2.5-flash",
        "openrouter/google/gemini-2.0-flash-001",
        "openrouter/anthropic/claude-sonnet-4",
        "openrouter/elephant-alpha",
    ]


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str | None = None
    repo_name: str | None = None
    state_table_type: str = "json"
    autonomous_mode: bool = False
    test_mode: bool = False
    pydantic_ai_enabled: bool = False
    instructor_enabled: bool = False
    langgraph_enabled: bool = False
    llamaindex_enabled: bool = False
    token_quota_per_task: int = 50000

    openrouter_api_key: str | None = None
    openrouter_api_base: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openrouter/elephant-alpha"
    openrouter_tool_model: str = "openrouter/elephant-alpha"
    fallback_models: list[str] = Field(default_factory=_default_fallback_models)
    llm_timeout: int = 30
    llm_retries: int = 3

    # Phase 0 stabilization flags
    github_mock_allowed: bool = False  # require real PyGithub in prod
    workspace_root: str = "."  # sandbox root for filesystem/dispatcher

    # Phase 1 phase-gate framework
    project_id: str = "chimera"  # single-tenant scope (v1)

    # Phase 4 self-prompting loop
    self_prompt_enabled: bool = False
    self_prompt_max_per_hour: int = 6

    # Phase 5 external SDLC MCP integration
    sdlc_mcp_enabled: bool = False

    # Phase 3 retrieval memory
    retrieval_backend: str = "keyword"  # "keyword" | "vector"
    embed_model: str = "openrouter/openai/text-embedding-3-small"
    embed_daily_token_cap: int = 200_000

    # Stabilization round 2: centralized runtime tunables.
    swarm_loop_poll_sec: float = 2.0
    self_prompt_tick_interval_sec: float = 60.0
    gate_subprocess_timeout_sec: float = 120.0
    github_dedup_issue_scan_limit: int = 100


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached typed settings for runtime consumers."""
    return Settings()


_settings = get_settings()


class Config:
    """Backward-compatible uppercase settings shim for existing imports."""

    GITHUB_TOKEN = _settings.github_token
    REPO_NAME = _settings.repo_name
    STATE_TABLE_TYPE = _settings.state_table_type
    AUTONOMOUS_MODE = _settings.autonomous_mode
    TEST_MODE = _settings.test_mode
    PYDANTIC_AI_ENABLED = _settings.pydantic_ai_enabled
    INSTRUCTOR_ENABLED = _settings.instructor_enabled
    LANGGRAPH_ENABLED = _settings.langgraph_enabled
    LLAMAINDEX_ENABLED = _settings.llamaindex_enabled
    TOKEN_QUOTA_PER_TASK = _settings.token_quota_per_task
    OPENROUTER_API_KEY = _settings.openrouter_api_key
    OPENROUTER_API_BASE = _settings.openrouter_api_base
    OPENROUTER_MODEL = _settings.openrouter_model
    OPENROUTER_TOOL_MODEL = _settings.openrouter_tool_model
    FALLBACK_MODELS = _settings.fallback_models
    LLM_TIMEOUT = _settings.llm_timeout
    LLM_RETRIES = _settings.llm_retries
    GITHUB_MOCK_ALLOWED = _settings.github_mock_allowed
    WORKSPACE_ROOT = _settings.workspace_root
    PROJECT_ID = _settings.project_id
    SELF_PROMPT_ENABLED = _settings.self_prompt_enabled
    SELF_PROMPT_MAX_PER_HOUR = _settings.self_prompt_max_per_hour
    SDLC_MCP_ENABLED = _settings.sdlc_mcp_enabled
    RETRIEVAL_BACKEND = _settings.retrieval_backend
    EMBED_MODEL = _settings.embed_model
    EMBED_DAILY_TOKEN_CAP = _settings.embed_daily_token_cap
    SWARM_LOOP_POLL_SEC = _settings.swarm_loop_poll_sec
    SELF_PROMPT_TICK_INTERVAL_SEC = _settings.self_prompt_tick_interval_sec
    GATE_SUBPROCESS_TIMEOUT_SEC = _settings.gate_subprocess_timeout_sec
    GITHUB_DEDUP_ISSUE_SCAN_LIMIT = _settings.github_dedup_issue_scan_limit


__all__ = ["Config", "Settings", "get_settings"]
