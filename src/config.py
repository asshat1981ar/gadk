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


__all__ = ["Config", "Settings", "get_settings"]
