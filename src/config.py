from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── Ollama Cloud Models (sorted by capability) ───────────────────────
# Primary: MiniMax M2.7 — agentic coding, complex reasoning, swarm orchestration
# Coding: GLM-5.1, Qwen3-Coder, Devstral-2, Kimi-K2.6, Kimi-K2.5
# Reasoning: DeepSeek-V4-Flash (MoE, 1M context), Gemma4, GLM-5
# Efficient: Nemotron-3-Nano (4B), Nemotron-3-Super (120B MoE)
# Edge: Ministral-3 (3B/8B/14B), RNJ-1 (8B)
OLLAMA_CLOUD_MODELS: list[str] = [
    "ollama/minimax-m2.7:cloud",
    "ollama/kimi-k2.6:cloud",
    "ollama/glm-5.1:cloud",
    "ollama/deepseek-v4-flash:cloud",
    "ollama/gemma4:cloud",
    "ollama/qwen3-coder-next:cloud",
    "ollama/devstral-2:cloud",
    "ollama/kimi-k2.5:cloud",
    "ollama/nemotron-3-super:cloud",
    "ollama/glm-5:cloud",
    "ollama/minimax-m2.5:cloud",
    "ollama/qwen3.5:cloud",
    "ollama/nemotron-3-nano:cloud",
    "ollama/ministral-3:cloud",
    "ollama/rnj-1:cloud",
    "ollama/gemini-3-flash:cloud",
    "ollama/glm-4.7:cloud",
    "ollama/devstral-small-2:cloud",
    "ollama/cogito-2.1:cloud",
    "ollama/qwen3-next:cloud",
]


def _default_fallback_models() -> list[str]:
    """Return the Ollama-first fallback model chain."""
    primary = os.getenv("LLM_MODEL", "ollama/minimax-m2.7:cloud")
    if not primary.startswith("ollama/"):
        primary = f"ollama/{primary}"
    # Build chain: primary + remaining models excluding primary
    others = [m for m in OLLAMA_CLOUD_MODELS if m != primary]
    return [primary] + others


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
    dbos_enabled: bool = False
    dbos_database_url: str = "sqlite:///./dbos.db"
    token_quota_per_task: int = 50000

    langfuse_enabled: bool = False
    helicone_enabled: bool = False
    agentops_enabled: bool = False
    mlflow_enabled: bool = False
    sentry_dsn: str | None = None

    memori_enabled: bool = False
    memori_api_key: str | None = None
    memori_base_url: str = "https://api.memorilabs.ai"
    memori_entity_id: str = "gadk-swarm"
    memori_process_id: str | None = None

    # ── Primary LLM (Ollama Cloud) ──────────────────────────────────
    llm_model: str = "ollama/minimax-m2.7:cloud"
    llm_tool_model: str = "ollama/minimax-m2.7:cloud"
    llm_api_base: str = "https://ollama.com"
    llm_api_key: str | None = None
    llm_timeout: int = 30
    llm_retries: int = 3

    @field_validator("llm_api_base")
    @classmethod
    def _validate_llm_api_base(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(f"llm_api_base must be a valid HTTP or HTTPS URL, got: {v!r}")
        return v

    fallback_models: list[str] = Field(default_factory=_default_fallback_models)

    # ── Legacy OpenRouter shim (reads from env for migration) ─────────
    openrouter_api_key: str | None = None
    openrouter_api_base: str = "https://openrouter.ai/api/v1"

    # ── Ollama Cloud backend ──────────────────────────────────────────
    ollama_model: str = "minimax-m2.7:cloud"
    ollama_base_url: str = "https://ollama.com"
    ollama_api_key: str | None = None
    ollama_api_base: str = "https://ollama.com"  # backward compat shim (no validation)
    workspace_root: str = "."  # sandbox root for filesystem/dispatcher

    # Phase 0 stabilization flags
    github_mock_allowed: bool = False  # require real PyGithub in prod

    # Phase 1 phase-gate framework
    project_id: str = "chimera"

    # Multi-tenant support
    tenant_id: str = "default"
    multi_tenant_enabled: bool = False

    # Phase 4 self-prompting loop
    self_prompt_enabled: bool = False
    self_prompt_max_per_hour: int = 6

    # Phase 5 external SDLC MCP integration
    sdlc_mcp_enabled: bool = False

    # Phase 3 retrieval memory
    retrieval_backend: Literal["keyword", "vector", "sqlite-vec", "sqlitevec"] = "keyword"
    embed_model: str = "ollama/ministral-3:cloud"
    embed_daily_token_cap: int = 200_000

    @field_validator("embed_model")
    @classmethod
    def _validate_embed_model(cls, v: str) -> str:
        if not v.startswith("ollama/"):
            raise ValueError(f"embed_model must start with 'ollama/', got: {v!r}")
        return v

    # Stabilization round 2: centralized runtime tunables
    swarm_loop_poll_sec: float = Field(default=2.0, gt=0.0)
    self_prompt_tick_interval_sec: float = Field(default=60.0, gt=0.0)
    gate_subprocess_timeout_sec: float = Field(default=120.0, gt=0.0)
    github_dedup_issue_scan_limit: int = Field(default=100, gt=0)

    # Planner safety: cap max content bytes
    planner_max_content_bytes: int = Field(default=500_000, gt=0)


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
    DBOS_ENABLED = _settings.dbos_enabled
    DBOS_DATABASE_URL = _settings.dbos_database_url
    TOKEN_QUOTA_PER_TASK = _settings.token_quota_per_task
    LANGFUSE_ENABLED = _settings.langfuse_enabled
    HELICONE_ENABLED = _settings.helicone_enabled
    AGENTOPS_ENABLED = _settings.agentops_enabled
    MLFLOW_ENABLED = _settings.mlflow_enabled
    SENTRY_DSN = _settings.sentry_dsn
    MEMORI_ENABLED = _settings.memori_enabled
    MEMORI_API_KEY = _settings.memori_api_key
    MEMORI_BASE_URL = _settings.memori_base_url
    MEMORI_ENTITY_ID = _settings.memori_entity_id
    MEMORI_PROCESS_ID = _settings.memori_process_id

    # ── Primary LLM exports (Ollama Cloud) ────────────────────────────
    LLM_MODEL = _settings.llm_model
    LLM_TOOL_MODEL = _settings.llm_tool_model
    LLM_API_BASE = _settings.llm_api_base
    LLM_API_KEY = _settings.llm_api_key
    LLM_TIMEOUT = _settings.llm_timeout
    LLM_RETRIES = _settings.llm_retries
    FALLBACK_MODELS = _settings.fallback_models

    # ── Legacy OpenRouter shim (deprecated, use LLM_* instead) ──────
    OPENROUTER_API_KEY = _settings.openrouter_api_key or _settings.llm_api_key
    OPENROUTER_API_BASE = _settings.openrouter_api_base
    OPENROUTER_MODEL = _settings.llm_model
    OPENROUTER_TOOL_MODEL = _settings.llm_tool_model

    # ── Ollama-specific exports ─────────────────────────────────────
    OLLAMA_MODEL = _settings.ollama_model
    OLLAMA_BASE_URL = _settings.ollama_base_url
    OLLAMA_API_KEY = _settings.ollama_api_key or _settings.llm_api_key
    WORKSPACE_ROOT = _settings.workspace_root
    PROJECT_ID = _settings.project_id
    TENANT_ID = _settings.tenant_id
    MULTI_TENANT_ENABLED = _settings.multi_tenant_enabled
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
    PLANNER_MAX_CONTENT_BYTES = _settings.planner_max_content_bytes

    # Model capability mappings for intelligent routing
    # Maps capabilities to preferred models (in priority order)
    MODEL_CAPABILITY_MAP = {
        "code": [
            "ollama/minimax-m2.7:cloud",
            "ollama/glm-5.1:cloud",
            "ollama/qwen3-coder-next:cloud",
            "ollama/devstral-2:cloud",
            "ollama/kimi-k2.6:cloud",
        ],
        "review": [
            "ollama/kimi-k2.6:cloud",
            "ollama/kimi-k2.5:cloud",
            "ollama/glm-5.1:cloud",
            "ollama/minimax-m2.7:cloud",
            "ollama/deepseek-v4-flash:cloud",
        ],
        "analysis": [
            "ollama/glm-5:cloud",
            "ollama/kimi-k2.6:cloud",
            "ollama/deepseek-v4-flash:cloud",
            "ollama/gemma4:cloud",
            "ollama/minimax-m2.7:cloud",
        ],
        "creative": [
            "ollama/kimi-k2.5:cloud",
            "ollama/gemma4:cloud",
            "ollama/glm-5:cloud",
            "ollama/qwen3.5:cloud",
        ],
        "quick": [
            "ollama/ministral-3:cloud",
            "ollama/nemotron-3-nano:cloud",
            "ollama/rnj-1:cloud",
            "ollama/gemini-3-flash:cloud",
        ],
        "embed": [
            "ollama/ministral-3:cloud",
        ],
    }

    # Ollama Cloud model metadata for registry lookups
    MODEL_METADATA: dict[str, dict] = {
        "ollama/minimax-m2.7:cloud": {
            "size": "unknown",
            "tags": ["tools", "thinking", "cloud"],
            "strengths": ["agentic", "coding", "swarm_orchestration"],
        },
        "ollama/kimi-k2.6:cloud": {
            "size": "43B",
            "tags": ["vision", "tools", "thinking", "cloud"],
            "strengths": ["coding", "design", "agentic", "swarm"],
        },
        "ollama/glm-5.1:cloud": {
            "size": "unknown",
            "tags": ["tools", "thinking", "cloud"],
            "strengths": ["coding", "swe_bench", "agentic_engineering"],
        },
        "ollama/deepseek-v4-flash:cloud": {
            "size": "284B_MoE_13B_act",
            "tags": ["tools", "thinking", "cloud"],
            "strengths": ["reasoning", "1M_context", "efficient"],
        },
        "ollama/gemma4:cloud": {
            "size": "26B",
            "tags": ["vision", "tools", "thinking", "audio", "cloud"],
            "strengths": ["frontier", "multimodal", "reasoning"],
        },
        "ollama/qwen3-coder-next:cloud": {
            "size": "unknown",
            "tags": ["tools", "cloud"],
            "strengths": ["coding", "agentic_coding"],
        },
        "ollama/devstral-2:cloud": {
            "size": "123B",
            "tags": ["tools", "cloud"],
            "strengths": ["software_engineering", "codebase_exploration"],
        },
        "ollama/kimi-k2.5:cloud": {
            "size": "unknown",
            "tags": ["vision", "tools", "thinking", "cloud"],
            "strengths": ["multimodal", "agentic", "instant+thinking"],
        },
        "ollama/nemotron-3-super:cloud": {
            "size": "120B_MoE_12B_act",
            "tags": ["tools", "thinking", "cloud"],
            "strengths": ["multi_agent", "efficiency", "accuracy"],
        },
        "ollama/glm-5:cloud": {
            "size": "744B_MoE_40B_act",
            "tags": ["tools", "thinking", "cloud"],
            "strengths": ["reasoning", "agentic", "systems_engineering"],
        },
        "ollama/ministral-3:cloud": {
            "size": "3B/8B/14B",
            "tags": ["vision", "tools", "cloud"],
            "strengths": ["edge", "fast", "multimodal"],
        },
        "ollama/nemotron-3-nano:cloud": {
            "size": "4B/30B",
            "tags": ["tools", "thinking", "cloud"],
            "strengths": ["efficient", "agentic", "edge"],
        },
        "ollama/rnj-1:cloud": {
            "size": "8B",
            "tags": ["tools", "cloud"],
            "strengths": ["code", "stem", "dense"],
        },
        "ollama/gemini-3-flash:cloud": {
            "size": "unknown",
            "tags": ["vision", "tools", "thinking", "cloud"],
            "strengths": ["speed", "frontier_intelligence", "cheap"],
        },
        "ollama/glm-4.7:cloud": {
            "size": "unknown",
            "tags": ["tools", "thinking", "cloud"],
            "strengths": ["coding"],
        },
        "ollama/devstral-small-2:cloud": {
            "size": "24B",
            "tags": ["vision", "tools", "cloud"],
            "strengths": ["codebase_exploration", "tools", "editing"],
        },
        "ollama/cogito-2.1:cloud": {
            "size": "671B",
            "tags": ["cloud"],
            "strengths": ["instruction_tuned", "commercial"],
        },
        "ollama/qwen3-next:cloud": {
            "size": "80B",
            "tags": ["tools", "thinking", "cloud"],
            "strengths": ["parameter_efficient", "fast"],
        },
        "ollama/qwen3.5:cloud": {
            "size": "35B",
            "tags": ["vision", "tools", "thinking", "cloud"],
            "strengths": ["multimodal", "utility"],
        },
        "ollama/minimax-m2.5:cloud": {
            "size": "unknown",
            "tags": ["tools", "thinking", "cloud"],
            "strengths": ["productivity", "coding"],
        },
    }


__all__ = ["Config", "Settings", "get_settings", "OLLAMA_CLOUD_MODELS"]
