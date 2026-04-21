"""Vector-retrieval backend abstraction.

Phase 3a shipped the protocol + null placeholder. Phase 3b adds a real
``SqliteVecBackend`` that embeds vectors in a sqlite database via the
``sqlite-vec`` extension. The embedding function is injectable so
tests don't need network access and so Phase 3c can wire in LiteLLM
embeddings without touching the backend.

Design notes:

- ``VectorIndex`` is a stateful protocol (``upsert`` + ``query`` + ``clear``)
  so incremental indexing can work when embeddings are expensive.
- ``VectorBackendUnavailable`` is the canonical way for a backend to
  signal "you asked for vector mode but I can't deliver" — callers always
  fall back to keyword retrieval rather than surface the exception.
- ``SqliteVecBackend`` persists vectors and metadata in two tables
  (``gadk_vec_index`` via vec0 + ``gadk_vec_meta`` for text+metadata).
  Default db path is ``sessions.db`` so the vectors live alongside ADK
  session data; callers can point it elsewhere for isolation.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from src.config import Config
from src.observability.logger import get_logger

logger = get_logger("vector_index")

try:
    import sqlite_vec as _sqlite_vec  # type: ignore[import]

    _SQLITE_VEC_AVAILABLE = True
except ImportError:  # pragma: no cover — depends on environment
    _sqlite_vec = None  # type: ignore[assignment]
    _SQLITE_VEC_AVAILABLE = False


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


#: Signature of an embedding function.
#:
#: Must accept a batch of texts and return one float vector per input,
#: each of the same dimensionality the backend was constructed with.
#: Implementations are expected to be deterministic for identical input
#: (enables caching) but the backend does not require it.
Embedder = Callable[[Sequence[str]], list[list[float]]]


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

    Returned by :func:`resolve_vector_backend` when vector mode is
    requested but the caller did not supply an :data:`Embedder` or the
    ``sqlite-vec`` extension is unavailable. Exercising the degraded
    fallback path through this class keeps the keyword-retrieval
    invariant live in tests.
    """

    name = "null"

    def upsert(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        # No-op: accepting writes without complaining keeps the placeholder
        # cheap to slot in while callers migrate onto a real embedder.
        return None

    def query(self, text: str, top_k: int = 3) -> list[SearchHit]:
        raise VectorBackendUnavailable(
            "NullVectorIndex cannot serve queries; supply an Embedder and "
            "install sqlite-vec to enable real vector retrieval."
        )

    def clear(self) -> None:
        return None


class SqliteVecBackend:
    """Vector index backed by the sqlite-vec extension.

    Vectors live in a ``vec0`` virtual table keyed by rowid; text and
    metadata live in a sibling table joined on rowid. The connection is
    owned by the backend and closed via :meth:`close`.
    """

    name = "sqlite-vec"

    _INDEX_TABLE = "gadk_vec_index"
    _META_TABLE = "gadk_vec_meta"

    def __init__(
        self,
        *,
        embedder: Embedder,
        db_path: str | Path = "sessions.db",
        dim: int = 1536,
    ) -> None:
        if not _SQLITE_VEC_AVAILABLE:
            raise VectorBackendUnavailable(
                "sqlite-vec is not installed; run `pip install sqlite-vec` "
                "or install the [memory] extra."
            )
        self._embedder = embedder
        self._dim = int(dim)
        self._db_path = str(db_path)
        self._conn = self._open_db()
        self._ensure_schema()

    # -- connection management ------------------------------------------

    def _open_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.enable_load_extension(True)
        try:
            _sqlite_vec.load(conn)
        except Exception as exc:
            conn.close()
            logger.warning("sqlite_vec.load failed: %s %s", type(exc).__name__, exc)
            raise VectorBackendUnavailable(f"sqlite-vec extension failed to load: {exc}") from exc
        conn.enable_load_extension(False)
        return conn

    def _ensure_schema(self) -> None:
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {self._INDEX_TABLE} "  # nosec B608 — table name is a hardcoded module constant, not user input
            f"USING vec0(embedding FLOAT[{self._dim}])"
        )
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self._META_TABLE} ("  # nosec B608 — table name is a hardcoded module constant, not user input
            "rowid INTEGER PRIMARY KEY, "
            "doc_id TEXT UNIQUE NOT NULL, "
            "text TEXT NOT NULL, "
            "metadata TEXT"
            ")"
        )
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    # -- encoding helpers -----------------------------------------------

    def _encode_vector(self, vec: Sequence[float]) -> str:
        if len(vec) != self._dim:
            raise VectorBackendUnavailable(
                f"embedder returned vector of length {len(vec)} but "
                f"backend is dimension {self._dim}"
            )
        return json.dumps([float(x) for x in vec])

    def _embed_single(self, text: str) -> str:
        batch = self._embedder([text])
        if not batch or len(batch) != 1:
            raise VectorBackendUnavailable("embedder returned malformed output; expected 1 vector")
        return self._encode_vector(batch[0])

    # -- protocol methods -----------------------------------------------

    def upsert(self, doc_id: str, text: str, metadata: dict[str, Any] | None = None) -> None:
        vector = self._embed_single(text)
        # Wrap all four table mutations in a transaction so an interruption
        # can't leave the meta table populated without a matching vector
        # row (or vice versa). `with self._conn:` commits on success and
        # rolls back on exception.
        with self._conn:
            row = self._conn.execute(
                f"SELECT rowid FROM {self._META_TABLE} WHERE doc_id = ?",
                (doc_id,),  # nosec B608 — table name is a hardcoded module constant, not user input
            ).fetchone()
            if row is not None:
                rowid = row[0]
                self._conn.execute(f"DELETE FROM {self._INDEX_TABLE} WHERE rowid = ?", (rowid,))  # nosec B608 — table name is a hardcoded module constant, not user input
                self._conn.execute(
                    f"UPDATE {self._META_TABLE} SET text = ?, metadata = ? WHERE rowid = ?",  # nosec B608 — table name is a hardcoded module constant, not user input
                    (text, json.dumps(metadata or {}), rowid),
                )
            else:
                cursor = self._conn.execute(
                    f"INSERT INTO {self._META_TABLE} (doc_id, text, metadata) VALUES (?, ?, ?)",  # nosec B608 — table name is a hardcoded module constant, not user input
                    (doc_id, text, json.dumps(metadata or {})),
                )
                rowid = cursor.lastrowid
            self._conn.execute(
                f"INSERT INTO {self._INDEX_TABLE} (rowid, embedding) VALUES (?, ?)",  # nosec B608 — table name is a hardcoded module constant, not user input
                (rowid, vector),
            )

    def delete(self, doc_id: str) -> None:
        """Remove a single document by ``doc_id``. Silent no-op if absent."""
        with self._conn:
            row = self._conn.execute(
                f"SELECT rowid FROM {self._META_TABLE} WHERE doc_id = ?",
                (doc_id,),  # nosec B608 — table name is a hardcoded module constant, not user input
            ).fetchone()
            if row is None:
                return
            rowid = row[0]
            self._conn.execute(f"DELETE FROM {self._INDEX_TABLE} WHERE rowid = ?", (rowid,))  # nosec B608 — table name is a hardcoded module constant, not user input
            self._conn.execute(f"DELETE FROM {self._META_TABLE} WHERE rowid = ?", (rowid,))  # nosec B608 — table name is a hardcoded module constant, not user input

    def known_doc_ids(self, *, corpora: Iterable[str] | None = None) -> set[str]:
        """Return every ``doc_id`` currently indexed.

        When ``corpora`` is provided, returns only docs whose stored
        metadata ``corpus`` key is in that iterable. Used by the
        retrieval-context sync loop to scope stale-doc cleanup so it
        never touches docs belonging to corpora that weren't part of
        the current request.
        """
        rows = self._conn.execute(f"SELECT doc_id, metadata FROM {self._META_TABLE}").fetchall()  # nosec B608 — table name is a hardcoded module constant, not user input
        if corpora is None:
            return {row[0] for row in rows}
        wanted = {c.strip().lower() for c in corpora}
        ids: set[str] = set()
        for doc_id, raw in rows:
            try:
                meta = json.loads(raw or "{}")
            except (TypeError, ValueError):
                continue
            corpus = str(meta.get("corpus", "")).strip().lower()
            if corpus in wanted:
                ids.add(doc_id)
        return ids

    def query(self, text: str, top_k: int = 3) -> list[SearchHit]:
        if top_k <= 0:
            return []
        vector = self._embed_single(text)
        rows = self._conn.execute(
            f"""
            SELECT m.doc_id, m.text, m.metadata, v.distance
            FROM {self._INDEX_TABLE} AS v
            JOIN {self._META_TABLE} AS m ON m.rowid = v.rowid
            WHERE v.embedding MATCH ?
              AND k = ?
            ORDER BY v.distance
            """,  # nosec B608 — table names are hardcoded module constants
            (vector, int(top_k)),
        ).fetchall()
        return [
            SearchHit(
                doc_id=row[0],
                text=row[1],
                # sqlite-vec returns L2 distance; convert to a score in [0, 1]
                # where closer = higher score. Callers that care about raw
                # distance can read it from metadata["distance"].
                score=1.0 / (1.0 + float(row[3])),
                metadata={**json.loads(row[2] or "{}"), "distance": float(row[3])},
            )
            for row in rows
        ]

    def clear(self) -> None:
        self._conn.execute(f"DELETE FROM {self._INDEX_TABLE}")  # nosec B608 — table name is a hardcoded module constant, not user input
        self._conn.execute(f"DELETE FROM {self._META_TABLE}")  # nosec B608 — table name is a hardcoded module constant, not user input
        self._conn.commit()


def resolve_vector_backend(
    *,
    backend_name: str | None = None,
    embedder: Embedder | None = None,
    db_path: str | Path = "sessions.db",
    dim: int = 1536,
) -> VectorIndex:
    """Return a :class:`VectorIndex` for the configured backend.

    Behavior:

    - When a non-vector backend is requested (``keyword``, ``mystery-db``,
      etc.), raises :class:`VectorBackendUnavailable` so the caller can
      fall back to keyword retrieval through its normal exception-handling
      path. Callers **must** catch this exception; :func:`retrieve_context`
      does so and emits a ``retrieval.degraded`` log.
    - When a vector backend is requested but ``sqlite-vec`` is not
      installed, returns :class:`NullVectorIndex` — whose ``query`` also
      raises ``VectorBackendUnavailable`` so the same fallback path fires.
    - When a vector backend is requested without an ``embedder``, also
      returns :class:`NullVectorIndex` (same degraded-fallback contract).
    - When everything is available, returns a real :class:`SqliteVecBackend`.
    """
    resolved = (backend_name or Config.RETRIEVAL_BACKEND or "keyword").strip().lower()
    if resolved not in {"vector", "sqlite-vec", "sqlitevec"}:
        raise VectorBackendUnavailable(
            f"retrieval backend {resolved!r} is not a vector backend; stay on keyword retrieval"
        )
    if not _SQLITE_VEC_AVAILABLE:
        logger.info("resolve_vector_backend: sqlite-vec missing; falling back to null backend")
        return NullVectorIndex()
    if embedder is None:
        logger.debug(
            "resolve_vector_backend: no embedder supplied; returning NullVectorIndex "
            "(caller must pass embedder= to get a real SqliteVecBackend)"
        )
        return NullVectorIndex()
    return SqliteVecBackend(embedder=embedder, db_path=db_path, dim=dim)


__all__ = [
    "Embedder",
    "NullVectorIndex",
    "SearchHit",
    "SqliteVecBackend",
    "VectorBackendUnavailable",
    "VectorIndex",
    "resolve_vector_backend",
]
