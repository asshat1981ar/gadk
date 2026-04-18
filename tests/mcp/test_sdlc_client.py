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
    import sys

    async def _slow_tool(**kwargs):
        await _asyncio.sleep(60)

    # Monkeypatch _invoke path: inject a fake smithery_bridge
    class _FakeModule:
        call_smithery_tool = staticmethod(_slow_tool)

    monkeypatch.setitem(sys.modules, "src.tools.smithery_bridge", _FakeModule)  # type: ignore[arg-type]
    # Shrink the timeout for testing
    orig_wait = _asyncio.wait_for

    async def _fast_wait(coro, timeout):
        return await orig_wait(coro, timeout=0.01)

    monkeypatch.setattr(sdlc_client.asyncio, "wait_for", _fast_wait)

    out = await sdlc_client.submit_quality_gate(pr_number=1, gates=[])
    assert out["status"] == "timeout"


def test_submit_gate_decision_skipped_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "SDLC_MCP_ENABLED", False)
    out = sdlc_client.submit_gate_decision(task_id="t", verdict={"ready": True})
    assert out["status"] == "skipped"
