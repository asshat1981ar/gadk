"""Tests for Phase 3a routing + degraded-fallback in retrieve_context.

Kept in a separate module from the existing `test_retrieval_context.py`
(which depends on llama-index) so these tests run in the stripped-down
CI matrix even if llama-index is absent — we patch the keyword path to
avoid the heavy import.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from src.config import Config
from src.services import retrieval_context as rc
from src.services.retrieval_context import RetrievalQuery


@pytest.fixture
def stub_keyword(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace _keyword_retrieve with a call-recording stub."""
    calls: list[str] = []

    def _stub(request: RetrievalQuery, resolved_root: Path) -> list[dict]:
        calls.append(request.query)
        return [
            {
                "path": "docs/fake.md",
                "corpus": "specs",
                "score": 1.0,
                "snippet": f"kw:{request.query}",
            }
        ]

    monkeypatch.setattr(rc, "_keyword_retrieve", _stub)
    return calls


def test_keyword_backend_routes_to_keyword(
    monkeypatch: pytest.MonkeyPatch,
    stub_keyword: list[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "keyword")
    result = rc.retrieve_context(RetrievalQuery(query="phase gate"), repo_root=tmp_path)
    assert stub_keyword == ["phase gate"]
    assert result["sources"][0]["snippet"] == "kw:phase gate"


def test_unknown_backend_falls_back_to_keyword(
    monkeypatch: pytest.MonkeyPatch,
    stub_keyword: list[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "mystery-db")
    result = rc.retrieve_context(RetrievalQuery(query="hi"), repo_root=tmp_path)
    assert stub_keyword == ["hi"]
    assert result["sources"][0]["snippet"] == "kw:hi"


def test_vector_backend_falls_back_and_emits_degraded(
    monkeypatch: pytest.MonkeyPatch,
    stub_keyword: list[str],
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")
    # Plant a corpus doc so _vector_retrieve reaches backend.query() and
    # then raises VectorBackendUnavailable (NullVectorIndex behavior).
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    (specs_dir / "spec.md").write_text("some substantive content here", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="retrieval_context"):
        result = rc.retrieve_context(RetrievalQuery(query="q"), repo_root=tmp_path)

    assert stub_keyword == ["q"], "keyword fallback should run after vector unavailable"
    assert any("retrieval.degraded" in rec.message for rec in caplog.records)
    assert result["sources"][0]["snippet"] == "kw:q"


def test_vector_backend_empty_corpus_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
    stub_keyword: list[str],
    tmp_path: Path,
) -> None:
    # No corpus files on disk at all.
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")
    result = rc.retrieve_context(RetrievalQuery(query="q"), repo_root=tmp_path)
    # With no docs, vector path returns [] WITHOUT raising, so keyword
    # fallback should NOT fire.
    assert stub_keyword == [], "empty corpus must not trigger degraded fallback"
    assert result == {"query": "q", "corpus": list(rc.DEFAULT_CORPUS), "sources": []}


def test_vector_backend_upsert_path_runs_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
    stub_keyword: list[str],
    tmp_path: Path,
) -> None:
    """Exercise the upsert loop to lock in behavior for Phase 3b.

    Once a real backend lands, this test will start returning hits
    directly instead of falling back; the assertion below deliberately
    accepts either outcome so Phase 3b doesn't have to rewrite it.
    """
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")
    # Two docs across two corpora.
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "specs" / "a.md").write_text("alpha beta gamma")
    (tmp_path / "docs" / "superpowers" / "plans" / "b.md").write_text("plan body text")

    result = rc.retrieve_context(RetrievalQuery(query="alpha"), repo_root=tmp_path)
    # Phase 3a: falls back to keyword (our stub). Phase 3b: vector returns hits directly.
    assert result["sources"], "expected at least one source from either backend"


def test_vector_backend_end_to_end_with_injected_embedder(
    monkeypatch: pytest.MonkeyPatch,
    stub_keyword: list[str],
    tmp_path: Path,
) -> None:
    """Phase 3c: when an embedder is installed via set_embedder, the vector
    path actually serves hits (no keyword fallback)."""
    # Word-hash embedder — matches the SqliteVecBackend fixture.
    import hashlib
    import math
    from collections.abc import Sequence

    def _fake_embedder(texts: Sequence[str]) -> list[list[float]]:
        out = []
        for text in texts:
            bucket = [0.0] * 32
            for word in text.lower().replace("-", " ").split():
                h = hashlib.md5(word.encode()).digest()
                idx = int.from_bytes(h[:4], "big") % 32
                bucket[idx] += 1.0
            n = math.sqrt(sum(v * v for v in bucket)) or 1.0
            out.append([v / n for v in bucket])
        return out

    from src.services.vector_index import _SQLITE_VEC_AVAILABLE, SqliteVecBackend

    if not _SQLITE_VEC_AVAILABLE:
        pytest.skip("sqlite-vec not installed")

    # Point the backend at a scratch db + dim=8 to match the fake.
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")

    def _resolve(*, embedder=None, backend_name=None, db_path="sessions.db", dim=1536):
        return SqliteVecBackend(embedder=embedder, db_path=tmp_path / "vec.db", dim=32)

    monkeypatch.setattr(rc, "resolve_vector_backend", _resolve)
    rc.set_embedder(_fake_embedder)
    try:
        (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
        (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
        (tmp_path / "docs" / "superpowers" / "specs" / "memory.md").write_text(
            "sqlite-vec vector retrieval embedding index"
        )
        (tmp_path / "docs" / "superpowers" / "plans" / "other.md").write_text(
            "unrelated document about lint and formatting"
        )

        result = rc.retrieve_context(
            RetrievalQuery(query="vector embedding retrieval"), repo_root=tmp_path
        )

        # Keyword stub must NOT fire; we should have real vector hits.
        assert stub_keyword == [], "vector path must not fall back when backend works"
        assert result["sources"], "expected real hits from the vector backend"
        # Confirm the memory doc is in the returned set — exact ranking is
        # not promised for the fake embedder, but the right doc must show up.
        paths = {s["path"] for s in result["sources"]}
        assert "docs/superpowers/specs/memory.md" in paths or any(
            "memory.md" in p for p in paths
        ), f"expected memory.md in hits, got {paths}"
    finally:
        rc.set_embedder(None)


def test_set_embedder_override_wins_over_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    rc.set_embedder(sentinel)
    try:
        assert rc._resolve_embedder() is sentinel
    finally:
        rc.set_embedder(None)


def test_vector_retrieve_skips_reembedding_unchanged_docs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Reviewer feedback on #11: avoid re-embedding the whole corpus on
    every call. Second retrieve with unchanged files should trigger zero
    new upsert() calls on the backend."""
    import math
    from collections.abc import Sequence

    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")

    embed_calls: list[int] = []

    def _fake_embedder(texts: Sequence[str]) -> list[list[float]]:
        embed_calls.append(len(texts))
        out = []
        for text in texts:
            bucket = [0.0] * 32
            for word in text.lower().split():
                h = hash(word) & 0x7FFFFFFF
                bucket[h % 32] += 1.0
            n = math.sqrt(sum(v * v for v in bucket)) or 1.0
            out.append([v / n for v in bucket])
        return out

    class _SpyBackend:
        name = "spy"
        upsert_count = 0

        def __init__(self, embedder):
            self._embedder = embedder
            self._docs: dict[str, tuple[str, list[float]]] = {}

        def upsert(self, doc_id, text, metadata=None):
            type(self).upsert_count += 1
            self._docs[doc_id] = (text, self._embedder([text])[0])

        def query(self, text, top_k=3):
            from src.services.vector_index import SearchHit

            qv = self._embedder([text])[0]
            scored = [
                (doc_id, t, sum(a * b for a, b in zip(v, qv, strict=True)))
                for doc_id, (t, v) in self._docs.items()
            ]
            scored.sort(key=lambda x: -x[2])
            return [
                SearchHit(doc_id=d, text=t, score=s, metadata={"path": d})
                for d, t, s in scored[:top_k]
            ]

        def close(self):
            pass

        def known_doc_ids(self):
            return set(self._docs)

        def delete(self, doc_id):
            self._docs.pop(doc_id, None)

    backend_instance = _SpyBackend(_fake_embedder)

    monkeypatch.setattr(rc, "resolve_vector_backend", lambda **kwargs: backend_instance)
    rc.set_embedder(_fake_embedder)
    rc._doc_hashes.clear()
    try:
        (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
        (tmp_path / "docs" / "superpowers" / "specs" / "a.md").write_text("alpha beta gamma")
        (tmp_path / "docs" / "superpowers" / "specs" / "b.md").write_text("delta epsilon zeta")

        # First call: upserts both docs.
        rc.retrieve_context(RetrievalQuery(query="alpha"), repo_root=tmp_path)
        first_upserts = _SpyBackend.upsert_count
        assert first_upserts == 2, f"first call should upsert 2 docs, got {first_upserts}"

        # Second call with identical files: no new upserts.
        rc.retrieve_context(RetrievalQuery(query="alpha"), repo_root=tmp_path)
        assert (
            _SpyBackend.upsert_count == first_upserts
        ), "unchanged docs must not trigger re-embedding"

        # Modify one file: only that one re-upserts.
        (tmp_path / "docs" / "superpowers" / "specs" / "a.md").write_text("alpha beta gamma NEW")
        rc.retrieve_context(RetrievalQuery(query="alpha"), repo_root=tmp_path)
        assert _SpyBackend.upsert_count == first_upserts + 1, "only the changed doc should re-embed"
    finally:
        rc.set_embedder(None)
        rc._doc_hashes.clear()


def test_vector_retrieve_closes_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Reviewer feedback on #11: SqliteVecBackend connections must not leak."""
    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")

    class _CloseTracker:
        name = "closable"
        closed = 0

        def upsert(self, **kwargs):
            pass

        def query(self, *args, **kwargs):
            return []

        def close(self):
            type(self).closed += 1

        def known_doc_ids(self):
            return set()

        def delete(self, doc_id):
            pass

    monkeypatch.setattr(rc, "resolve_vector_backend", lambda **kwargs: _CloseTracker())
    rc.set_embedder(lambda texts: [[0.0] * 32 for _ in texts])
    rc._doc_hashes.clear()
    try:
        (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
        (tmp_path / "docs" / "superpowers" / "specs" / "a.md").write_text("content")
        rc.retrieve_context(RetrievalQuery(query="q"), repo_root=tmp_path)
        assert _CloseTracker.closed == 1, "backend.close() must be called in finally block"
    finally:
        rc.set_embedder(None)
        rc._doc_hashes.clear()


def test_retrieve_context_falls_back_on_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
    stub_keyword: list[str],
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Reviewer feedback on #11: any vector-path failure degrades cleanly
    to keyword, not just VectorBackendUnavailable."""
    import logging

    monkeypatch.setattr(Config, "RETRIEVAL_BACKEND", "vector")

    def _boom(request, resolved_root):
        raise RuntimeError("schema migration failed")

    monkeypatch.setattr(rc, "_vector_retrieve", _boom)

    with caplog.at_level(logging.WARNING, logger="retrieval_context"):
        result = rc.retrieve_context(RetrievalQuery(query="q"), repo_root=tmp_path)

    assert stub_keyword == ["q"], "keyword fallback should fire on any vector-path error"
    assert any("unexpected_error" in rec.message for rec in caplog.records)
    assert result["sources"][0]["snippet"] == "kw:q"
