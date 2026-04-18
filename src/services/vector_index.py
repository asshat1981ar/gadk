"""Vector-retrieval backend abstraction.

Phase 3a ships **only** the protocol and the availability probe; the real
`SqliteVecBackend` is a Phase 3b follow-up. Splitting the work this way
means:

- Callers can already route through the protocol and fall back gracefully,
  so toggling ``Config.RETRIEVAL_BACKEND=vector`` is safe (degrades to
  keyword with a structured log line).
- Phase 3b becomes a narrow change: implement ``SqliteVecBackend`` + wire
  it into ``resolve_vector_backend`` — no caller changes required.

Design notes:

- ``VectorIndex`` is a stateful protocol (``upsert`` + ``query`` + ``clear``)
  so incremental indexing can work when embeddings are expensive. A
  stateless convenience shim lives on top if callers want it.
- ``VectorBackendUnavailable`` is the canonical way for a backend to
  signal "you asked for vector mode but I can't deliver" — callers always
  fall back to keyword retrieval rather than surface the exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from src.config import Config
from src.observability.logger import get_logger

logger = get_logger("vector_index")


class VectorBackendUnavailable(RuntimeError):
    """Raised when the requested vector backend cannot satisfy a query.

    Callers should catch this and fall back to keyword retrieval,
    typically emitting a ``retrieval.degraded`` event so observability
    can spot the drop in retrieval quality.
    """


@dataclass(frozen=True)
class SearchHit:
    """Single retrieval result returned by a :class:`VectorIndex`."""

    doc_id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorIndex(Protocol):
    """Protocol every vector backend must satisfy."""

    #: Human-friendly name used in logs and degraded-event payloads.
    name: str

    def upsert(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        """Insert-or-update one document by stable id."""
        ...

    def query(self, text: str, top_k: int = 3) -> list[SearchHit]:
        """Return the top-``k`` nearest neighbors of ``text``.

        Raises:
            VectorBackendUnavailable: if the backend cannot service the
                query (missing native dependency, cold index, quota cap).
        """
        ...

    def clear(self) -> None:
        """Drop all indexed documents (primarily used in tests)."""
        ...


class NullVectorIndex:
    """Placeholder backend that never succeeds.

    Phase 3a only: the real ``SqliteVecBackend`` arrives in Phase 3b.
    Until then, requesting vector retrieval always raises
    :class:`VectorBackendUnavailable` so the caller's degraded-fallback
    path is exercised under realistic conditions.
    """

    name = "null"

    def upsert(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        # No-op: accepting writes without complaining keeps the placeholder
        # cheap to slot in while Phase 3b is in flight.
        return None

    def query(self, text: str, top_k: int = 3) -> list[SearchHit]:
        raise VectorBackendUnavailable(
            "NullVectorIndex is a Phase 3a placeholder; install sqlite-vec "
            "and wait for Phase 3b wiring to enable real vector retrieval."
        )

    def clear(self) -> None:
        return None


def resolve_vector_backend(
    *,
    backend_name: str | None = None,
) -> VectorIndex:
    """Return a :class:`VectorIndex` for the configured backend.

    Phase 3a always returns the :class:`NullVectorIndex`. The factory
    shape is final so Phase 3b can slot in ``SqliteVecBackend`` behind
    a branch on ``backend_name`` without touching callers.
    """
    resolved = (backend_name or Config.RETRIEVAL_BACKEND or "keyword").strip().lower()
    if resolved in {"vector", "sqlite-vec", "sqlitevec"}:
        # Phase 3b will switch on resolved == "sqlite-vec" and return a
        # real backend here.
        logger.debug("resolve_vector_backend: returning NullVectorIndex (Phase 3a)")
        return NullVectorIndex()
    # Any value that isn't an explicit vector name is treated as "no vector
    # backend requested"; callers stay on keyword retrieval.
    raise VectorBackendUnavailable(
        f"retrieval backend {resolved!r} is not a vector backend; stay on keyword retrieval"
    )


__all__ = [
    "NullVectorIndex",
    "SearchHit",
    "VectorBackendUnavailable",
    "VectorIndex",
    "resolve_vector_backend",
]
