# tests/services/test_dbos_phase_workflow.py
from __future__ import annotations

import os

import pytest
from src.services.sdlc_phase import Phase, WorkItem
from src.services.dbos_phase_workflow import transition_workflow


def test_workflow_runs_single_transition():
    """A PLAN→ARCHITECT transition completes and returns the updated item."""
    result = transition_workflow(
        item_id="task-1",
        target_phase=Phase.ARCHITECT,
        current_phase=Phase.PLAN,
    )
    assert result["to_phase"] == Phase.ARCHITECT.value
    assert result["advanced"] is True


def test_workflow_result_structure():
    """Result always has expected keys."""
    result = transition_workflow(
        item_id="task-2",
        target_phase=Phase.IMPLEMENT,
        current_phase=Phase.ARCHITECT,
    )
    assert set(result.keys()) == {"item_id", "from_phase", "to_phase", "advanced", "reason", "gates"}


def test_dbos_workflow_attribute_exists_when_enabled():
    """When DBOS_ENABLED is true in Config, _durable_transition_workflow is set."""
    from src.config import Config
    if Config.DBOS_ENABLED:
        from src.services.dbos_phase_workflow import _durable_transition_workflow
        assert _durable_transition_workflow is not None, \
            "_durable_transition_workflow should be set when DBOS_ENABLED=true"
        assert hasattr(_durable_transition_workflow, "dbos_function_name"), \
            f"Expected DBOS workflow with dbos_function_name, got {type(_durable_transition_workflow)}"
