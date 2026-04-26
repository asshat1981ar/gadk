import importlib

import pytest

import src.config as config_module


def _reload_config_module(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    return importlib.reload(config_module)


def test_settings_reads_defaults_without_env(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    monkeypatch.delenv("LLM_TOOL_MODEL", raising=False)

    settings = config_module.Settings(_env_file=None)

    assert settings.ollama_model == "minimax-m2.7:cloud"
    assert settings.llm_timeout == 30
    assert settings.fallback_models[0] == "ollama/minimax-m2.7:cloud"
    assert all(model.startswith("ollama/") for model in settings.fallback_models)


def test_settings_parses_boolean_flags(monkeypatch):
    monkeypatch.setenv("AUTONOMOUS_MODE", "true")
    monkeypatch.setenv("TEST_MODE", "false")

    settings = config_module.Settings(_env_file=None)

    assert settings.autonomous_mode is True
    assert settings.test_mode is False


def test_get_settings_returns_cached_settings(monkeypatch, tmp_path):
    module = _reload_config_module(monkeypatch, tmp_path)
    monkeypatch.setenv("LLM_MODEL", "ollama/test-model")
    module.get_settings.cache_clear()

    first = module.get_settings()
    second = module.get_settings()

    assert first is second
    assert first.llm_model == "ollama/test-model"


def test_config_preserves_legacy_uppercase_attributes(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("LLM_MODEL", "ollama/compat-model")
    monkeypatch.setenv("LLM_TOOL_MODEL", "ollama/tool-compat-model")

    module = _reload_config_module(monkeypatch, tmp_path)

    assert module.Config.TEST_MODE is True
    assert module.Config.LLM_MODEL == "ollama/compat-model"
    assert module.Config.LLM_TOOL_MODEL == "ollama/tool-compat-model"
    assert module.Config.FALLBACK_MODELS[0] == "ollama/compat-model"
    # Legacy OpenRouter shim still works
    assert module.Config.OPENROUTER_MODEL == "ollama/compat-model"
    assert module.Config.OPENROUTER_TOOL_MODEL == "ollama/tool-compat-model"


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------


def test_retrieval_backend_invalid_raises():
    """`retrieval_backend` must be one of the four accepted literals."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        config_module.Settings(_env_file=None, retrieval_backend="typo")  # type: ignore[call-arg]


def test_retrieval_backend_valid_values():
    """All four valid `retrieval_backend` values must be accepted."""
    for value in ("keyword", "vector", "sqlite-vec", "sqlitevec"):
        s = config_module.Settings(_env_file=None, retrieval_backend=value)  # type: ignore[call-arg]
        assert s.retrieval_backend == value


def test_embed_model_invalid_raises():
    """`embed_model` values not prefixed with `ollama/` must be rejected."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        config_module.Settings(_env_file=None, embed_model="not-an-ollama-model")  # type: ignore[call-arg]


def test_embed_model_valid_accepts_ollama_prefix():
    """A model string starting with `ollama/` must be accepted."""
    s = config_module.Settings(
        _env_file=None,
        embed_model="ollama/ministral-3:cloud",  # type: ignore[call-arg]
    )
    assert s.embed_model == "ollama/ministral-3:cloud"


def test_llm_api_base_invalid_raises():
    """`llm_api_base` must be a valid HTTP/HTTPS URL."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        config_module.Settings(_env_file=None, llm_api_base="garbage")  # type: ignore[call-arg]


def test_llm_api_base_valid_url():
    """A valid HTTPS URL must be accepted for `llm_api_base`."""
    s = config_module.Settings(
        _env_file=None,
        llm_api_base="https://ollama.com",  # type: ignore[call-arg]
    )
    assert s.llm_api_base == "https://ollama.com"


def test_ollama_api_base_valid_url():
    """A valid HTTPS URL must be accepted for `ollama_api_base`."""
    s = config_module.Settings(
        _env_file=None,
        ollama_api_base="https://ollama.com",  # type: ignore[call-arg]
    )
    assert s.ollama_api_base == "https://ollama.com"


def test_github_tool_late_mock_flag(monkeypatch):
    """GitHubTool() honours GITHUB_MOCK_ALLOWED even when it was set after module import."""
    import src.tools.github_tool as gth

    monkeypatch.setattr(gth, "_PYGITHUB_AVAILABLE", False)
    monkeypatch.setenv("GITHUB_MOCK_ALLOWED", "true")
    config_module.get_settings.cache_clear()

    try:
        tool = gth.GitHubTool()
        assert tool.gh is not None
    finally:
        config_module.get_settings.cache_clear()
