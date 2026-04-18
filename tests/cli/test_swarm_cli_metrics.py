"""Tests for the embed-quota block in swarm_cli metrics."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cli import swarm_cli
from src.services.embed_quota import EmbedQuota
from src.state import StateManager


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    rc = swarm_cli.main(list(argv))
    out = capsys.readouterr().out
    return rc, out


def test_metrics_shows_embed_quota_section_empty(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    state = tmp_path / "state.json"
    events = tmp_path / "events.jsonl"
    rc, out = _run(capsys, "metrics", "--state-file", str(state), "--events-file", str(events))
    assert rc == 0
    assert "=== Embed Quota (today) ===" in out
    assert "Used:" in out
    assert "0 tokens" in out  # no usage yet


def test_metrics_reflects_prior_quota_spend(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    state = tmp_path / "state.json"
    events = tmp_path / "events.jsonl"
    # Seed today's spend at 1234 tokens.
    sm = StateManager(storage_type="json", filename=str(state), event_filename=str(events))
    EmbedQuota(sm, daily_cap=10_000).record(1234)

    rc, out = _run(capsys, "metrics", "--state-file", str(state), "--events-file", str(events))
    assert rc == 0
    assert "1234 tokens" in out
    # Percentage line should reflect some non-zero usage.
    assert "% used" in out
