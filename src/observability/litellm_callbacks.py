import os
from importlib.util import find_spec

try:
    import litellm
except ImportError:
    litellm = None

from src.config import get_settings


def _module_available(module_name: str) -> bool:
    return find_spec(module_name) is not None


def setup_callbacks() -> None:
    """Configures global LiteLLM callbacks based on environment variables and settings."""
    settings = get_settings()

    # Langfuse/Lunary tracing
    if (os.getenv("LANGFUSE_PUBLIC_KEY") or settings.langfuse_enabled) and _module_available(
        "langfuse"
    ):
        if "langfuse" not in litellm.success_callback:
            litellm.success_callback.append("langfuse")
        if "langfuse" not in litellm.failure_callback:
            litellm.failure_callback.append("langfuse")

    # Helicone cost tracking
    if os.getenv("HELICONE_API_KEY") or settings.helicone_enabled:
        if "helicone" not in litellm.success_callback:
            litellm.success_callback.append("helicone")

    # AgentOps tracing
    if os.getenv("AGENTOPS_API_KEY") or settings.agentops_enabled:
        if "agentops" not in litellm.success_callback:
            litellm.success_callback.append("agentops")
        if "agentops" not in litellm.failure_callback:
            litellm.failure_callback.append("agentops")

    # MLflow experiment tracking
    if settings.mlflow_enabled:
        if "mlflow" not in litellm.success_callback:
            litellm.success_callback.append("mlflow")
        if "mlflow" not in litellm.failure_callback:
            litellm.failure_callback.append("mlflow")

    # Sentry exception tracking
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn)
        if "sentry" not in litellm.failure_callback:
            litellm.failure_callback.append("sentry")
