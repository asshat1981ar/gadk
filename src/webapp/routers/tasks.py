"""Tasks and phase REST API router.

Provides task listing, detail view, phase history, and phase advance
endpoints backed by the shared StateManager and PhaseController.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from src.services.phase_controller import PhaseController
from src.services.sdlc_phase import Phase, PhaseHistoryEntry, WorkItem
from src.state import StateManager

router = APIRouter(prefix="/api", tags=["tasks"])

# Shared instances — lazy to avoid import-order issues at startup
_state_manager: StateManager | None = None
_phase_controller: PhaseController | None = None


def _sm() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def _pc() -> PhaseController:
    global _phase_controller
    if _phase_controller is None:
        _phase_controller = PhaseController(state_manager=_sm())
    return _phase_controller


def _serialize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe representation of a task dict."""
    return {
        "id": task.get("id"),
        "phase": task.get("phase"),
        "status": task.get("status"),
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "payload": task.get("payload", {}),
        "history": [
            {
                "from_phase": h.get("from_phase"),
                "to_phase": h.get("to_phase"),
                "at": h.get("at"),
                "reason": h.get("reason", ""),
                "evidence_refs": h.get("evidence_refs", []),
            }
            for h in task.get("history", [])
        ],
    }


@router.get("/tasks")
def list_tasks(status: str | None = None, phase: str | None = None):
    """List all tasks with optional filtering by status and/or phase."""
    sm = _sm()
    all_tasks = sm.get_all_tasks()
    result = [_serialize_task(t) for t in all_tasks.values()]
    if status is not None:
        result = [t for t in result if t.get("status") == status]
    if phase is not None:
        result = [t for t in result if t.get("phase") == phase]
    return {"tasks": result, "total": len(result)}


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    """Get a single task with full details, or 404 if not found."""
    sm = _sm()
    task = sm.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return _serialize_task(task)


@router.get("/tasks/{task_id}/history")
def get_task_history(task_id: str):
    """Get the phase-transition history for a task.

    Combines the ``history`` list embedded in the task dict (for
    in-memory transitions) with the events.jsonl audit log for
    durable records.
    """
    sm = _sm()
    task = sm.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    # In-memory history from task dict
    in_memory = [
        {
            "from_phase": h.get("from_phase"),
            "to_phase": h.get("to_phase"),
            "at": h.get("at"),
            "reason": h.get("reason", ""),
            "evidence_refs": h.get("evidence_refs", []),
        }
        for h in task.get("history", [])
    ]

    # Durable audit log from events.jsonl
    events = sm.get_task_history(task_id)
    audit_entries = [
        {
            "from_phase": e.get("from_phase"),
            "to_phase": e.get("to_phase"),
            "at": e.get("timestamp"),
            "reason": e.get("reason", ""),
            "source": "events.jsonl",
        }
        for e in events
        if e.get("action") in ("phase.transition", "phase.transition.blocked")
    ]

    return {
        "task_id": task_id,
        "in_memory": in_memory,
        "audit_log": audit_entries,
    }


@router.get("/phase/status/{task_id}")
def get_phase_status(task_id: str):
    """Get current phase and full transition history for a task."""
    sm = _sm()
    task = sm.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    current_phase = task.get("phase", "PLAN")

    # Build history from task dict
    history = [
        {
            "from_phase": h.get("from_phase"),
            "to_phase": h.get("to_phase"),
            "at": h.get("at"),
            "reason": h.get("reason", ""),
        }
        for h in task.get("history", [])
    ]

    return {
        "task_id": task_id,
        "current_phase": current_phase,
        "history": history,
    }


@router.post("/phase/advance")
def advance_phase(task_id: str, target_phase: str, reason: str = ""):
    """Advance a task to the next phase (wraps PhaseController.advance).

    Returns the advance report including whether the transition succeeded,
    any gate results, and the updated task state.
    """
    sm = _sm()
    task = sm.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    # Parse target phase
    try:
        target = Phase[target_phase.upper()]
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown phase '{target_phase}'. Valid phases: {[p.value for p in Phase]}",
        )

    # Reconstruct a WorkItem from stored task data
    work_item = WorkItem(
        id=task_id,
        phase=Phase(task.get("phase", "PLAN")),
        payload=task.get("payload", {}),
        history=[
            PhaseHistoryEntry(
                from_phase=Phase(h.get("from_phase", "PLAN")) if h.get("from_phase") else None,
                to_phase=Phase(h.get("to_phase", "PLAN")),
                at=datetime.fromisoformat(h["at"]) if h.get("at") else datetime.now(UTC),
                reason=h.get("reason", ""),
                evidence_refs=h.get("evidence_refs", []),
            )
            for h in task.get("history", [])
        ],
    )

    pc = _pc()
    report = pc.advance(work_item, target, reason=reason)

    # Persist updated task back to StateManager
    updated_task = {
        **task,
        "phase": report.to_phase.value,
        "updated_at": datetime.now(UTC).isoformat(),
        "history": [
            {
                "from_phase": h.from_phase.value if h.from_phase else None,
                "to_phase": h.to_phase.value,
                "at": h.at.isoformat(),
                "reason": h.reason,
                "evidence_refs": h.evidence_refs,
            }
            for h in work_item.history
        ],
    }
    sm.set_task(task_id, updated_task)

    return {
        "task_id": task_id,
        "from_phase": report.from_phase.value,
        "to_phase": report.to_phase.value,
        "advanced": report.advanced,
        "reason": report.reason,
        "gates": [
            {
                "gate": g.gate,
                "passed": g.passed,
                "blocking": g.blocking,
                "message": g.message,
            }
            for g in report.gates
        ],
    }