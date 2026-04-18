from __future__ import annotations

from pathlib import Path

import pytest

from src.services.retrieval_context import (
    PLANNING_RETRIEVAL_CAPABILITY,
    RetrievalQuery,
    retrieve_context,
    retrieve_planning_context,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestRetrievalContext:
    def test_retrieve_context_filters_to_first_corpus(self, tmp_path: Path):
        _write(
            tmp_path / "docs/superpowers/specs/spec-a.md",
            "Planner contracts and delegation rules live in the approved spec.",
        )
        _write(
            tmp_path / "docs/superpowers/plans/plan-a.md",
            "The implementation plan tracks planner tasks and rollout order.",
        )
        _write(
            tmp_path / ".swarm_history",
            "# 2026-04-18\n+prompt inspect prior planner work\n",
        )

        result = retrieve_context(
            RetrievalQuery(query="planner contracts", corpus=["specs", "plans"]),
            repo_root=tmp_path,
        )

        assert set(result["corpus"]) == {"specs", "plans"}
        assert result["sources"]
        assert {source["corpus"] for source in result["sources"]}.issubset({"specs", "plans"})

    def test_retrieve_context_supports_history_corpus(self, tmp_path: Path):
        _write(
            tmp_path / "docs/superpowers/specs/spec-a.md",
            "Delegation contracts are documented here.",
        )
        _write(
            tmp_path / ".swarm_history",
            "# 2026-04-18\n+prompt planner history should remain searchable\n",
        )

        result = retrieve_context(
            RetrievalQuery(query="history searchable", corpus=["history"], top_k=1),
            repo_root=tmp_path,
        )

        assert result["corpus"] == ["history"]
        assert result["sources"][0]["path"] == ".swarm_history"
        assert result["sources"][0]["corpus"] == "history"

    def test_retrieval_query_rejects_unapproved_corpus(self):
        with pytest.raises(ValueError, match="Unsupported retrieval corpus"):
            RetrievalQuery(query="planner contracts", corpus=["issues"])

    def test_retrieve_context_empty_corpus_returns_empty(self, tmp_path: Path):
        """An empty tmp_path (no corpus files) must return sources=[] without errors."""
        result = retrieve_context(
            RetrievalQuery(query="anything", corpus=["specs", "plans", "history"]),
            repo_root=tmp_path,
        )

        assert result["sources"] == []
        assert set(result["corpus"]) == {"specs", "plans", "history"}

    @pytest.mark.asyncio
    async def test_retrieve_planning_context_uses_capability_layer(self, monkeypatch):
        captured: dict[str, object] = {}

        async def fake_execute_capability(name: str, **arguments: object) -> dict[str, object]:
            captured["name"] = name
            captured["arguments"] = arguments
            return {"status": "success", "payload": {"sources": []}}

        monkeypatch.setattr(
            "src.tools.dispatcher.execute_capability",
            fake_execute_capability,
        )

        result = await retrieve_planning_context("planner contracts", corpus=["specs"], top_k=2)

        assert captured == {
            "name": PLANNING_RETRIEVAL_CAPABILITY,
            "arguments": {
                "query": "planner contracts",
                "corpus": ["specs"],
                "top_k": 2,
            },
        }
        assert result == {"status": "success", "payload": {"sources": []}}
