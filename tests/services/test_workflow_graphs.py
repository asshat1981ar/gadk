"""Tests for bounded workflow graph logic (Task 4).

Covers review→rework cycle semantics and autonomous retry/stop sequences.
All tests are deterministic and do not require LangGraph to be installed.
"""

from __future__ import annotations

import pytest

from src.services.workflow_graphs import (
    AutonomousRetryState,
    GraphDecision,
    ReviewLoopState,
    run_autonomous_retry,
    run_review_rework_cycle,
)

# ---------------------------------------------------------------------------
# ReviewLoopState construction
# ---------------------------------------------------------------------------


def test_review_loop_state_requires_non_negative_attempts():
    with pytest.raises(Exception):
        ReviewLoopState(builder_attempts=-1, review_status="pass", latest_summary="ok")


def test_review_loop_state_accepts_zero_attempts():
    state = ReviewLoopState(builder_attempts=0, review_status="pass", latest_summary="ok")
    assert state.builder_attempts == 0


# ---------------------------------------------------------------------------
# run_review_rework_cycle — plan-required tests (from task spec)
# ---------------------------------------------------------------------------


def test_review_rework_cycle_stops_on_pass():
    """Plan test: pass verdict always stops the loop."""
    state = ReviewLoopState(builder_attempts=1, review_status="pass", latest_summary="ready")

    result = run_review_rework_cycle(state)

    assert result.next_step == "stop"


def test_review_rework_cycle_retries_before_stop():
    """Plan test: retry verdict routes back to Builder while budget remains."""
    state = ReviewLoopState(
        builder_attempts=1, review_status="retry", latest_summary="missing tests"
    )

    result = run_review_rework_cycle(state, max_retries=2)

    assert result.next_step == "builder"


# ---------------------------------------------------------------------------
# run_review_rework_cycle — additional contract tests
# ---------------------------------------------------------------------------


def test_review_rework_cycle_exhausts_budget():
    """When builder_attempts reaches max_retries, stop unconditionally."""
    state = ReviewLoopState(
        builder_attempts=3, review_status="retry", latest_summary="still failing"
    )

    result = run_review_rework_cycle(state, max_retries=2)

    assert result.next_step == "critic_stop"
    assert "exhausted" in result.reason


def test_review_rework_cycle_blocks_immediately():
    """Block verdict always returns critic_stop regardless of attempt count."""
    state = ReviewLoopState(
        builder_attempts=1, review_status="block", latest_summary="safety issue"
    )

    result = run_review_rework_cycle(state)

    assert result.next_step == "critic_stop"
    assert "block" in result.reason


def test_review_rework_cycle_returns_typed_decision():
    """Return type is always GraphDecision with non-empty fields."""
    state = ReviewLoopState(builder_attempts=1, review_status="pass", latest_summary="ok")

    result = run_review_rework_cycle(state)

    assert isinstance(result, GraphDecision)
    assert result.next_step
    assert result.reason


def test_review_rework_cycle_pass_at_first_attempt():
    state = ReviewLoopState(builder_attempts=1, review_status="pass", latest_summary="clean")
    result = run_review_rework_cycle(state, max_retries=3)
    assert result.next_step == "stop"


def test_review_rework_cycle_retry_at_zero_attempts_below_budget():
    """Zero attempts with retry status should still route to builder if budget > 0."""
    state = ReviewLoopState(builder_attempts=0, review_status="retry", latest_summary="needs work")
    result = run_review_rework_cycle(state, max_retries=1)
    assert result.next_step == "builder"


def test_review_rework_cycle_retry_exactly_at_max_retries():
    """builder_attempts == max_retries should exhaust the budget."""
    state = ReviewLoopState(builder_attempts=2, review_status="retry", latest_summary="still bad")
    result = run_review_rework_cycle(state, max_retries=2)
    assert result.next_step == "critic_stop"


# ---------------------------------------------------------------------------
# run_autonomous_retry
# ---------------------------------------------------------------------------


def test_autonomous_retry_stops_on_success():
    state = AutonomousRetryState(cycle_attempts=1, last_status="success")

    result = run_autonomous_retry(state)

    assert result.next_step == "stop"


def test_autonomous_retry_continues_within_budget():
    state = AutonomousRetryState(cycle_attempts=1, last_status="retry")

    result = run_autonomous_retry(state, max_cycles=3)

    assert result.next_step == "retry"


def test_autonomous_retry_stops_when_budget_exhausted():
    state = AutonomousRetryState(cycle_attempts=5, last_status="retry")

    result = run_autonomous_retry(state, max_cycles=3)

    assert result.next_step == "stop"
    assert "exhausted" in result.reason


def test_autonomous_retry_stops_on_explicit_stop_status():
    state = AutonomousRetryState(cycle_attempts=0, last_status="stop")
    result = run_autonomous_retry(state, max_cycles=10)
    assert result.next_step == "stop"


def test_autonomous_retry_returns_typed_decision():
    state = AutonomousRetryState(cycle_attempts=0, last_status="retry")
    result = run_autonomous_retry(state)
    assert isinstance(result, GraphDecision)


def test_autonomous_retry_reason_includes_attempt_count():
    state = AutonomousRetryState(cycle_attempts=2, last_status="retry")
    result = run_autonomous_retry(state, max_cycles=5)
    assert "3" in result.reason or "2" in result.reason  # attempt numbering visible


def test_autonomous_retry_at_boundary():
    """cycle_attempts == max_cycles should stop."""
    state = AutonomousRetryState(cycle_attempts=3, last_status="retry")
    result = run_autonomous_retry(state, max_cycles=3)
    assert result.next_step == "stop"
