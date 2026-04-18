from src.config import Config


def test_fallback_models_configured():
    assert len(Config.FALLBACK_MODELS) >= 2
    assert all("/" in m for m in Config.FALLBACK_MODELS)


def test_timeout_and_retries_configured():
    assert Config.LLM_TIMEOUT > 0
    assert Config.LLM_RETRIES >= 0
