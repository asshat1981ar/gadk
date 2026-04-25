# tests/services/test_dbos_recovery.py
"""Tests for DBOSRecoveryManager."""
from __future__ import annotations

from src.services.dbos_recovery import DBOSRecoveryManager, WorkflowStatus


def test_manager_defaults_to_empty_when_disabled():
    """When DBOS is not enabled, all methods return safe empty values."""
    manager = DBOSRecoveryManager()

    # list_interrupted_workflows returns empty list
    assert manager.list_interrupted_workflows() == []

    # resume_workflow returns False when disabled
    result = manager.resume_workflow("wf-123")
    assert result == {"resumed": False, "error": "DBOS not enabled"}

    # get_workflow_history returns empty list
    assert manager.get_workflow_history("wf-123") == []

    # cancel_workflow returns False when disabled
    result = manager.cancel_workflow("wf-123")
    assert result == {"cancelled": False, "error": "DBOS not enabled"}


def test_manager_has_required_attributes():
    """DBOSRecoveryManager exposes expected public interface."""
    manager = DBOSRecoveryManager()
    assert hasattr(manager, "list_interrupted_workflows")
    assert hasattr(manager, "resume_workflow")
    assert hasattr(manager, "get_workflow_history")
    assert hasattr(manager, "cancel_workflow")
    # Internal _enabled flag is also present
    assert hasattr(manager, "_enabled")


def test_workflow_status_dataclass():
    """WorkflowStatus holds expected fields."""
    ws = WorkflowStatus(
        workflow_id="wf-1",
        name="TestWorkflow",
        status="PENDING",
        created_at="2025-01-01T00:00:00",
        last_updated="2025-01-01T00:01:00",
        step_count=3,
        error=None,
    )
    assert ws.workflow_id == "wf-1"
    assert ws.name == "TestWorkflow"
    assert ws.status == "PENDING"
    assert ws.step_count == 3
    assert ws.error is None