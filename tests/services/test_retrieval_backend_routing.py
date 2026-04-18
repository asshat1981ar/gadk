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
