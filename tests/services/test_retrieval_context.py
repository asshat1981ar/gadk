from __future__ import annotations

import threading
from pathlib import Path

import pytest

import src.services.retrieval_context as rc
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


class TestDocHashesLock:
    """Verify that concurrent _sync_corpus_to_backend calls don't trigger duplicate embeds."""

    def test_concurrent_retrieves_no_duplicate_embed(self, tmp_path: Path):
        """Two threads calling _sync_corpus_to_backend simultaneously for the
        same doc must embed it exactly once — the _doc_hashes_lock with
        atomic check-and-pre-mark prevents both threads from seeing a cache
        miss and both issuing an upsert.
        """
        # Write a single spec file that both threads will try to embed.
        spec_file = tmp_path / "docs" / "superpowers" / "specs" / "spec.md"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text("alpha beta gamma", encoding="utf-8")

        upsert_calls: list[str] = []
        upsert_lock = threading.Lock()
        # A barrier inside upsert lets the second thread arrive and see the
        # (already pre-marked) cache entry before the first thread finishes.
        upsert_entered = threading.Event()
        upsert_proceed = threading.Event()

        class _TrackingBackend:
            name = "tracking"

            def upsert(self, *, doc_id: str, text: str, metadata: dict) -> None:
                with upsert_lock:
                    upsert_calls.append(doc_id)
                # Signal the second thread that we're inside upsert, then
                # wait briefly so it has time to check the hash cache.
                upsert_entered.set()
                upsert_proceed.wait(timeout=2)

            def query(self, query: str, top_k: int = 3):
                return []

            def known_doc_ids(self, **kwargs):
                return set()

            def delete(self, doc_id: str) -> None:
                pass

        # Clear module-level cache before the test.
        with rc._doc_hashes_lock:
            rc._doc_hashes.clear()

        backend = _TrackingBackend()
        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def _run():
            try:
                barrier.wait()  # both threads start simultaneously
                rc._sync_corpus_to_backend(backend, tmp_path, ["specs"])
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_run) for _ in range(2)]
        for t in threads:
            t.start()

        # Once the first upsert has started, let both threads proceed.
        upsert_entered.wait(timeout=5)
        upsert_proceed.set()

        for t in threads:
            t.join(timeout=10)

        # Restore state
        with rc._doc_hashes_lock:
            rc._doc_hashes.clear()

        assert not errors, f"Threads raised exceptions: {errors}"
        # The doc should have been upserted exactly once despite two concurrent calls.
        assert len(upsert_calls) == 1, (
            f"Expected 1 upsert call, got {len(upsert_calls)}. "
            "Duplicate embed detected — _doc_hashes_lock may not be working."
        )
