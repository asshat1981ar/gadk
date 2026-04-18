"""Tests for the Governor agent's pure tool functions."""

from __future__ import annotations

import pytest

from src.agents.governor import (
    GovernanceVerdict,
    register_external_gate,
    run_governance_review,
)
from src.config import Config


@pytest.mark.asyncio
async def test_governance_review_passes_with_substantial_body_and_no_cost() -> None:
    body = "Release note: migrate autonomous_sdlc task IDs to regex-validated slugs; no behaviour change beyond rejecting unsafe titles."
    verdict = await run_governance_review(
        task_id="task-1",
        payload={"body": body, "cost_usd": 0.0},
    )
    assert verdict["ready"] is True
    assert verdict["concerns"] == []
    assert verdict["evidence"]["content_guard"]["low_value"] is False
    assert verdict["evidence"]["finops"]["status"] == "OK"


@pytest.mark.asyncio
async def test_governance_review_flags_thin_body() -> None:
    verdict = await run_governance_review(
        task_id="task-2",
        payload={"body": "ok", "cost_usd": 0.0},
        min_body_bytes=120,
    )
    assert verdict["ready"] is False
    assert any("thin" in c or "leakage" in c for c in verdict["concerns"])


@pytest.mark.asyncio
async def test_governance_review_propagates_reviewer_retry() -> None:
    def _retry_reviewer(payload: dict) -> dict:
        return {"status": "retry", "summary": "needs rework"}

    verdict = await run_governance_review(
        task_id="task-3",
        payload={
            "body": "This release note has more than one hundred and twenty bytes of substantive content. It discusses the specific changes, the reasoning behind them, and the downstream impact for operators.",
            "cost_usd": 0.0,
        },
        reviewer=_retry_reviewer,
    )
    assert verdict["ready"] is False
    assert any("second-pass" in c for c in verdict["concerns"])
    assert verdict["evidence"]["second_pass"]["status"] == "retry"


@pytest.mark.asyncio
async def test_governance_review_pass_with_reviewer_pass() -> None:
    def _pass_reviewer(payload: dict) -> dict:
        return {"status": "pass", "summary": "lgtm"}

    verdict = await run_governance_review(
        task_id="task-4",
        payload={
            "body": "This release note has more than one hundred and twenty bytes of substantive content. It discusses the specific changes, the reasoning behind them, and the downstream impact for operators.",
            "cost_usd": 0.0,
        },
        reviewer=_pass_reviewer,
    )
    assert verdict["ready"] is True


def test_register_external_gate_skipped_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "SDLC_MCP_ENABLED", False)
    out = register_external_gate(task_id="t", verdict={"ready": True})
    assert out["status"] == "sdlc.gate.skipped"
    assert out["task_id"] == "t"


def test_register_external_gate_skipped_when_client_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "SDLC_MCP_ENABLED", True)
    import sys as _sys

    # Ensure the client module is not resolvable.
    _sys.modules.pop("src.mcp.sdlc_client", None)
    # Make the import fail cleanly.
    orig_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def _no_sdlc_client(name, *args, **kwargs):
        if name == "src.mcp.sdlc_client":
            raise ImportError("simulated absence")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _no_sdlc_client)
    out = register_external_gate(task_id="t", verdict={"ready": True})
    assert out["status"] == "sdlc.gate.skipped"


def test_governance_verdict_dataclass_round_trip() -> None:
    v = GovernanceVerdict(task_id="t", ready=True)
    assert v.to_dict() == {"task_id": "t", "ready": True, "evidence": {}, "concerns": []}
