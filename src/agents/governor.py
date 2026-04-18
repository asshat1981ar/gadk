"""Governor agent — owner of the GOVERN SDLC phase.

Composes existing review, cost, and content primitives into a single
governance decision surface. Unlike Critic (which rules on implementation
quality at REVIEW), Governor rules on *release readiness* at GOVERN:
lint / type / coverage / security are already green at this point, so
its job is the softer cross-cutting checks — budget, content substance,
and optional external gate registration via the SDLC MCP client.

Design choices:
- Pure functions at module scope; ADK agent is optional and gated on
  ``google.adk`` being importable (mirrors architect.py).
- SDLC MCP integration (``Config.SDLC_MCP_ENABLED``) is a soft hook —
  the Governor records a ``sdlc.gate.skipped`` verdict when the client
  is absent rather than erroring, so local runs remain unblocked.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.config import Config
from src.observability.cost_tracker import CostTracker
from src.observability.logger import get_logger
from src.services.sdlc_phase import Phase
from src.tools.content_guards import is_low_value_content

logger = get_logger("governor")

_tracker = CostTracker()
_BUDGET_USD = float(os.getenv("BUDGET_USD", "10.0"))


async def _check_quota(task_id: str, cost_usd: float) -> dict[str, Any]:
    """Inline FinOps quota check — mirrors ``src.agents.finops.check_quota``
    but avoids importing the FinOps ADK agent module (which pulls in
    google.adk even when we just want the tracker)."""
    _tracker.record_cost(task_id, "governor", cost_usd)
    total = _tracker.get_total_spend()
    if total > _BUDGET_USD:
        return {
            "status": "BUDGET_EXCEEDED",
            "limit_usd": _BUDGET_USD,
            "current_usd": total,
        }
    return {"status": "OK", "current_usd": total, "budget_usd": _BUDGET_USD}


@dataclass
class GovernanceVerdict:
    """Aggregate outcome of a governance pass."""

    task_id: str
    ready: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    concerns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "ready": self.ready,
            "evidence": self.evidence,
            "concerns": self.concerns,
        }


#: Second-pass reviewer callable — typically the Critic agent's
#: ``create_review_verdict`` bound into a closure. Keeping this injectable
#: means the Governor stays testable without spinning up an LLM.
ReviewerFn = Callable[[dict[str, Any]], dict[str, Any]]


async def run_governance_review(
    task_id: str,
    payload: dict[str, Any],
    *,
    reviewer: ReviewerFn | None = None,
    min_body_bytes: int = 120,
) -> dict[str, Any]:
    """Aggregate Critic + FinOps + content-guard signals into a GOVERN verdict.

    Args:
        task_id:         Work-item identifier; used for audit logging.
        payload:         Must contain ``body`` (the release note / PR body).
                         May contain ``cost_usd`` for the budget check.
        reviewer:        Optional callable that runs a second-pass review.
                         When provided, its returned dict must include
                         ``status`` (``pass | retry | block``) and
                         ``summary``.
        min_body_bytes:  Content-guard threshold at the GOVERN boundary.

    Returns:
        A dict-shaped :class:`GovernanceVerdict`.
    """
    concerns: list[str] = []
    evidence: dict[str, Any] = {}

    body = str(payload.get("body", ""))
    low_value = is_low_value_content(body, min_bytes=min_body_bytes)
    evidence["content_guard"] = {"body_len": len(body), "low_value": low_value}
    if low_value:
        concerns.append("release note is too thin or contains only leakage")

    cost_usd = float(payload.get("cost_usd", 0.0))
    quota = await _check_quota(task_id=task_id, cost_usd=cost_usd)
    evidence["finops"] = quota
    if quota.get("status") == "BUDGET_EXCEEDED":
        concerns.append(
            f"budget exceeded ({quota.get('current_usd'):.2f} > {quota.get('limit_usd'):.2f})"
        )

    if reviewer is not None:
        second_pass = reviewer(payload)
        evidence["second_pass"] = second_pass
        status = str(second_pass.get("status", "retry"))
        if status != "pass":
            concerns.append(f"second-pass review returned status={status}")

    verdict = GovernanceVerdict(
        task_id=task_id,
        ready=not concerns,
        evidence=evidence,
        concerns=concerns,
    )
    logger.info(
        "govern.verdict task=%s ready=%s concerns=%d",
        verdict.task_id,
        verdict.ready,
        len(verdict.concerns),
    )
    return verdict.to_dict()


def register_external_gate(task_id: str, verdict: dict[str, Any]) -> dict[str, Any]:
    """Optionally forward a governance verdict to the external SDLC MCP server.

    Dormant unless ``Config.SDLC_MCP_ENABLED`` is True. Always returns a
    dict so callers never have to branch on None.
    """
    if not Config.SDLC_MCP_ENABLED:
        return {
            "status": "sdlc.gate.skipped",
            "task_id": task_id,
            "reason": "SDLC_MCP_ENABLED=false",
        }

    try:
        from src.mcp.sdlc_client import submit_gate_decision  # type: ignore[import-not-found]
    except ImportError as exc:
        logger.debug("sdlc_client not available: %s", exc)
        return {"status": "sdlc.gate.skipped", "task_id": task_id, "reason": "sdlc_client missing"}

    result = submit_gate_decision(task_id=task_id, verdict=verdict)
    logger.info("sdlc.gate.submitted task=%s result=%s", task_id, result)
    return {"status": "sdlc.gate.submitted", "task_id": task_id, "result": result}


# ---------------------------------------------------------------------------
# Optional ADK wiring
# ---------------------------------------------------------------------------

governor_agent: Any = None

try:  # pragma: no cover — ADK wiring is exercised by integration tests
    from google.adk.agents import Agent

    from src.tools.dispatcher import batch_execute
    from src.tools.filesystem import list_directory, read_file
    from src.tools.github_tool import list_repo_contents, read_repo_file

    if Config.TEST_MODE:
        from src.testing.mock_llm import MockLiteLlm as LiteLlm
    else:
        from google.adk.models.lite_llm import LiteLlm

    _model = LiteLlm(
        model=Config.OPENROUTER_TOOL_MODEL,
        api_key=Config.OPENROUTER_API_KEY,
        api_base=Config.OPENROUTER_API_BASE,
    )

    governor_agent = Agent(
        name="Governor",
        model=_model,
        description="Owns GOVERN phase: release readiness, budget, optional external SDLC gate.",
        instruction="""You are the Governor of the Cognitive Foundry.

At GOVERN you decide whether a task is ready to ship. Use
`run_governance_review` with the release note / PR body and (if known)
the cumulative cost_usd. If the verdict is ready, optionally call
`register_external_gate` to surface the decision to the external SDLC
tooling. If not ready, enumerate the concerns and route the work item
back to REVIEW.

Phase under your ownership: """
        + Phase.GOVERN.value,
        tools=[
            batch_execute,
            run_governance_review,
            register_external_gate,
            read_file,
            list_directory,
            read_repo_file,
            list_repo_contents,
        ],
    )
except ImportError as exc:
    logger.debug("ADK unavailable; governor_agent disabled: %s", exc)


__all__ = [
    "GovernanceVerdict",
    "ReviewerFn",
    "governor_agent",
    "register_external_gate",
    "run_governance_review",
]
