"""Tests for graph-aware context assembly in retrieval_context."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

import src.services.retrieval_context as rc
from src.services.retrieval_context import RetrievalQuery, retrieve_context
from src.memory.memory_graph import MemoryGraph, TaskOutcome


def _make_memory_graph() -> MemoryGraph:
    store = MagicMock()
    mg = MemoryGraph(store)
    mg.record_task = MagicMock(return_value="task_1")
    mg.find_similar = MagicMock(return_value=[])
    return mg


class FakeTask:
    def __init__(self, name: str) -> None:
        self.data = {"id": f"node_{name}", "name": name, "attrs": {}}


class TestRetrievalGraph:
    """Unit tests for retrieve_context memory_graph augmentation."""

    def test_retrieve_context_without_memory_graph_unchanged(self, monkeypatch, tmp_path: Path):
        """When memory_graph is omitted, result should match plain retrieval."""
        monkeypatch.setattr(
            rc,
            "_keyword_retrieve",
            lambda req, root: [{"path": "a.md", "corpus": "specs", "score": 0.5, "snippet": "ok"}],
        )
        monkeypatch.setattr(rc._retrieval_cache, "clear", lambda: None)
        rc._retrieval_cache.clear()

        result = retrieve_context(
            RetrievalQuery(query="contracts", corpus=["specs"]),
            repo_root=tmp_path,
        )

        assert result["sources"][0]["path"] == "a.md"
        assert "graph_context" not in result

    def test_retrieve_context_with_memory_graph_adds_context(self, monkeypatch, tmp_path: Path):
        """Passing memory_graph augments result with similar task history."""
        monkeypatch.setattr(
            rc,
            "_keyword_retrieve",
            lambda req, root: [{"path": "a.md", "corpus": "specs", "score": 0.5, "snippet": "ok"}],
        )
        rc.get_retrieval_cache().clear()

        mg = MagicMock()
        mg.find_similar.return_value = [
            {"id": "node_1", "name": "refactor_code", "attrs": {"status": "completed"}},
            {"id": "node_2", "name": "update_docs", "attrs": {"status": "completed"}},
        ]

        result = retrieve_context(
            RetrievalQuery(query="refactor docs", corpus=["specs"]),
            repo_root=tmp_path,
            memory_graph=mg,
        )

        mg.find_similar.assert_called_once_with("refactor docs", max_results=3)
        assert result["graph_context"] == mg.find_similar.return_value
        assert len(result["sources"]) == 1

    def test_retrieve_context_graph_empty_similar_results(self, monkeypatch, tmp_path: Path):
        """When memory_graph returns no similar tasks, graph_context is empty list."""
        monkeypatch.setattr(
            rc,
            "_keyword_retrieve",
            lambda req, root: [],
        )
        rc.get_retrieval_cache().clear()

        mg = MagicMock()
        mg.find_similar.return_value = []

        result = retrieve_context(
            RetrievalQuery(query="xyz", corpus=["plans"]),
            repo_root=tmp_path,
            memory_graph=mg,
        )

        assert result["graph_context"] == []
        assert result["sources"] == []

    def test_retrieve_context_graph_uses_top_k(self, monkeypatch, tmp_path: Path):
        """The max_results passed to find_similar should match request.top_k."""
        monkeypatch.setattr(
            rc,
            "_keyword_retrieve",
            lambda req, root: [],
        )
        rc.get_retrieval_cache().clear()

        mg = MagicMock()
        mg.find_similar.return_value = []

        retrieve_context(
            RetrievalQuery(query="query", corpus=["history"], top_k=7),
            repo_root=tmp_path,
            memory_graph=mg,
        )

        mg.find_similar.assert_called_once_with("query", max_results=7)

    def test_retrieve_context_caching_includes_graph(self, monkeypatch, tmp_path: Path):
        """When use_cache=True and memory_graph present, cache stores/returns with graph_context."""
        monkeypatch.setattr(
            rc,
            "_keyword_retrieve",
            lambda req, root: [{"path": "b.md", "corpus": "plans", "score": 0.5, "snippet": "ok"}],
        )
        rc.get_retrieval_cache().clear()
        rc.reset_retrieval_metrics()

        mg = MagicMock()
        mg.find_similar.return_value = [
            {"id": "node_3", "name": "add_tests", "attrs": {"status": "completed"}},
        ]

        # First call (cache miss)
        result1 = retrieve_context(
            RetrievalQuery(query="caching test", corpus=["plans"]),
            repo_root=tmp_path,
            memory_graph=mg,
        )
        assert result1["graph_context"][0]["name"] == "add_tests"
        assert mg.find_similar.call_count == 1

        # Second call (cache hit)
        result2 = retrieve_context(
            RetrievalQuery(query="caching test", corpus=["plans"]),
            repo_root=tmp_path,
            memory_graph=mg,
        )
        # Should come from cache without re-invoking find_similar a second time
        assert result2["graph_context"][0]["name"] == "add_tests"
        assert mg.find_similar.call_count == 1  # still 1

    def test_retrieve_context_real_memory_graph_integration(self, tmp_path: Path):
        """Use a real MemoryGraph (backed by GraphStore) end-to-end with mocked retrieval."""
        from src.memory.graph_store import GraphStore

        store = GraphStore()
        mg = MemoryGraph(store)
        mg.record_task("auth_service", "builder", TaskOutcome.SUCCESS, {"runtime": 42})
        mg.record_task("payment_gateway", "builder", TaskOutcome.PARTIAL, {"runtime": 12})
        mg.record_task("user_profile", "critic", TaskOutcome.SUCCESS)

        monkeypatch = pytest.MonkeyPatch()
        with monkeypatch.context() as m:
            m.setattr(
                rc,
                "_keyword_retrieve",
                lambda req, root: [],
            )
            rc.get_retrieval_cache().clear()

            result = retrieve_context(
                RetrievalQuery(query="auth service", corpus=["history"], top_k=5),
                repo_root=tmp_path,
                memory_graph=mg,
            )

        assert len(result["graph_context"]) >= 1
        names = [t["name"] for t in result["graph_context"]]
        assert "auth_service" in names
        assert "payment_gateway" not in names  # doesn't match auth/service query
