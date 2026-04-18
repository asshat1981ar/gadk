"""Bounded LangGraph-style workflow graphs for review→rework and autonomous retry sequences.

Design constraints (enforced, not just documented):
- ADK remains the only top-level runtime; these graphs are subordinate subflows.
- LangGraph internals are used only when the library is installed AND
  ``Config.LANGGRAPH_ENABLED`` is True; the pure-Python path is always correct.
- Every loop has an explicit stop criterion; no unbounded execution is possible.
- Graph state is modelled as typed Pydantic objects so callers and tests stay
  independent of LangGraph internals.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.config import Config

# ---------------------------------------------------------------------------
# Optional LangGraph import — kept subordinate to ADK
# ---------------------------------------------------------------------------
LANGGRAPH_AVAILABLE: bool = False
if Config.LANGGRAPH_ENABLED:
    try:
        from langgraph.graph import StateGraph  # type: ignore[import]

        LANGGRAPH_AVAILABLE = True
    except ImportError:
        pass  # Stay on pure-Python path; no import error is raised to callers


# ---------------------------------------------------------------------------
# Typed state models
# ---------------------------------------------------------------------------


class ReviewLoopState(BaseModel):
    """State carried through a bounded review→rework cycle."""

    builder_attempts: int = Field(ge=0)
    review_status: str  # expected: "pass" | "retry" | "block"
    latest_summary: str


class GraphDecision(BaseModel):
    """Decision emitted at each graph node transition."""

    next_step: str  # "stop" | "builder" | "critic_stop" | "retry"
    reason: str


class AutonomousRetryState(BaseModel):
    """State for a bounded autonomous SDLC campaign retry sequence."""

    cycle_attempts: int = Field(ge=0)
    last_status: str  # "success" | "retry" | "stop"
    failure_reason: str = ""


# ---------------------------------------------------------------------------
# Pure-Python decision logic (primary implementation path)
# ---------------------------------------------------------------------------


def _review_rework_decision(state: ReviewLoopState, max_retries: int) -> GraphDecision:
    """Deterministic bounded transition rule for review→rework cycles.

    Returns:
        ``stop``        — review passed; proceed to deliver.
        ``builder``     — retry budget remains; route back to Builder.
        ``critic_stop`` — review blocked or retry budget exhausted; halt cycle.
    """
    if state.review_status == "pass":
        return GraphDecision(next_step="stop", reason="review passed")
    if state.review_status == "block":
        return GraphDecision(
            next_step="critic_stop",
            reason="review blocked by critic; rework not permitted",
        )
    # status == "retry" (or any unrecognised status treated as retry)
    if state.builder_attempts < max_retries:
        return GraphDecision(
            next_step="builder",
            reason=f"bounded retry ({state.builder_attempts}/{max_retries})",
        )
    return GraphDecision(
        next_step="critic_stop",
        reason=f"retry budget exhausted after {state.builder_attempts} attempt(s)",
    )


# ---------------------------------------------------------------------------
# LangGraph-accelerated path (optional, same semantics)
# ---------------------------------------------------------------------------


def _run_review_rework_via_langgraph(
    state: ReviewLoopState, max_retries: int
) -> GraphDecision:
    """Thin LangGraph wrapper — applies the same decision rule through a
    single-node StateGraph.

    LangGraph is subordinate here: it only runs the transition function;
    ADK still owns sessions, routing, and the outer execution lifecycle.
    """
    from langgraph.graph import StateGraph  # type: ignore[import]  # noqa: PLC0415

    def review_node(s: dict) -> dict:
        decision = _review_rework_decision(
            ReviewLoopState(
                builder_attempts=s["builder_attempts"],
                review_status=s["review_status"],
                latest_summary=s["latest_summary"],
            ),
            max_retries,
        )
        return {**s, "next_step": decision.next_step, "reason": decision.reason}

    graph = StateGraph(dict)
    graph.add_node("review", review_node)
    graph.set_entry_point("review")
    graph.set_finish_point("review")
    compiled = graph.compile()
    result = compiled.invoke(state.model_dump())
    return GraphDecision(next_step=result["next_step"], reason=result["reason"])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_review_rework_cycle(
    state: ReviewLoopState,
    max_retries: int = 2,
) -> GraphDecision:
    """Run a bounded review→rework cycle decision.

    Uses the LangGraph-accelerated path when available and enabled; falls
    back to the identical pure-Python implementation otherwise.  The
    semantics are always identical — callers need not care which path runs.

    Args:
        state:       Current loop state (attempts, status, summary).
        max_retries: Maximum number of builder rework attempts before
                     the loop stops unconditionally.  Must be >= 1.

    Returns:
        A ``GraphDecision`` with ``next_step`` set to one of:
        - ``"stop"``        — review passed; proceed to deliver.
        - ``"builder"``     — route back to Builder for rework.
        - ``"critic_stop"`` — blocked or budget exhausted; halt cycle.
    """
    if LANGGRAPH_AVAILABLE:
        return _run_review_rework_via_langgraph(state, max_retries)
    return _review_rework_decision(state, max_retries)


def run_autonomous_retry(
    state: AutonomousRetryState,
    max_cycles: int = 3,
) -> GraphDecision:
    """Return a bounded retry/stop decision for autonomous SDLC campaign sequences.

    Prevents unbounded autonomous loops by enforcing an explicit cycle budget.

    Args:
        state:      Current campaign retry state.
        max_cycles: Maximum number of retry cycles before the campaign stops.

    Returns:
        A ``GraphDecision`` with ``next_step`` set to ``"retry"`` or ``"stop"``.
    """
    if state.last_status == "success":
        return GraphDecision(next_step="stop", reason="autonomous campaign succeeded")
    if state.last_status == "stop":
        return GraphDecision(
            next_step="stop", reason="stop requested by upstream controller"
        )
    if state.cycle_attempts < max_cycles:
        return GraphDecision(
            next_step="retry",
            reason=f"autonomous retry {state.cycle_attempts + 1}/{max_cycles}",
        )
    return GraphDecision(
        next_step="stop",
        reason=f"autonomous retry budget exhausted after {max_cycles} cycle(s)",
    )


__all__ = [
    "LANGGRAPH_AVAILABLE",
    "AutonomousRetryState",
    "GraphDecision",
    "ReviewLoopState",
    "run_autonomous_retry",
    "run_review_rework_cycle",
]
