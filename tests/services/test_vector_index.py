"""Tests for the Phase 3a vector-retrieval protocol + null backend."""

from __future__ import annotations

import pytest

from src.config import Config
from src.services.vector_index import (
    NullVectorIndex,
    SearchHit,
    VectorBackendUnavailable,
    VectorIndex,
    resolve_vector_backend,
)


def test_null_backend_satisfies_protocol() -> None:
    backend = NullVectorIndex()
    assert isinstance(backend, VectorIndex)
    assert backend.name == "null"


def test_null_backend_accepts_upserts() -> None:
    backend = NullVectorIndex()
    # Upsert is a no-op; must not raise.
    backend.upsert("doc-1", "hello world", {"corpus": "specs"})
    backend.upsert("doc-2", "another doc")


def test_null_backend_query_raises_unavailable() -> None:
    backend = NullVectorIndex()
    with pytest.raises(VectorBackendUnavailable):
        backend.query("anything", top_k=3)


def test_null_backend_clear_is_noop() -> None:
    NullVectorIndex().clear()


def test_search_hit_is_frozen() -> None:
    hit = SearchHit(doc_id="x", text="t", score=0.5)
    with pytest.raises(Exception):
        hit.score = 0.9  # type: ignore[misc]


def test_search_hit_default_metadata() -> None:
    hit = SearchHit(doc_id="x", text="t", score=0.5)
    assert hit.metadata == {}


def test_resolve_returns_null_for_vector_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")
    backend = resolve_vector_backend()
    assert isinstance(backend, NullVectorIndex)


def test_resolve_normalizes_synonyms() -> None:
    assert isinstance(resolve_vector_backend(backend_name="sqlite-vec"), NullVectorIndex)
    assert isinstance(resolve_vector_backend(backend_name="SQLITEVEC"), NullVectorIndex)


def test_resolve_raises_for_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "keyword")
    with pytest.raises(VectorBackendUnavailable):
        resolve_vector_backend()


def test_resolve_raises_for_unknown() -> None:
    with pytest.raises(VectorBackendUnavailable):
        resolve_vector_backend(backend_name="mystery-db")
