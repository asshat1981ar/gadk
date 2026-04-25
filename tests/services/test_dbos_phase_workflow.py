# tests/services/test_dbos_phase_workflow.py
from __future__ import annotations

import pytest
from src.services.sdlc_phase import Phase, WorkItem
from src.services.dbos_phase_workflow import transition_workflow


def test_workflow_runs_single_transition():
    """A PLAN→ARCHITECT transition completes and returns the updated item."""
    item = WorkItem(id="task-1", phase=Phase.PLAN)
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
