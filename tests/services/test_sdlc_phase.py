"""Tests for the SDLC phase model and transition rules."""

from __future__ import annotations

import pytest

from src.services.sdlc_phase import (
    ALLOWED_TRANSITIONS,
    PHASE_ORDER,
    Phase,
    PhaseHistoryEntry,
    WorkItem,
    can_advance,
    next_phase,
)


def test_phase_order_is_canonical() -> None:
    assert PHASE_ORDER[0] is Phase.PLAN
    assert PHASE_ORDER[-1] is Phase.OPERATE
    assert len(set(PHASE_ORDER)) == len(PHASE_ORDER)


def test_next_phase_walks_forward() -> None:
    assert next_phase(Phase.PLAN) is Phase.ARCHITECT
    assert next_phase(Phase.REVIEW) is Phase.GOVERN
    assert next_phase(Phase.OPERATE) is None


def test_can_advance_allows_forward_edge() -> None:
    assert can_advance(Phase.PLAN, Phase.ARCHITECT)
    assert can_advance(Phase.REVIEW, Phase.GOVERN)


def test_can_advance_allows_review_rework_edge() -> None:
    assert can_advance(Phase.REVIEW, Phase.IMPLEMENT)


def test_can_advance_rejects_skip() -> None:
    assert not can_advance(Phase.PLAN, Phase.REVIEW)
    assert not can_advance(Phase.PLAN, Phase.IMPLEMENT)


def test_can_advance_rejects_backwards_except_rework() -> None:
    assert not can_advance(Phase.ARCHITECT, Phase.PLAN)
    assert not can_advance(Phase.GOVERN, Phase.IMPLEMENT)


def test_operate_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS[Phase.OPERATE] == frozenset()


def test_work_item_defaults() -> None:
    item = WorkItem(id="task-1")
    assert item.phase is Phase.PLAN
    assert item.payload == {}
    assert item.history == []


def test_work_item_record_appends_history() -> None:
    item = WorkItem(id="task-1")
    item.record(Phase.ARCHITECT, reason="ready", evidence_refs=["lint"])
    assert len(item.history) == 1
    entry = item.history[0]
    assert isinstance(entry, PhaseHistoryEntry)
    assert entry.from_phase is Phase.PLAN
    assert entry.to_phase is Phase.ARCHITECT
    assert entry.reason == "ready"
    assert entry.evidence_refs == ["lint"]


def test_work_item_id_min_length_enforced() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WorkItem(id="")
