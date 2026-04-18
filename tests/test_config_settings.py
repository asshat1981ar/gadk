import importlib

import pytest

import src.config as config_module


def _reload_config_module(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    return importlib.reload(config_module)


def test_settings_reads_defaults_without_env(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT", raising=False)
    monkeypatch.delenv("OPENROUTER_TOOL_MODEL", raising=False)

    settings = config_module.Settings(_env_file=None)

    assert settings.openrouter_model == "openrouter/elephant-alpha"
    assert settings.llm_timeout == 30
    # _default_fallback_models prefixes the chain with ``openrouter/`` so
    # LiteLLM routes through the OpenRouter-compatible endpoint rather
    # than the provider-native one (which would 404 on /chat/completions).
    assert settings.fallback_models[0] == "openrouter/openai/gpt-4o"
    # And every entry must carry the prefix — any unprefixed entry means
    # the defensive fix in `_default_fallback_models` regressed.
    assert all(model.startswith("openrouter/") for model in settings.fallback_models)


def test_settings_parses_boolean_flags(monkeypatch):
    monkeypatch.setenv("AUTONOMOUS_MODE", "true")
    monkeypatch.setenv("TEST_MODE", "false")

    settings = config_module.Settings(_env_file=None)

    assert settings.autonomous_mode is True
    assert settings.test_mode is False


def test_get_settings_returns_cached_settings(monkeypatch, tmp_path):
    module = _reload_config_module(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/test-model")
    module.get_settings.cache_clear()

    first = module.get_settings()
    second = module.get_settings()

    assert first is second
    assert first.openrouter_model == "openrouter/test-model"


def test_config_preserves_legacy_uppercase_attributes(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/compat-model")
    monkeypatch.setenv("OPENROUTER_TOOL_MODEL", "openrouter/tool-compat-model")

    module = _reload_config_module(monkeypatch, tmp_path)

    assert module.Config.TEST_MODE is True
    assert module.Config.OPENROUTER_MODEL == "openrouter/compat-model"
    assert module.Config.OPENROUTER_TOOL_MODEL == "openrouter/tool-compat-model"
    assert module.Config.FALLBACK_MODELS[0] == "openrouter/tool-compat-model"


# ---------------------------------------------------------------------------
# Validator tests (new validators added in fix(config) issue)
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
    """`embed_model` values not prefixed with `openrouter/` must be rejected."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        config_module.Settings(_env_file=None, embed_model="not-an-openrouter-model")  # type: ignore[call-arg]


def test_embed_model_valid_accepts_openrouter_prefix():
    """A model string starting with `openrouter/` must be accepted."""
    s = config_module.Settings(
        _env_file=None,
        embed_model="openrouter/openai/text-embedding-3-small",  # type: ignore[call-arg]
    )
    assert s.embed_model == "openrouter/openai/text-embedding-3-small"


def test_openrouter_api_base_invalid_raises():
    """`openrouter_api_base` must be a valid HTTP/HTTPS URL."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        config_module.Settings(_env_file=None, openrouter_api_base="garbage")  # type: ignore[call-arg]


def test_openrouter_api_base_valid_url():
    """A valid HTTPS URL must be accepted for `openrouter_api_base`."""
    s = config_module.Settings(
        _env_file=None,
        openrouter_api_base="https://openrouter.ai/api/v1",  # type: ignore[call-arg]
    )
    assert s.openrouter_api_base == "https://openrouter.ai/api/v1"


def test_github_tool_late_mock_flag(monkeypatch):
    """GitHubTool() honours GITHUB_MOCK_ALLOWED even when it was set after module import."""
    import src.tools.github_tool as gth

    # Simulate PyGithub being absent by patching _PYGITHUB_AVAILABLE
    monkeypatch.setattr(gth, "_PYGITHUB_AVAILABLE", False)

    # Set the mock flag after module import (the "late" scenario)
    monkeypatch.setenv("GITHUB_MOCK_ALLOWED", "true")
    config_module.get_settings.cache_clear()

    try:
        tool = gth.GitHubTool()
        # Should have reached here without RuntimeError, using the mock Github
        assert tool.gh is not None
    finally:
        config_module.get_settings.cache_clear()
