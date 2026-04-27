"""Tests for OllamaCloudBackend."""

from __future__ import annotations

from src.services.ollama_cloud_backend import OllamaCloudBackend


def test_backend_initialization():
    """OllamaCloudBackend initializes with correct defaults."""
    backend = OllamaCloudBackend()
    assert backend.model == "minimax-m2.7:cloud"
    assert backend.base_url == "https://ollama.com"
    assert backend.api_key is None


def test_backend_custom_model():
    """OllamaCloudBackend accepts custom model name."""
    backend = OllamaCloudBackend(model="minimax-m2.5:cloud")
    assert backend.model == "minimax-m2.5:cloud"


def test_backend_custom_base_url():
    """OllamaCloudBackend accepts custom base URL."""
    backend = OllamaCloudBackend(base_url="http://localhost:11434")
    assert backend.base_url == "http://localhost:11434"


def test_config_defaults():
    """Ollama config flags are set correctly."""
    from src.config import Config

    assert Config.OLLAMA_MODEL == "minimax-m2.7:cloud"
    assert Config.OLLAMA_BASE_URL == "https://ollama.com"
    assert Config.LLM_MODEL == "ollama/minimax-m2.7:cloud"
    assert Config.LLM_TOOL_MODEL == "ollama/minimax-m2.7:cloud"


def test_model_router_ollama_prefix():
    """ModelRouter dispatches ollama/ prefixed models to OllamaCloudBackend."""
    from src.services.model_router import ModelRouter

    router = ModelRouter()
    backend = router.get_backend("ollama/minimax-m2.7:cloud")
    assert backend is not None
    assert hasattr(backend, "chat")
    assert hasattr(backend, "chat_stream")


def test_model_router_ollama_prefix_custom_model():
    """ModelRouter handles ollama/ prefix with custom model name."""
    from src.services.model_router import ModelRouter

    router = ModelRouter()
    backend = router.get_backend("ollama/minimax-m2.5:cloud")
    assert backend is not None
    assert backend.model == "minimax-m2.5:cloud"
