import importlib

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
