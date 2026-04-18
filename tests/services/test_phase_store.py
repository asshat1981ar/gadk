"""Tests for phase_store — WorkItem persistence atop StateManager."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.phase_store import ensure_work_item, load_work_item, save_work_item
from src.services.sdlc_phase import Phase, WorkItem
from src.state import StateManager


@pytest.fixture
def sm(tmp_path: Path) -> StateManager:
    return StateManager(
        storage_type="json",
        filename=str(tmp_path / "state.json"),
        event_filename=str(tmp_path / "events.jsonl"),
    )


def test_load_missing_returns_none(sm: StateManager) -> None:
    assert load_work_item(sm, "nope") is None


def test_ensure_creates_with_default_phase(sm: StateManager) -> None:
    item = ensure_work_item(sm, "task-1")
    assert item.id == "task-1"
    assert item.phase is Phase.PLAN
    # Round-trip: stored and loadable
    loaded = load_work_item(sm, "task-1")
    assert loaded is not None
    assert loaded.phase is Phase.PLAN


def test_save_roundtrip_preserves_history(sm: StateManager) -> None:
    item = WorkItem(id="task-1", phase=Phase.ARCHITECT, payload={"k": "v"})
    item.record(Phase.IMPLEMENT, reason="ready", evidence_refs=["lint"])
    item.phase = Phase.IMPLEMENT
    save_work_item(sm, item)

    loaded = load_work_item(sm, "task-1")
    assert loaded is not None
    assert loaded.phase is Phase.IMPLEMENT
    assert loaded.payload == {"k": "v"}
    assert len(loaded.history) == 1
    assert loaded.history[0].to_phase is Phase.IMPLEMENT
    assert loaded.history[0].evidence_refs == ["lint"]


def test_save_preserves_other_task_fields(sm: StateManager) -> None:
    sm.set_task("task-1", {"status": "IN_PROGRESS", "priority": 1, "source": "Ideator"})
    item = ensure_work_item(sm, "task-1", phase=Phase.IMPLEMENT)
    assert item.phase is Phase.IMPLEMENT
    task = sm.get_task("task-1")
    assert task is not None
    assert task["status"] == "IN_PROGRESS"
    assert task["priority"] == 1
    assert task["source"] == "Ideator"
    assert task["phase"] == "IMPLEMENT"
