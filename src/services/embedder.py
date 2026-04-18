"""LiteLLM-backed :data:`Embedder` implementation.

Wraps ``litellm.embedding`` so the Phase 3b ``SqliteVecBackend`` can
produce real semantic vectors. Quota enforcement lives in
:class:`src.services.embed_quota.EmbedQuota` so this module stays
embedding-agnostic beyond counting tokens.

Design notes:

- ``LiteLLMEmbedder`` is a callable satisfying the ``Embedder`` signature
  ``(Sequence[str]) -> list[list[float]]`` — exactly what
  :class:`src.services.vector_index.SqliteVecBackend` expects.
- The ``litellm`` import is lazy so test environments without the
  package (or without API credentials) can still import this module
  for type checking.
- On quota exhaustion or LiteLLM errors, raises
  :class:`src.services.vector_index.VectorBackendUnavailable` — the
  canonical signal that the vector path should degrade to keyword.
"""

from __future__ import annotations

from collections.abc import Sequence

from src.config import Config
from src.observability.logger import get_logger
from src.services.embed_quota import EmbedQuota, EmbedQuotaExceeded, estimate_tokens
from src.services.vector_index import VectorBackendUnavailable
from src.state import StateManager

logger = get_logger("embedder")


class LiteLLMEmbedder:
    """Embedder backed by ``litellm.embedding`` + ``EmbedQuota``.

    Persistence note: the embedder writes the daily token total through
    the ``EmbedQuota`` it's given, which in turn writes the whole
    ``state.json`` via its ``StateManager``. To avoid racing with the
    SDLC loop's writes, callers **must** pass in either a ``quota`` or
    a ``state_manager`` that's shared with the rest of the swarm. The
    factory :func:`build_default_embedder` enforces this — instantiating
    ``LiteLLMEmbedder()`` without one of those args raises.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        quota: EmbedQuota | None = None,
        state_manager: StateManager | None = None,
    ) -> None:
        if quota is None and state_manager is None:
            raise ValueError(
                "LiteLLMEmbedder requires either a shared EmbedQuota or "
                "a StateManager; auto-constructing a fresh StateManager "
                "risks racing with the swarm's writers. Use "
                "build_default_embedder() or pass state_manager= explicitly."
            )
        self._model = model or Config.EMBED_MODEL
        if quota is None:
            quota = EmbedQuota(state_manager)  # type: ignore[arg-type]
        self._quota = quota

    @property
    def model(self) -> str:
        return self._model

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        texts = list(texts or [])
        if not texts:
            return []

        # Pre-call quota check on the rough estimate. If this trips, we
        # raise before spending any LiteLLM-side tokens; the actual
        # consumption from the response supersedes the estimate below.
        pre_estimate = estimate_tokens(texts)
        try:
            self._quota.check(pre_estimate)
        except EmbedQuotaExceeded as exc:
            raise VectorBackendUnavailable(f"embed quota exceeded: {exc}") from exc

        try:
            import litellm  # local import: heavy dep, env-dependent
        except ImportError as exc:  # pragma: no cover — depends on env
            raise VectorBackendUnavailable(
                f"litellm not installed; cannot produce embeddings: {exc}"
            ) from exc

        try:
            response = litellm.embedding(model=self._model, input=texts)
        except Exception as exc:  # noqa: BLE001 — external SDK surface
            logger.error("litellm.embedding failed: %s", exc, exc_info=True)
            raise VectorBackendUnavailable(f"embedding call failed: {exc}") from exc

        # Extract vectors. LiteLLM normalizes to OpenAI-shape:
        # {"data": [{"embedding": [...]}, ...], "usage": {...}}
        try:
            data = response["data"]  # type: ignore[index]
            vectors = [list(map(float, item["embedding"])) for item in data]
        except (KeyError, TypeError, ValueError) as exc:
            logger.error("malformed embedding response: %s", exc)
            raise VectorBackendUnavailable("malformed embedding response") from exc

        # Record actual token usage when the provider surfaces it;
        # otherwise keep the pre-call estimate.
        used = pre_estimate
        try:
            usage = response.get("usage") if hasattr(response, "get") else response["usage"]
            if isinstance(usage, dict):
                total = usage.get("total_tokens") or usage.get("prompt_tokens")
                if total is not None:
                    used = int(total)
        except (KeyError, TypeError):
            pass
        self._quota.record(used)
        return vectors


def build_default_embedder(
    *,
    state_manager: StateManager | None = None,
) -> LiteLLMEmbedder | None:
    """Construct the default embedder used by :mod:`retrieval_context`.

    ``state_manager`` is **required in practice** — pass in the same
    ``StateManager`` instance the swarm uses elsewhere so quota writes
    don't race with task-state writes. Callers that don't have one
    already can construct ``StateManager()`` once at bootstrap and
    thread it through.

    Returns ``None`` when:
    - ``Config.TEST_MODE`` is on (keep tests hermetic unless they opt in
      via their own embedder fixture);
    - ``Config.OPENROUTER_API_KEY`` is missing (fail fast via the
      keyword-fallback path instead of surfacing auth errors);
    - or the current ``Config.RETRIEVAL_BACKEND`` is not a vector name
      (don't pay the setup cost if we'll never be used).
    """
    if Config.TEST_MODE:
        return None
    if not Config.OPENROUTER_API_KEY:
        logger.debug("build_default_embedder: no OPENROUTER_API_KEY; skipping")
        return None
    backend = (Config.RETRIEVAL_BACKEND or "").strip().lower()
    if backend not in {"vector", "sqlite-vec", "sqlitevec"}:
        return None
    # Fall back to a fresh StateManager only when the caller didn't pass
    # one — LiteLLMEmbedder enforces that *something* is supplied, so we
    # surface a construction error rather than silently spawning a racing
    # writer.
    return LiteLLMEmbedder(state_manager=state_manager or StateManager())


__all__ = ["LiteLLMEmbedder", "build_default_embedder"]
