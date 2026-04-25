# src/services/dbos_recovery.py
"""DBOS workflow recovery manager for resuming interrupted workflows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.config import Config


@dataclass
class WorkflowStatus:
    """Status record for a DBOS workflow."""

    workflow_id: str
    name: str
    status: str
    created_at: datetime | None
    last_updated: datetime | None = None
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
        result: list[WorkflowStatus] = []
        for wf in workflows:
            created_ts = getattr(wf, "created_at", None)
            updated_ts = getattr(wf, "last_updated", None)
            result.append(
                WorkflowStatus(
                    workflow_id=wf.workflow_id,
                    name=wf.name,
                    status=wf.status,
                    created_at=datetime.fromtimestamp(int(created_ts)) if created_ts else None,
                    last_updated=datetime.fromtimestamp(int(updated_ts)) if updated_ts else None,
                    step_count=getattr(wf, "step_count", 0),
                    error=getattr(wf, "error", None),
                )
            )
        return result

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

        # Handle DBOS API differences - get_workflow_steps may not exist
        if hasattr(dbos.DBOS, "get_workflow_steps"):
            steps = dbos.DBOS.get_workflow_steps(workflow_id)
        else:
            steps = getattr(dbos.DBOS, "list_workflow_steps", lambda wid: [])(
                workflow_id
            )
        return [
            {
                "step_index": getattr(s, "step_index", i),
                "name": getattr(s, "name", ""),
                "status": getattr(s, "status", ""),
                "output": getattr(s, "output", None),
            }
            for i, s in enumerate(steps or [])
        ]

    def cancel_workflow(self, workflow_id: str) -> dict:
        """Cancel a running or pending workflow."""
        if not self._enabled:
            return {"cancelled": False, "error": "DBOS not enabled"}
        import dbos

        dbos.DBOS.cancel_workflow(workflow_id)
        return {"cancelled": True}
