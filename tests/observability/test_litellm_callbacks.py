import litellm
import os
from src.observability.litellm_callbacks import setup_callbacks


def test_callbacks_are_registered_in_litellm(monkeypatch):
    litellm.success_callback = []
    litellm.failure_callback = []
    monkeypatch.setattr(
        "src.observability.litellm_callbacks._module_available",
        lambda module_name: True,
    )

    # Setup dummy env for activation to ensure the branches are hit
    os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-123"
    os.environ["HELICONE_API_KEY"] = "sk-123"
    
    setup_callbacks()
    
    assert "langfuse" in litellm.success_callback
    assert "langfuse" in litellm.failure_callback
    assert "helicone" in litellm.success_callback
