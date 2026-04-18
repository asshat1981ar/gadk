"""Parity tests: LangGraph path vs pure-Python path for run_review_rework_cycle.

Both ``_review_rework_decision`` (pure-Python) and
``_run_review_rework_via_langgraph`` (LangGraph-accelerated) must produce
semantically identical ``GraphDecision`` objects for every input.

The module is skipped entirely when LangGraph is not installed so that
environments without the optional dependency still produce a clean pass.
"""

from __future__ import annotations

import pytest

# Skip the whole module when langgraph is not installed.
pytest.importorskip("langgraph")

from src.services.workflow_graphs import (  # noqa: E402 (after importorskip)
    GraphDecision,
    ReviewLoopState,
    _review_rework_decision,
    _run_review_rework_via_langgraph,
)

# ---------------------------------------------------------------------------
# Parametrize matrix: (builder_attempts, review_status, max_retries)
# Expected outcomes are derived from the pure-Python logic, which is the
# source of truth; the LangGraph path must reproduce them exactly.
# ---------------------------------------------------------------------------

PARITY_CASES = [
    # --- pass → always stop ------------------------------------------------
    pytest.param(0, "pass", 2, id="pass-0attempts-max2"),
    pytest.param(1, "pass", 2, id="pass-1attempt-max2"),
    pytest.param(0, "pass", 1, id="pass-0attempts-max1"),
    # --- retry within budget → builder -------------------------------------
    pytest.param(0, "retry", 2, id="retry-0attempts-max2-within-budget"),
    pytest.param(1, "retry", 3, id="retry-1attempt-max3-within-budget"),
    # --- retry exhausted → critic_stop -------------------------------------
    pytest.param(2, "retry", 2, id="retry-at-max-exhausted"),
    pytest.param(3, "retry", 2, id="retry-beyond-max-exhausted"),
    # --- block → always critic_stop ----------------------------------------
    pytest.param(0, "block", 2, id="block-0attempts"),
    pytest.param(2, "block", 5, id="block-2attempts-budget-remaining"),
    # --- unrecognised status treated as retry ------------------------------
    pytest.param(0, "unknown", 3, id="unknown-status-within-budget"),
    pytest.param(5, "unknown", 3, id="unknown-status-exhausted"),
]


@pytest.mark.parametrize("builder_attempts,review_status,max_retries", PARITY_CASES)
def test_langgraph_path_matches_pure_python(
    builder_attempts: int,
    review_status: str,
    max_retries: int,
) -> None:
    """Both paths must produce identical next_step and reason for the same input."""
    state = ReviewLoopState(
        builder_attempts=builder_attempts,
        review_status=review_status,
        latest_summary="parity test summary",
    )

    pure_python: GraphDecision = _review_rework_decision(state, max_retries)
    langgraph_result: GraphDecision = _run_review_rework_via_langgraph(state, max_retries)

    assert langgraph_result.next_step == pure_python.next_step, (
        f"next_step mismatch for {review_status!r} "
        f"(attempts={builder_attempts}, max={max_retries}): "
        f"pure-Python={pure_python.next_step!r}, "
        f"langgraph={langgraph_result.next_step!r}"
    )
    assert langgraph_result.reason == pure_python.reason, (
        f"reason mismatch for {review_status!r} "
        f"(attempts={builder_attempts}, max={max_retries}): "
        f"pure-Python={pure_python.reason!r}, "
        f"langgraph={langgraph_result.reason!r}"
    )
