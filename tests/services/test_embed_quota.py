"""Tests for the daily embedding-token quota tracker."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from src.services.embed_quota import EmbedQuota, EmbedQuotaExceeded, estimate_tokens
from src.state import StateManager


@pytest.fixture
def sm(tmp_path: Path) -> StateManager:
    return StateManager(
        storage_type="json",
        filename=str(tmp_path / "state.json"),
        event_filename=str(tmp_path / "events.jsonl"),
    )


def test_empty_quota_starts_at_zero(sm: StateManager) -> None:
    q = EmbedQuota(sm, daily_cap=1000)
    assert q.used_today() == 0
    assert q.remaining_today() == 1000


def test_record_increments_and_persists(sm: StateManager, tmp_path: Path) -> None:
    q = EmbedQuota(sm, daily_cap=1000)
    q.record(250)
    assert q.used_today() == 250

    # Rehydrate a fresh StateManager from disk to verify persistence.
    sm2 = StateManager(
        storage_type="json",
        filename=str(tmp_path / "state.json"),
        event_filename=str(tmp_path / "events.jsonl"),
    )
    q2 = EmbedQuota(sm2, daily_cap=1000)
    assert q2.used_today() == 250


def test_check_blocks_at_cap(sm: StateManager) -> None:
    q = EmbedQuota(sm, daily_cap=100)
    q.record(90)
    q.check(5)  # fits
    with pytest.raises(EmbedQuotaExceeded):
        q.check(20)


def test_check_is_noop_for_nonpositive_requests(sm: StateManager) -> None:
    q = EmbedQuota(sm, daily_cap=10)
    q.record(10)
    q.check(0)
    q.check(-5)


def test_prune_drops_stale_entries(sm: StateManager) -> None:
    # Seed the state file with some old + fresh entries.
    stale = (date.today() - timedelta(days=30)).isoformat()
    recent = (date.today() - timedelta(days=2)).isoformat()
    sm.data["embed_quota"] = {stale: 999, recent: 50}
    q = EmbedQuota(sm, daily_cap=1000)
    # Recording triggers save which prunes.
    q.record(10)
    remaining_keys = set(sm.data["embed_quota"].keys())
    assert stale not in remaining_keys
    assert recent in remaining_keys


def test_estimate_tokens_rough_length_heuristic() -> None:
    # 1 token per ~4 chars, floor of 1 per non-empty text.
    assert estimate_tokens([""]) == 1
    assert estimate_tokens(["abcd"]) == 1
    assert estimate_tokens(["a" * 100]) == 25
    assert estimate_tokens(["aa", "bbbb"]) == 2
    assert estimate_tokens([]) == 0
    assert estimate_tokens(None) == 0
