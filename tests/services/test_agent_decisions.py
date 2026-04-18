from __future__ import annotations

import pytest

from src.services.agent_contracts import DelegationDecision, ReviewVerdict, TaskProposal
from src.services.agent_decisions import (
    build_task_proposal,
    choose_delegate,
    normalize_review_verdict,
)


class TestAgentDecisions:
    def test_choose_delegate_returns_typed_decision(self):
        decision = choose_delegate(
            user_goal="review staged code for safety",
            available_agents=["Builder", "Critic"],
        )

        assert isinstance(decision, DelegationDecision)
        assert decision.target_agent == "Critic"
        assert decision.reason == "goal requires structured review"
        assert decision.required_capabilities == ["repo.read_file"]

    def test_choose_delegate_defaults_to_builder_when_no_rule_matches(self):
        decision = choose_delegate(
            user_goal="ship the requested change",
            available_agents=["Ideator", "Builder", "Critic"],
        )

        assert decision.target_agent == "Builder"
        assert decision.reason == "default routing"

    def test_build_task_proposal_returns_typed_contract(self):
        proposal = build_task_proposal(
            title="Add typed review verdicts",
            description="Return structured review decisions from Critic.",
            acceptance_criteria=["Critic returns pass/retry/block"],
            suggested_agent="Critic",
            required_capabilities=["repo.read_file"],
        )

        assert isinstance(proposal, TaskProposal)
        assert proposal.summary == "Return structured review decisions from Critic."
        assert proposal.recommended_agent == "Critic"
        assert proposal.required_capabilities == ["repo.read_file"]

    def test_normalize_review_verdict_coerces_retry_shape(self):
        verdict = normalize_review_verdict(
            {
                "status": "retry",
                "summary": "missing tests",
                "retry_reason": "needs deterministic regression",
            }
        )

        assert isinstance(verdict, ReviewVerdict)
        assert verdict.status == "retry"
        assert verdict.retry_reason == "needs deterministic regression"

    def test_normalize_review_verdict_rejects_invalid_payload(self):
        with pytest.raises(ValueError, match="summary"):
            normalize_review_verdict({"status": "pass"})


# ---------------------------------------------------------------------------
# Config.PYDANTIC_AI_ENABLED True-branch coverage
# ---------------------------------------------------------------------------


def test_choose_delegate_pydantic_ai_enabled_sets_fallback_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config.PYDANTIC_AI_ENABLED=True + library absent → specific fallback reason."""
    import src.services.agent_decisions as ad_mod

    monkeypatch.setattr(ad_mod.Config, "PYDANTIC_AI_ENABLED", True)
    monkeypatch.setattr(ad_mod, "PYDANTIC_AI_AVAILABLE", False)

    decision = choose_delegate(
        user_goal="ship the requested change",  # no keyword match → fallback path
        available_agents=["Builder"],
    )

    assert decision.target_agent == "Builder"
    assert decision.reason == "pydantic-ai decisioning unavailable; using deterministic fallback"
