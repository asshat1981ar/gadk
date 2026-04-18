"""Tests for the Phase 3b SqliteVecBackend.

Uses a deterministic fake embedder so the tests are hermetic — no
network calls, no LiteLLM dependency. Real embeddings are exercised
in Phase 3c once the LiteLLM wiring lands.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

import pytest

from src.services.vector_index import (
    _SQLITE_VEC_AVAILABLE,
    Embedder,
    NullVectorIndex,
    SearchHit,
    SqliteVecBackend,
    VectorBackendUnavailable,
    VectorIndex,
    resolve_vector_backend,
)

# Skip the whole module cleanly if the native extension isn't installed —
# Phase 3a's NullVectorIndex tests cover the absent-backend case already.
pytestmark = pytest.mark.skipif(
    not _SQLITE_VEC_AVAILABLE, reason="sqlite-vec extension not installed"
)


# ---------------------------------------------------------------------------
# Deterministic fake embedder
# ---------------------------------------------------------------------------


def _make_fake_embedder(dim: int = 8) -> Embedder:
    """Return a deterministic embedder that maps text → stable unit vector.

    Uses character-n-gram hashing into ``dim`` buckets; the same text
    always produces the same vector, and vectors for similar strings
    share more components, so the L2 distance behaves roughly like
    a semantic-similarity proxy for the tests.
    """

    def _embed(texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            bucket = [0.0] * dim
            normalized = text.lower().strip()
            if not normalized:
                out.append([0.0] * dim)
                continue
            for i in range(len(normalized) - 2):
                trigram = normalized[i : i + 3]
                idx = hash(trigram) % dim
                bucket[idx] += 1.0
            # Also count individual chars so short docs still differ.
            for ch in normalized:
                bucket[ord(ch) % dim] += 0.25
            norm = math.sqrt(sum(v * v for v in bucket)) or 1.0
            out.append([v / norm for v in bucket])
        return out

    return _embed


@pytest.fixture
def backend(tmp_path: Path) -> SqliteVecBackend:
    db = tmp_path / "vec.db"
    b = SqliteVecBackend(
        embedder=_make_fake_embedder(dim=8),
        db_path=db,
        dim=8,
    )
    yield b
    b.close()


# ---------------------------------------------------------------------------
# Protocol / construction
# ---------------------------------------------------------------------------


def test_backend_satisfies_protocol(backend: SqliteVecBackend) -> None:
    assert isinstance(backend, VectorIndex)
    assert backend.name == "sqlite-vec"


def test_backend_rejects_embedder_dimension_mismatch(tmp_path: Path) -> None:
    def _bad(_: Sequence[str]) -> list[list[float]]:
        return [[1.0, 2.0]]  # dim=2

    backend = SqliteVecBackend(embedder=_bad, db_path=tmp_path / "db.sqlite", dim=8)
    try:
        with pytest.raises(VectorBackendUnavailable):
            backend.upsert("doc-1", "hello")
    finally:
        backend.close()


def test_backend_rejects_malformed_embedder_output(tmp_path: Path) -> None:
    def _empty(_: Sequence[str]) -> list[list[float]]:
        return []

    backend = SqliteVecBackend(embedder=_empty, db_path=tmp_path / "db.sqlite", dim=8)
    try:
        with pytest.raises(VectorBackendUnavailable):
            backend.upsert("doc-1", "hello")
    finally:
        backend.close()


# ---------------------------------------------------------------------------
# Round-trip behavior
# ---------------------------------------------------------------------------


def test_upsert_then_query_returns_inserted_doc(backend: SqliteVecBackend) -> None:
    backend.upsert("doc-1", "phase gate framework", {"corpus": "specs"})
    hits = backend.query("phase gate framework", top_k=1)
    assert len(hits) == 1
    assert hits[0].doc_id == "doc-1"
    assert hits[0].text == "phase gate framework"
    assert hits[0].metadata["corpus"] == "specs"
    # Score should be near 1.0 when querying the exact indexed string.
    assert 0.8 < hits[0].score <= 1.0


def test_query_orders_by_similarity(backend: SqliteVecBackend) -> None:
    backend.upsert("alpha", "alpha beta gamma delta")
    backend.upsert("omega", "completely different string here")
    hits = backend.query("alpha beta gamma delta", top_k=2)
    # The identical doc should come first.
    assert hits[0].doc_id == "alpha"
    assert hits[0].score > hits[1].score


def test_query_empty_index_returns_no_hits(backend: SqliteVecBackend) -> None:
    assert backend.query("anything", top_k=3) == []


def test_query_with_zero_top_k_is_empty(backend: SqliteVecBackend) -> None:
    backend.upsert("doc", "text")
    assert backend.query("text", top_k=0) == []


def test_upsert_overwrites_same_doc_id(backend: SqliteVecBackend) -> None:
    backend.upsert("doc-1", "original content", {"version": 1})
    backend.upsert("doc-1", "replacement content", {"version": 2})
    hits = backend.query("replacement content", top_k=5)
    ids = [h.doc_id for h in hits]
    # Only one entry should exist for doc-1.
    assert ids.count("doc-1") == 1
    [doc1] = [h for h in hits if h.doc_id == "doc-1"]
    assert doc1.text == "replacement content"
    assert doc1.metadata["version"] == 2


def test_clear_drops_all_docs(backend: SqliteVecBackend) -> None:
    backend.upsert("a", "first doc")
    backend.upsert("b", "second doc")
    backend.clear()
    assert backend.query("first", top_k=3) == []


def test_recall_at_k_on_small_corpus(backend: SqliteVecBackend) -> None:
    """Insert 5 themed docs and confirm the thematically-closest one wins."""
    backend.upsert("phase", "SDLC phase gate controller and quality gates")
    backend.upsert("memory", "sqlite-vec vector retrieval embedding index")
    backend.upsert("prompt", "self-prompt loop gap signals coverage backlog")
    backend.upsert("atomic", "atomic writes state manager concurrent safety")
    backend.upsert("lint", "ruff format check pycodestyle pyflakes isort")

    hits = backend.query("vector embedding retrieval", top_k=5)
    assert hits
    # The memory doc should beat the others given the shared tokens.
    assert hits[0].doc_id == "memory"


def test_hit_metadata_exposes_distance(backend: SqliteVecBackend) -> None:
    backend.upsert("doc-1", "content here")
    hit = backend.query("content here", top_k=1)[0]
    assert "distance" in hit.metadata
    assert hit.metadata["distance"] >= 0.0


# ---------------------------------------------------------------------------
# Factory wiring
# ---------------------------------------------------------------------------


def test_resolve_returns_sqlite_vec_when_embedder_supplied(tmp_path: Path) -> None:
    backend = resolve_vector_backend(
        backend_name="vector",
        embedder=_make_fake_embedder(dim=8),
        db_path=tmp_path / "fv.sqlite",
        dim=8,
    )
    try:
        assert isinstance(backend, SqliteVecBackend)
        assert backend.name == "sqlite-vec"
    finally:
        if hasattr(backend, "close"):
            backend.close()


def test_resolve_returns_null_when_no_embedder(tmp_path: Path) -> None:
    backend = resolve_vector_backend(backend_name="vector", db_path=tmp_path / "fv.sqlite")
    assert isinstance(backend, NullVectorIndex)


def test_resolve_keyword_still_raises(tmp_path: Path) -> None:
    with pytest.raises(VectorBackendUnavailable):
        resolve_vector_backend(backend_name="keyword", db_path=tmp_path / "fv.sqlite")


def test_search_hit_metadata_defaults_to_empty() -> None:
    hit = SearchHit(doc_id="x", text="t", score=0.5)
    assert hit.metadata == {}
