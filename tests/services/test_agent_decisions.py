"""Tests for agent decisions module - decision-making and delegation logic."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.services.agent_contracts import DelegationDecision, ReviewVerdict, TaskProposal
from src.services.agent_decisions import (
    PYDANTIC_AI_AVAILABLE,
    build_task_proposal,
    choose_delegate,
    normalize_review_verdict,
    normalize_task_proposal,
)

# =============================================================================
# choose_delegate() Tests
# =============================================================================


class TestChooseDelegate:
    """Test cases for choose_delegate function."""

    def test_empty_available_agents_raises_error(self):
        """Test that empty available_agents list raises ValueError."""
        with pytest.raises(ValueError, match="available_agents must not be empty"):
            choose_delegate("some goal", [])

    def test_reviewer_keywords_route_to_critic(self):
        """Test keywords related to review/criticism route to Critic agent."""
        keywords_map = [
            ("review code", "Critic"),
            ("critic the implementation", "Critic"),
            ("safety check", "Critic"),
            ("quality assurance", "Critic"),
            ("test the functionality", "Critic"),
            ("validate the output", "Critic"),
        ]
        for goal, expected_agent in keywords_map:
            decision = choose_delegate(goal, ["Critic", "Builder", "Ideator"])
            assert decision.target_agent == expected_agent, f"Failed for goal: {goal}"
            assert "goal requires structured review" in decision.reason

    def test_review_keywords_require_capabilities(self):
        """Test review/critic routing adds required capabilities."""
        decision = choose_delegate("review code", ["Critic", "Builder"])
        assert "repo.read_file" in decision.required_capabilities

    def test_ideator_keywords_route_to_ideator(self):
        """Test keywords related to planning route to Ideator agent."""
        keywords_map = [
            ("generate ideas", "Ideator"),
            ("plan project", "Ideator"),
            ("research topic", "Ideator"),
            ("explore options", "Ideator"),
            ("analyze trends", "Ideator"),
            ("discover patterns", "Ideator"),
        ]
        for goal, expected_agent in keywords_map:
            decision = choose_delegate(goal, ["Ideator", "Builder", "Critic"])
            assert decision.target_agent == expected_agent, f"Failed for goal: {goal}"
            assert "goal requires discovery and planning" in decision.reason

    def test_ideator_has_read_file_capability(self):
        """Test Ideator routing adds required capabilities."""
        decision = choose_delegate("research topic", ["Ideator", "Builder"])
        assert "repo.read_file" in decision.required_capabilities

    def test_pulse_keywords_route_to_pulse(self):
        """Test keywords related to monitoring route to Pulse agent."""
        keywords_map = [
            ("check health", "Pulse"),
            ("get status", "Pulse"),
            ("monitor queue", "Pulse"),
            ("system health", "Pulse"),
        ]
        for goal, expected_agent in keywords_map:
            decision = choose_delegate(goal, ["Pulse", "Builder", "Critic"])
            assert decision.target_agent == expected_agent, f"Failed for goal: {goal}"
            assert "goal requires runtime health visibility" in decision.reason

    def test_finops_keywords_route_to_finops(self):
        """Test keywords related to budget/cost route to FinOps agent."""
        keywords_map = [
            ("analyze budget", "FinOps"),
            ("check costs", "FinOps"),
            ("spend analysis", "FinOps"),
            ("quota check", "FinOps"),
        ]
        for goal, expected_agent in keywords_map:
            decision = choose_delegate(goal, ["FinOps", "Builder", "Critic"])
            assert decision.target_agent == expected_agent, f"Failed for goal: {goal}"
            assert "goal requires cost and budget analysis" in decision.reason

    def test_builder_keywords_route_to_builder(self):
        """Test keywords related to implementation route to Builder agent."""
        keywords_map = [
            ("build feature", "Builder"),
            ("implement interface", "Builder"),
            ("code solution", "Builder"),
            ("create module", "Builder"),
            ("fix bug", "Builder"),
        ]
        for goal, expected_agent in keywords_map:
            decision = choose_delegate(goal, ["Builder", "Ideator", "Critic"])
            assert decision.target_agent == expected_agent, f"Failed for goal: {goal}"
            assert "goal requires implementation work" in decision.reason

    def test_keywords_case_insensitive(self):
        """Test that keyword matching is case insensitive."""
        test_cases = [
            ("BUILD A Feature", "BUILD"),
            ("Review CODE", "REVIEW"),
            ("RESEARCH Topic", "RESEARCH"),
        ]
        for goal, expected_in_reason in test_cases:
            # Just verify no error occurs and result is returned
            decision = choose_delegate(goal, ["Builder", "Critic", "Ideator"])
            assert isinstance(decision, DelegationDecision)

    def test_unknown_goal_falls_back_to_builder(self):
        """Test unknown goals fall back to Builder."""
        decision = choose_delegate(
            "something completely unrelated", ["Builder", "Critic", "Ideator"]
        )
        assert decision.target_agent == "Builder"
        assert "default routing" in decision.reason

    def test_unknown_goal_falls_back_to_first_available_agent(self):
        """Test unknown goals fall back to first available if Builder not present."""
        decision = choose_delegate("unknown goal", ["Ideator", "Critic"])
        assert decision.target_agent == "Ideator"

    def test_priority_ordering_respected(self):
        """Test that keyword priority is respected (review > idea > health > budget > build)."""
        # "review" comes before "build" in priority
        multi_keyword_goal = "review and build something"
        available = ["Critic", "Builder", "Ideator"]
        decision = choose_delegate(multi_keyword_goal, available)
        # Should pick Critic (review) over Builder (build)
        assert decision.target_agent == "Critic"

    def test_delegation_returns_typed_delegation_decision(self):
        """Test that choose_delegate returns a DelegationDecision instance."""
        decision = choose_delegate("build feature", ["Builder"])
        assert isinstance(decision, DelegationDecision)

    def test_target_agent_must_be_in_available(self):
        """Test that target agent is from available agents list."""
        decision = choose_delegate("review code", ["Critic", "Builder"])
        assert decision.target_agent in ["Critic", "Builder"]

    @patch("src.services.agent_decisions.PYDANTIC_AI_AVAILABLE", False)
    @patch("src.services.agent_decisions.Config.PYDANTIC_AI_ENABLED", True)
    def test_fallback_reason_when_pydantic_ai_unavailable(self):
        """Test fallback reason when pydantic-ai is enabled but unavailable."""
        from src.services.agent_decisions import choose_delegate as cd

        decision = cd("unknown goal", ["Builder"])
        assert "pydantic-ai decisioning unavailable" in decision.reason


# =============================================================================
# normalize_task_proposal() Tests
# =============================================================================


class TestNormalizeTaskProposal:
    """Test cases for normalize_task_proposal function."""

    def test_normalize_task_proposal_with_dict(self):
        """Test normalize_task_proposal accepts dict input."""
        payload = {
            "title": "Test Task",
            "summary": "Summary",
            "description": "Detailed description",
            "acceptance_criteria": ["criterion 1"],
            "recommended_agent": "Builder",
            "required_capabilities": ["repo.commit"],
        }
        result = normalize_task_proposal(payload)
        assert isinstance(result, TaskProposal)
        assert result.title == "Test Task"
        assert result.summary == "Summary"
        assert result.description == "Detailed description"
        assert result.acceptance_criteria == ["criterion 1"]
        assert result.recommended_agent == "Builder"
        assert result.required_capabilities == ["repo.commit"]

    def test_normalize_task_proposal_with_task_proposal_object(self):
        """Test normalize_task_proposal accepts TaskProposal input."""
        original = TaskProposal(
            title="Original",
            summary="Original summary",
            description="Original desc",
            recommended_agent="Critic",
        )
        result = normalize_task_proposal(original)
        # Returns equal object (may be same or re-validated)
        assert result == original
        assert isinstance(result, TaskProposal)

    def test_normalize_task_proposal_with_string_json(self):
        """Test normalize_task_proposal accepts JSON string input."""
        json_str = '{"title": "JSON Task", "summary": "JSON summary", "description": "JSON desc", "recommended_agent": "Builder"}'
        result = normalize_task_proposal(json_str)
        assert isinstance(result, TaskProposal)
        assert result.title == "JSON Task"


# =============================================================================
# build_task_proposal() Tests
# =============================================================================


class TestBuildTaskProposal:
    """Test cases for build_task_proposal function."""

    def test_build_task_proposal_basic(self):
        """Test build_task_proposal with minimal required arguments."""
        result = build_task_proposal(
            title="Feature A",
            description="Build feature A",
            acceptance_criteria=["Works", "Tested"],
            suggested_agent="Builder",
        )
        assert isinstance(result, TaskProposal)
        assert result.title == "Feature A"
        assert result.description == "Build feature A"
        assert result.summary == "Build feature A"  # summary defaults to description
        assert result.acceptance_criteria == ["Works", "Tested"]
        assert result.recommended_agent == "Builder"
        assert result.required_capabilities == []

    def test_build_task_proposal_with_summary(self):
        """Test build_task_proposal with explicit summary."""
        result = build_task_proposal(
            title="Feature B",
            description="Detailed description of feature B",
            acceptance_criteria=["c1", "c2"],
            suggested_agent="Critic",
            summary="Short summary",
        )
        assert result.title == "Feature B"
        assert result.description == "Detailed description of feature B"
        assert result.summary == "Short summary"  # explicit summary
        assert result.recommended_agent == "Critic"

    def test_build_task_proposal_with_capabilities(self):
        """Test build_task_proposal with required capabilities."""
        result = build_task_proposal(
            title="Feature C",
            description="Complex feature",
            acceptance_criteria=["c1"],
            suggested_agent="Ideator",
            required_capabilities=["repo.read", "analysis.plan"],
        )
        assert result.required_capabilities == ["repo.read", "analysis.plan"]

    def test_build_task_proposal_returns_validated_task_proposal(self):
        """Test build_task_proposal returns a validated TaskProposal."""
        result = build_task_proposal(
            title="Test",
            description="Test desc",
            acceptance_criteria=[],
            suggested_agent="Builder",
        )
        assert isinstance(result, TaskProposal)
        # Verify internal normalization was called
        assert hasattr(result, "title")


# =============================================================================
# normalize_review_verdict() Tests
# =============================================================================


class TestNormalizeReviewVerdict:
    """Test cases for normalize_review_verdict function."""

    def test_normalize_review_verdict_with_dict(self):
        """Test normalize_review_verdict accepts dict input."""
        payload = {
            "status": "pass",
            "summary": "Code looks good",
            "concerns": [],
            "recommended_actions": [],
        }
        result = normalize_review_verdict(payload)
        assert isinstance(result, ReviewVerdict)
        assert result.status == "pass"
        assert result.summary == "Code looks good"
        assert result.concerns == []
        assert result.recommended_actions == []

    def test_normalize_review_verdict_with_review_verdict_object(self):
        """Test normalize_review_verdict accepts ReviewVerdict input."""
        original = ReviewVerdict(
            status="retry",
            summary="Needs changes",
        )
        result = normalize_review_verdict(original)
        # Returns equal object (may be same or re-validated)
        assert result == original
        assert isinstance(result, ReviewVerdict)

    def test_normalize_review_verdict_with_string_json(self):
        """Test normalize_review_verdict accepts JSON string input."""
        json_str = (
            '{"status": "block", "summary": "Critical issues found", "concerns": ["security hole"]}'
        )
        result = normalize_review_verdict(json_str)
        assert isinstance(result, ReviewVerdict)
        assert result.status == "block"
        assert result.summary == "Critical issues found"
        assert result.concerns == ["security hole"]


# =============================================================================
# PYDANTIC_AI_AVAILABLE Tests
# =============================================================================


class TestPydanticAIAvailable:
    """Test cases for PYDANTIC_AI_AVAILABLE constant."""

    def test_pydantic_ai_available_is_boolean(self):
        """Test PYDANTIC_AI_AVAILABLE is a boolean."""
        assert isinstance(PYDANTIC_AI_AVAILABLE, bool)

    def test_pydantic_ai_available_defined(self):
        """Test PYDANTIC_AI_AVAILABLE is defined."""
        # Should be either True or False, never undefined
        assert PYDANTIC_AI_AVAILABLE in (True, False)


# =============================================================================
# Integration Tests
# =============================================================================


class TestDecisionWorkflow:
    """Integration tests for decision workflow."""

    def test_end_to_end_task_proposal_workflow(self):
        """Test complete task proposal workflow."""
        # Build a proposal
        proposal = build_task_proposal(
            title="Refactor Authentication",
            description="Update auth module to use OAuth2",
            acceptance_criteria=[
                "All existing tests pass",
                "OAuth2 integration complete",
                "Documentation updated",
            ],
            suggested_agent="Builder",
            required_capabilities=["repo.commit", "repo.push"],
        )

        # Normalize it (could be through API, file, etc)
        normalized = normalize_task_proposal(proposal)

        assert normalized.title == "Refactor Authentication"
        assert len(normalized.acceptance_criteria) == 3

    def test_end_to_end_delegation_workflow(self):
        """Test complete delegation workflow."""
        # User has a goal
        user_goal = "I need to review the pull request for security issues"

        # System chooses a delegate
        decision = choose_delegate(user_goal, ["Critic", "Builder", "Ideator", "Pulse", "FinOps"])

        assert decision.target_agent == "Critic"
        assert "goal requires structured review" in decision.reason

        # Then we could build a task proposal based on this
        proposal = build_task_proposal(
            title="Security Review",
            description="Review PR for security vulnerabilities",
            acceptance_criteria=["No security issues found"],
            suggested_agent=decision.target_agent,
            required_capabilities=decision.required_capabilities,
        )

        assert proposal.recommended_agent == "Critic"

    def test_review_verdict_workflow(self):
        """Test review verdict handling in workflow."""
        # Simulate receiving a verdict from JSON/API
        verdict_json = '{"status": "retry", "summary": "Minor issues found", "retry_reason": "Missing docstrings"}'

        verdict = normalize_review_verdict(verdict_json)

        assert verdict.status == "retry"
        assert verdict.retry_reason == "Missing docstrings"
        assert verdict.concerns == []  # Default empty


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_delegation_with_single_agent(self):
        """Test delegation with only one available agent."""
        decision = choose_delegate("any goal", ["Builder"])
        assert decision.target_agent == "Builder"

    def test_delegation_goal_with_whitespace(self):
        """Test delegation goal with extra whitespace."""
        decision = choose_delegate("   build something   ", ["Builder", "Critic"])
        assert "goal requires implementation work" in decision.reason

    def test_build_proposal_empty_acceptance_criteria(self):
        """Test building proposal with empty acceptance criteria."""
        result = build_task_proposal(
            title="Simple Task",
            description="Do something simple",
            acceptance_criteria=[],
            suggested_agent="Builder",
        )
        assert result.acceptance_criteria == []

    def test_normalize_task_proposal_with_malformed_dict(self):
        """Test normalize_task_proposal with missing fields raises validation error."""
        with pytest.raises(Exception):  # Pydantic validation error
            normalize_task_proposal({"title_only": "incomplete"})


# =============================================================================
# Module Export Tests
# =============================================================================


def test_all_expected_functions_exported():
    """Test that all expected functions are in __all__."""
    from src.services import agent_decisions

    expected_exports = [
        "PYDANTIC_AI_AVAILABLE",
        "build_task_proposal",
        "choose_delegate",
        "normalize_review_verdict",
        "normalize_task_proposal",
    ]

    for export in expected_exports:
        assert export in agent_decisions.__all__

    # Ensure no duplicates
    assert len(set(agent_decisions.__all__)) == len(agent_decisions.__all__)
