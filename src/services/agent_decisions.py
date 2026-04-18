from __future__ import annotations

from typing import Any

from src.config import Config
from src.services.agent_contracts import DelegationDecision, ReviewVerdict, TaskProposal
from src.services.structured_output import parse_review_verdict, parse_task_proposal

try:  # pragma: no cover - optional dependency in local environments
    import pydantic_ai  # noqa: F401

    PYDANTIC_AI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised through fallback behavior
    PYDANTIC_AI_AVAILABLE = False


def choose_delegate(user_goal: str, available_agents: list[str]) -> DelegationDecision:
    """Return a typed delegation decision for the current goal."""
    if not available_agents:
        raise ValueError("available_agents must not be empty")

    normalized_goal = user_goal.strip().lower()
    ranked_rules: list[tuple[tuple[str, ...], str, str]] = [
        (
            ("review", "critic", "safety", "quality", "test", "validate"),
            "Critic",
            "goal requires structured review",
        ),
        (
            ("idea", "plan", "research", "explore", "trend", "discover"),
            "Ideator",
            "goal requires discovery and planning",
        ),
        (
            ("health", "status", "queue", "monitor"),
            "Pulse",
            "goal requires runtime health visibility",
        ),
        (
            ("budget", "cost", "spend", "quota"),
            "FinOps",
            "goal requires cost and budget analysis",
        ),
        (
            ("build", "implement", "code", "create", "fix"),
            "Builder",
            "goal requires implementation work",
        ),
    ]

    for keywords, candidate, reason in ranked_rules:
        if candidate in available_agents and any(
            keyword in normalized_goal for keyword in keywords
        ):
            required_capabilities = ["repo.read_file"] if candidate in {"Ideator", "Critic"} else []
            return DelegationDecision(
                target_agent=candidate,
                reason=reason,
                required_capabilities=required_capabilities,
            )

    fallback_agent = "Builder" if "Builder" in available_agents else available_agents[0]
    fallback_reason = (
        "pydantic-ai decisioning unavailable; using deterministic fallback"
        if Config.PYDANTIC_AI_ENABLED and not PYDANTIC_AI_AVAILABLE
        else "default routing"
    )
    return DelegationDecision(
        target_agent=fallback_agent,
        reason=fallback_reason,
        required_capabilities=[],
    )


def normalize_task_proposal(payload: TaskProposal | dict[str, Any] | str) -> TaskProposal:
    """Coerce ideation output into the shared task-proposal contract."""
    return parse_task_proposal(payload)


def build_task_proposal(
    *,
    title: str,
    description: str,
    acceptance_criteria: list[str],
    suggested_agent: str,
    required_capabilities: list[str] | None = None,
    summary: str | None = None,
) -> TaskProposal:
    """Build a validated task proposal from ideator inputs."""
    return normalize_task_proposal(
        {
            "title": title,
            "summary": summary or description,
            "description": description,
            "acceptance_criteria": acceptance_criteria,
            "recommended_agent": suggested_agent,
            "required_capabilities": required_capabilities or [],
        }
    )


def normalize_review_verdict(payload: ReviewVerdict | dict[str, Any] | str) -> ReviewVerdict:
    """Coerce critic output into the shared review-verdict contract."""
    return parse_review_verdict(payload)


__all__ = [
    "PYDANTIC_AI_AVAILABLE",
    "build_task_proposal",
    "choose_delegate",
    "normalize_review_verdict",
    "normalize_task_proposal",
]
