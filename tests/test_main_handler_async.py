"""Regression test for the Gemini-flagged blocking in the retrieval capability handler.

Before this fix, `_planning_retrieval_handler` invoked `retrieve_context`
(and therefore `litellm.embedding`) synchronously from the event loop,
which meant a vector-retrieve could stall the swarm's async loop for
seconds at a time. The fix dispatches the sync `retrieve_context` call
through `asyncio.to_thread`; this test proves that a blocking
`retrieve_context` no longer starves concurrent tasks.
"""

from __future__ import annotations

import asyncio
import time

import pytest

# `src.main` imports `google.adk.runners` at module scope; skip the whole
# test module when ADK isn't installed (local env without heavy deps).
pytest.importorskip("google.adk")

from src.capabilities.contracts import CapabilityRequest


@pytest.mark.asyncio
async def test_planning_retrieval_handler_yields_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `retrieve_context` blocks for 150ms, a concurrent async task
    must still run in the meantime. Without the `asyncio.to_thread`
    wrapper the handler would hog the loop and the other task couldn't
    make progress until it returned."""
    import src.main as main_mod

    def _slow_retrieve(query):
        time.sleep(0.15)  # simulates the blocking litellm.embedding call
        return {"query": query.query, "corpus": query.corpus, "sources": []}

    monkeypatch.setattr(main_mod, "retrieve_context", _slow_retrieve)

    request = CapabilityRequest(
        name="planning.retrieve_context",
        arguments={"query": "phase gate", "corpus": ["specs"], "top_k": 3},
    )

    # Schedule the handler and a concurrent task that records its wake time.
    handler_start = asyncio.get_event_loop().time()
    concurrent_wake = asyncio.get_event_loop().time()  # overwritten below

    async def _concurrent_task():
        nonlocal concurrent_wake
        # Multiple small sleeps so if the loop is hogged we see the delay.
        for _ in range(10):
            await asyncio.sleep(0.01)
        concurrent_wake = asyncio.get_event_loop().time()

    handler_task = asyncio.create_task(main_mod._planning_retrieval_handler(request))
    concurrent_task = asyncio.create_task(_concurrent_task())

    result = await handler_task
    await concurrent_task

    # The concurrent task's ~100ms of cumulative sleeps must complete while
    # the handler's 150ms blocking sleep is still in flight — i.e., the
    # concurrent task finished BEFORE the handler did. If the handler had
    # blocked the loop, the concurrent task couldn't wake until the handler
    # returned, putting `concurrent_wake` AFTER `handler_start + 150ms`.
    elapsed_concurrent = concurrent_wake - handler_start
    assert elapsed_concurrent < 0.14, (
        f"concurrent task was starved; completed after {elapsed_concurrent:.3f}s. "
        "Handler must dispatch retrieve_context through asyncio.to_thread."
    )
    assert result == {"query": "phase gate", "corpus": ["specs"], "sources": []}
