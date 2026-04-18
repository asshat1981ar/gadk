"""Persistence shim for :class:`WorkItem` on top of :class:`StateManager`.

The phase controller is pure in-memory; the CLI (and future autonomous
flows) need work items to survive restarts. This module keeps that
persistence localized so the controller and its tests stay unchanged.

Encoding: work items are stored under their normal ``task_id`` key in
``state.json``; we namespace our fields under ``_work_item`` so we don't
collide with pre-existing task dicts used by the autonomous SDLC engine.
"""

from __future__ import annotations

from src.observability.logger import get_logger
from src.services.sdlc_phase import Phase, PhaseHistoryEntry, WorkItem
from src.state import StateManager

logger = get_logger("phase_store")

_WORK_ITEM_KEY = "_work_item"


def _serialize(item: WorkItem) -> dict:
    return {
        "phase": item.phase.value,
        "payload": item.payload,
        "history": [entry.model_dump(mode="json") for entry in item.history],
    }


def _deserialize(task_id: str, raw: dict) -> WorkItem:
    history_raw = raw.get("history", [])
    history = [PhaseHistoryEntry.model_validate(h) for h in history_raw]
    return WorkItem(
        id=task_id,
        phase=Phase(raw.get("phase", Phase.PLAN.value)),
        payload=dict(raw.get("payload", {})),
        history=history,
    )


def load_work_item(sm: StateManager, task_id: str) -> WorkItem | None:
    """Rehydrate a :class:`WorkItem` from the state file, if present."""
    task = sm.get_task(task_id)
    if task is None:
        return None
    raw = task.get(_WORK_ITEM_KEY)
    if not raw:
        return None
    return _deserialize(task_id, raw)


def save_work_item(sm: StateManager, item: WorkItem, *, agent: str = "PhaseController") -> None:
    """Persist a :class:`WorkItem` back into the task's dict.

    Preserves other task fields (status, priority, etc.) so the autonomous
    SDLC engine can continue to reason about the same row.
    """
    existing = sm.get_task(item.id) or {}
    existing[_WORK_ITEM_KEY] = _serialize(item)
    # Mirror the phase at the task root so CLI filters (`tasks --status ...`)
    # and downstream tooling can see progress without parsing _work_item.
    existing["phase"] = item.phase.value
    sm.set_task(item.id, existing, agent=agent)


def ensure_work_item(sm: StateManager, task_id: str, *, phase: Phase = Phase.PLAN) -> WorkItem:
    """Return the stored :class:`WorkItem` or create a new one if missing."""
    item = load_work_item(sm, task_id)
    if item is not None:
        return item
    item = WorkItem(id=task_id, phase=phase)
    save_work_item(sm, item, agent="cli")
    logger.info("phase_store: created work_item task=%s phase=%s", task_id, phase.value)
    return item


__all__ = ["ensure_work_item", "load_work_item", "save_work_item"]
