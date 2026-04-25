# src/services/dbos_recovery.py
"""DBOS workflow recovery manager for resuming interrupted workflows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from src.config import Config


@dataclass
class WorkflowStatus:
    """Status record for a DBOS workflow."""

    workflow_id: str
    name: str
    status: Literal["PENDING", "COMPLETED", "FAILED"]
    created_at: datetime
    last_updated: datetime
    step_count: int = 0
    error: str | None = None


class DBOSRecoveryManager:
    """Manage DBOS workflow recovery and resumption.

    When DBOS is disabled, all methods return safe empty/False values.
    When enabled, delegates to the dbos.DBOS runtime.
    """

    def __init__(self) -> None:
        self._enabled = Config.DBOS_ENABLED

    def list_interrupted_workflows(self) -> list[WorkflowStatus]:
        """Return workflows with PENDING status that may need resumption."""
        if not self._enabled:
            return []
        import dbos

        workflows = dbos.DBOS.list_workflows(status="PENDING")
        return [
            WorkflowStatus(
                workflow_id=wf.workflow_id,
                name=wf.name,
                status=wf.status,
                created_at=wf.created_at,
                last_updated=wf.last_updated,
                step_count=getattr(wf, "step_count", 0),
                error=getattr(wf, "error", None),
            )
            for wf in workflows
        ]

    def resume_workflow(self, workflow_id: str) -> dict:
        """Attempt to resume an interrupted workflow by ID."""
        if not self._enabled:
            return {"resumed": False, "error": "DBOS not enabled"}
        import dbos

        result = dbos.DBOS.resume_workflow(workflow_id)
        return {"resumed": True, "result": result}

    def get_workflow_history(self, workflow_id: str) -> list[dict]:
        """Return the step history for a given workflow."""
        if not self._enabled:
            return []
        import dbos

        steps = dbos.DBOS.get_workflow_steps(workflow_id)
        return [
            {
                "step_index": getattr(s, "step_index", i),
                "name": getattr(s, "name", ""),
                "status": getattr(s, "status", ""),
                "output": getattr(s, "output", None),
            }
            for i, s in enumerate(steps)
        ]

    def cancel_workflow(self, workflow_id: str) -> dict:
        """Cancel a running or pending workflow."""
        if not self._enabled:
            return {"cancelled": False, "error": "DBOS not enabled"}
        import dbos

        dbos.DBOS.cancel_workflow(workflow_id)
        return {"cancelled": True}