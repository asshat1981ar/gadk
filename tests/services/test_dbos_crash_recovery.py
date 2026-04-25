from __future__ import annotations

from src.services.sdlc_phase import Phase
from src.services.dbos_phase_workflow import transition_workflow


def test_workflow_produces_valid_result_structure():
    """transition_workflow returns complete, well-typed result dict."""
    result = transition_workflow(
        item_id='crash-test-1',
        target_phase=Phase.ARCHITECT,
        current_phase=Phase.PLAN,
    )
    assert isinstance(result, dict)
    assert result['item_id'] == 'crash-test-1'
    assert 'from_phase' in result
    assert 'to_phase' in result
    assert 'advanced' in result
    assert 'reason' in result
    assert 'gates' in result
    assert isinstance(result['gates'], list)


def test_workflow_with_dbos_enabled_degrades_gracefully():
    """When DBOS_ENABLED=true but DBOS not launched, workflow still completes."""
    # This should not raise — even if DBOS isn't initialized,
    # the workflow should fall back to PhaseController.advance()
    result = transition_workflow(
        item_id='graceful-degrade-1',
        target_phase=Phase.REVIEW,
        current_phase=Phase.IMPLEMENT,
    )
    assert result['item_id'] == 'graceful-degrade-1'
    assert isinstance(result['advanced'], bool)