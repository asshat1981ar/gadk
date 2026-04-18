"""Tests for the external SDLC MCP client — dormant-by-default behavior."""

from __future__ import annotations

import pytest

from src.config import Config
from src.mcp import sdlc_client


@pytest.mark.asyncio
async def test_create_adr_skipped_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "SDLC_MCP_ENABLED", False)
    out = await sdlc_client.create_adr(
        task_id="t1",
        title="T",
        context="C",
        decision="D",
        consequences=["x"],
    )
    assert out["status"] == "skipped"


@pytest.mark.asyncio
async def test_commit_phase_skipped_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "SDLC_MCP_ENABLED", False)
    out = await sdlc_client.commit_phase(
        task_id="t1", from_phase="PLAN", to_phase="ARCHITECT", reason=""
    )
    assert out["status"] == "skipped"


@pytest.mark.asyncio
async def test_submit_quality_gate_routes_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "SDLC_MCP_ENABLED", True)

    import asyncio as _asyncio

    async def _slow_tool(**kwargs):
        await _asyncio.sleep(60)

    # Monkeypatch _invoke path: inject a fake smithery_bridge
    import sys

    class _FakeModule:
        call_smithery_tool = staticmethod(_slow_tool)

    sys.modules["src.tools.smithery_bridge"] = _FakeModule  # type: ignore[assignment]
    # Shrink the timeout for testing
    orig_wait = _asyncio.wait_for

    async def _fast_wait(coro, timeout):
        return await orig_wait(coro, timeout=0.01)

    monkeypatch.setattr(sdlc_client.asyncio, "wait_for", _fast_wait)

    out = await sdlc_client.submit_quality_gate(pr_number=1, gates=[])
    assert out["status"] == "timeout"
    sys.modules.pop("src.tools.smithery_bridge", None)


def test_submit_gate_decision_skipped_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "SDLC_MCP_ENABLED", False)
    out = sdlc_client.submit_gate_decision(task_id="t", verdict={"ready": True})
    assert out["status"] == "skipped"


@pytest.mark.asyncio
async def test_submit_gate_decision_tracks_pending_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """submit_gate_decision must add the created task to _pending_tasks
    and remove it automatically via done_callback when it completes.
    """
    import asyncio as _asyncio

    monkeypatch.setattr(sdlc_client.Config, "SDLC_MCP_ENABLED", True)

    # Inject a fast-completing fake _invoke so the task finishes quickly.
    async def _fast_invoke(tool_name: str, payload: dict) -> dict:
        return {"status": "ok", "tool": tool_name}

    monkeypatch.setattr(sdlc_client, "_invoke", _fast_invoke)

    # Clear any leftover tasks from previous tests.
    sdlc_client._pending_tasks.clear()

    out = sdlc_client.submit_gate_decision(task_id="t-track", verdict={"ready": True})
    assert out["status"] == "scheduled"

    # The task must be tracked immediately after creation.
    assert len(sdlc_client._pending_tasks) == 1

    # Allow the event loop to run until the task completes.
    await _asyncio.sleep(0.05)

    # After completion the done_callback should have removed it.
    assert len(sdlc_client._pending_tasks) == 0, (
        "Task was not removed from _pending_tasks after completion."
    )
