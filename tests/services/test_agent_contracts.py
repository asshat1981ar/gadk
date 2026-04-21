"""Tests for agent contracts module - Pydantic models for agent communication."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.services.agent_contracts import (
    AgentDecision,
    AgentMemory,
    DelegationDecision,
    ReviewStatus,
    ReviewVerdict,
    SpecialistRegistration,
    TaskProposal,
)


# =============================================================================
# DelegationDecision Tests
# =============================================================================

class TestDelegationDecision:
    """Test cases for DelegationDecision model."""

    def test_minimal_valid_delegation(self):
        """Test DelegationDecision creation with minimal required fields."""
        decision = DelegationDecision(
            target_agent="Builder",
            reason="goal requires implementation work", 
        )
        assert decision.target_agent == "Builder"
        assert decision.reason == "goal requires implementation work"
        assert decision.required_capabilities == []
        assert decision.specialist_hint is None

    def test_delegation_with_all_fields(self):
        """Test DelegationDecision creation with all fields populated."""
        decision = DelegationDecision(
            target_agent="Critic",
            reason="Safety review required",
            required_capabilities=["repo.read_file", "analysis.critical"],
            specialist_hint="security_expert",
        )
        assert decision.target_agent == "Critic"
        assert decision.reason == "Safety review required"
        assert decision.required_capabilities == ["repo.read_file", "analysis.critical"]
        assert decision.specialist_hint == "security_expert"

    def test_delegation_target_agent_min_length(self):
        """Test target_agent must have at least 1 character."""
        with pytest.raises(ValidationError):
            DelegationDecision(target_agent="", reason="some reason")

    def test_delegation_reason_min_length(self):
        """Test reason must have at least 1 character."""
        with pytest.raises(ValidationError):
            DelegationDecision(target_agent="Builder", reason="")

    def test_delegation_extra_fields_forbidden(self):
        """Test DelegationDecision rejects extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            DelegationDecision(
                target_agent="Builder",
                reason="test",
                extra_field="not allowed",
            )
        assert "extra_field" in str(exc_info.value)

    def test_delegation_required_capabilities_defaults(self):
        """Test required_capabilities defaults to empty list."""
        decision = DelegationDecision(
            target_agent="Ideator",
            reason="needs ideas",
        )
        assert decision.required_capabilities == []


# =============================================================================
# TaskProposal Tests
# =============================================================================

class TestTaskProposal:
    """Test cases for TaskProposal model."""

    def test_minimal_valid_proposal(self):
        """Test TaskProposal creation with minimal required fields."""
        proposal = TaskProposal(
            title="Build Feature X",
            summary="Implement feature X for better UX",
            description="Detailed description of feature X",
            recommended_agent="Builder",
        )
        assert proposal.title == "Build Feature X"
        assert proposal.summary == "Implement feature X for better UX"
        assert proposal.description == "Detailed description of feature X"
        assert proposal.recommended_agent == "Builder"
        assert proposal.acceptance_criteria == []
        assert proposal.required_capabilities == []

    def test_proposal_with_all_fields(self):
        """Test TaskProposal creation with all fields."""
        proposal = TaskProposal(
            title="Refactor Codebase",
            summary="Clean up legacy code",
            description="Refactor old module structure",
            acceptance_criteria=["All tests pass", "Code coverage >80%"],
            recommended_agent="Builder",
            required_capabilities=["repo.commit", "repo.push"],
        )
        assert proposal.title == "Refactor Codebase"
        assert proposal.summary == "Clean up legacy code"
        assert proposal.description == "Refactor old module structure"
        assert proposal.acceptance_criteria == ["All tests pass", "Code coverage >80%"]
        assert proposal.recommended_agent == "Builder"
        assert proposal.required_capabilities == ["repo.commit", "repo.push"]

    def test_proposal_title_min_length(self):
        """Test title must have at least 1 character."""
        with pytest.raises(ValidationError):
            TaskProposal(
                title="",
                summary="summary",
                description="description",
                recommended_agent="Builder",
            )

    def test_proposal_summary_min_length(self):
        """Test summary must have at least 1 character."""
        with pytest.raises(ValidationError):
            TaskProposal(
                title="title",
                summary="",
                description="description", 
                recommended_agent="Builder",
            )

    def test_proposal_description_min_length(self):
        """Test description must have at least 1 character."""
        with pytest.raises(ValidationError):
            TaskProposal(
                title="title",
                summary="summary",
                description="",
                recommended_agent="Builder",
            )

    def test_proposal_recommended_agent_min_length(self):
        """Test recommended_agent must have at least 1 character."""
        with pytest.raises(ValidationError):
            TaskProposal(
                title="title",
                summary="summary",
                description="description",
                recommended_agent="",
            )

    def test_proposal_extra_fields_forbidden(self):
        """Test TaskProposal rejects extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            TaskProposal(
                title="title",
                summary="summary",
                description="description",
                recommended_agent="Builder",
                unknown_field="value",
            )
        assert "unknown_field" in str(exc_info.value)


# =============================================================================
# ReviewVerdict Tests
# =============================================================================

class TestReviewVerdict:
    """Test cases for ReviewVerdict model."""

    def test_review_valid_status_pass(self):
        """Test ReviewVerdict with pass status."""
        verdict = ReviewVerdict(
            status="pass",
            summary="Code meets standards",
        )
        assert verdict.status == "pass"
        assert verdict.summary == "Code meets standards"
        assert verdict.concerns == []
        assert verdict.retry_reason is None
        assert verdict.recommended_actions == []

    def test_review_valid_status_retry(self):
        """Test ReviewVerdict with retry status."""
        verdict = ReviewVerdict(
            status="retry",
            summary="Needs minor fixes",
            retry_reason="Missing documentation",
        )
        assert verdict.status == "retry"
        assert verdict.summary == "Needs minor fixes"
        assert verdict.retry_reason == "Missing documentation"

    def test_review_valid_status_block(self):
        """Test ReviewVerdict with block status."""
        verdict = ReviewVerdict(
            status="block",
            summary="Critical security issues found",
            concerns=["SQL injection vulnerability", "XSS risk"],
            recommended_actions=["Audit code", "Add input validation"],
        )
        assert verdict.status == "block"
        assert verdict.summary == "Critical security issues found"
        assert verdict.concerns == ["SQL injection vulnerability", "XSS risk"]
        assert verdict.recommended_actions == ["Audit code", "Add input validation"]

    def test_review_invalid_status(self):
        """Test ReviewVerdict rejects invalid status values."""
        with pytest.raises(ValidationError):
            ReviewVerdict(status="invalid", summary="test")

    def test_review_summary_min_length(self):
        """Test summary must have at least 1 character."""
        with pytest.raises(ValidationError):
            ReviewVerdict(status="pass", summary="")

    def test_review_with_all_fields(self):
        """Test ReviewVerdict with all fields populated."""
        verdict = ReviewVerdict(
            status="retry",
            summary="Needs work",
            concerns=["Concern 1", "Concern 2"],
            retry_reason="Not ready",
            recommended_actions=["Fix A", "Fix B"],
        )
        assert verdict.status == "retry"
        assert verdict.summary == "Needs work"
        assert verdict.concerns == ["Concern 1", "Concern 2"]
        assert verdict.retry_reason == "Not ready"
        assert verdict.recommended_actions == ["Fix A", "Fix B"]

    def test_review_extra_fields_forbidden(self):
        """Test ReviewVerdict rejects extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            ReviewVerdict(
                status="pass",
                summary="test",
                extra_field="not allowed",
            )
        assert "extra_field" in str(exc_info.value)

    def test_review_concerns_defaults_to_empty(self):
        """Test concerns defaults to empty list."""
        verdict = ReviewVerdict(status="pass", summary="test")
        assert verdict.concerns == []

    def test_review_recommended_actions_defaults_to_empty(self):
        """Test recommended_actions defaults to empty list."""
        verdict = ReviewVerdict(status="pass", summary="test")
        assert verdict.recommended_actions == []


# =============================================================================
# SpecialistRegistration Tests
# =============================================================================

class TestSpecialistRegistration:
    """Test cases for SpecialistRegistration model."""

    def test_minimal_valid_registration(self):
        """Test SpecialistRegistration with minimal required fields."""
        reg = SpecialistRegistration(
            name="SecurityExpert",
            role="security_reviewer",
            description="Reviews code for security vulnerabilities",
            escalation_target="SecurityLead",
        )
        assert reg.name == "SecurityExpert"
        assert reg.role == "security_reviewer"
        assert reg.description == "Reviews code for security vulnerabilities"
        assert reg.escalation_target == "SecurityLead"
        assert reg.inputs == []
        assert reg.outputs == []
        assert reg.capability_needs == []
        assert reg.tags == []

    def test_registration_with_all_fields(self):
        """Test SpecialistRegistration with all fields."""
        reg = SpecialistRegistration(
            name="PerformanceExpert",
            role="performance_analyst",
            description="Analyzes and optimizes system performance",
            inputs=["profiling_data", "metrics"],
            outputs=["recommendations", "optimization_plan"],
            capability_needs=["profiling.tools", "benchmarking"],
            escalation_target="TechLead",
            tags=["performance", "optimization", "critical"],
        )
        assert reg.name == "PerformanceExpert"
        assert reg.role == "performance_analyst"
        assert reg.description == "Analyzes and optimizes system performance"
        assert reg.inputs == ["profiling_data", "metrics"]
        assert reg.outputs == ["recommendations", "optimization_plan"]
        assert reg.capability_needs == ["profiling.tools", "benchmarking"]
        assert reg.escalation_target == "TechLead"
        assert reg.tags == ["performance", "optimization", "critical"]

    def test_registration_name_min_length(self):
        """Test name must have at least 1 character."""
        with pytest.raises(ValidationError):
            SpecialistRegistration(
                name="",
                role="test",
                description="test",
                escalation_target="test",
            )

    def test_registration_role_min_length(self):
        """Test role must have at least 1 character."""
        with pytest.raises(ValidationError):
            SpecialistRegistration(
                name="test",
                role="",
                description="test",
                escalation_target="test",
            )

    def test_registration_description_min_length(self):
        """Test description must have at least 1 character."""
        with pytest.raises(ValidationError):
            SpecialistRegistration(
                name="test",
                role="test",
                description="",
                escalation_target="test",
            )

    def test_registration_escalation_target_min_length(self):
        """Test escalation_target must have at least 1 character."""
        with pytest.raises(ValidationError):
            SpecialistRegistration(
                name="test",
                role="test",
                description="test",
                escalation_target="",
            )

    def test_registration_extra_fields_forbidden(self):
        """Test SpecialistRegistration rejects extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            SpecialistRegistration(
                name="Test",
                role="test",
                description="test",
                escalation_target="target",
                extra_field="not allowed",
            )
        assert "extra_field" in str(exc_info.value)


# =============================================================================
# AgentDecision Tests
# =============================================================================

class TestAgentDecision:
    """Test cases for AgentDecision model."""

    def test_minimal_valid_decision(self):
        """Test AgentDecision with minimal required fields."""
        decision = AgentDecision(
            confidence=0.95,
            reasoning="This is the best approach",
            action="delegate",
        )
        assert decision.confidence == 0.95
        assert decision.reasoning == "This is the best approach"
        assert decision.action == "delegate"
        assert decision.payload == {}
        assert decision.estimated_cost_usd == 0.0
        assert decision.estimated_duration_seconds == 0
        assert decision.required_approvals == []

    def test_decision_with_all_fields(self):
        """Test AgentDecision with all fields populated."""
        decision = AgentDecision(
            confidence=0.87,
            reasoning="Multiple factors considered",
            action="complete",
            payload={"result": "success", "data": {"key": "value"}},
            estimated_cost_usd=1.50,
            estimated_duration_seconds=30,
            required_approvals=["manager", "security_lead"],
        )
        assert decision.confidence == 0.87
        assert decision.reasoning == "Multiple factors considered"
        assert decision.action == "complete"
        assert decision.payload == {"result": "success", "data": {"key": "value"}}
        assert decision.estimated_cost_usd == 1.50
        assert decision.estimated_duration_seconds == 30
        assert decision.required_approvals == ["manager", "security_lead"]

    def test_decision_confidence_minimum(self):
        """Test confidence must be >= 0.0."""
        with pytest.raises(ValidationError):
            AgentDecision(confidence=-0.1, reasoning="test", action="test")

    def test_decision_confidence_maximum(self):
        """Test confidence must be <= 1.0."""
        with pytest.raises(ValidationError):
            AgentDecision(confidence=1.1, reasoning="test", action="test")

    def test_decision_confidence_boundary_values(self):
        """Test confidence boundary values 0.0 and 1.0."""
        decision_min = AgentDecision(confidence=0.0, reasoning="test", action="test")
        assert decision_min.confidence == 0.0
        
        decision_max = AgentDecision(confidence=1.0, reasoning="test", action="test")
        assert decision_max.confidence == 1.0

    def test_decision_reasoning_min_length(self):
        """Test reasoning must have at least 1 character."""
        with pytest.raises(ValidationError):
            AgentDecision(confidence=0.5, reasoning="", action="test")

    def test_decision_action_min_length(self):
        """Test action must have at least 1 character."""
        with pytest.raises(ValidationError):
            AgentDecision(confidence=0.5, reasoning="test", action="")

    def test_decision_estimated_cost_minimum(self):
        """Test estimated_cost_usd must be >= 0.0."""
        with pytest.raises(ValidationError):
            AgentDecision(
                confidence=0.5,
                reasoning="test",
                action="test",
                estimated_cost_usd=-1.0,
            )

    def test_decision_estimated_duration_minimum(self):
        """Test estimated_duration_seconds must be >= 0."""
        with pytest.raises(ValidationError):
            AgentDecision(
                confidence=0.5,
                reasoning="test",
                action="test",
                estimated_duration_seconds=-1,
            )

    def test_decision_extra_fields_forbidden(self):
        """Test AgentDecision rejects extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            AgentDecision(
                confidence=0.5,
                reasoning="test",
                action="test",
                extra_field="not allowed",
            )
        assert "extra_field" in str(exc_info.value)

    def test_decision_payload_can_be_empty(self):
        """Test payload defaults to empty dict."""
        decision = AgentDecision(
            confidence=0.5,
            reasoning="test",
            action="test",
        )
        assert decision.payload == {}


# =============================================================================
# AgentMemory Tests
# =============================================================================

class TestAgentMemory:
    """Test cases for AgentMemory model."""

    def test_valid_memory_context(self):
        """Test AgentMemory with context type."""
        memory = AgentMemory(
            agent_id="agent-123",
            memory_type="context",
            content={"task": "current_task", "priority": "high"},
            timestamp="2024-01-15T10:30:00Z",
        )
        assert memory.agent_id == "agent-123"
        assert memory.memory_type == "context"
        assert memory.content == {"task": "current_task", "priority": "high"}
        assert memory.timestamp == "2024-01-15T10:30:00Z"
        assert memory.ttl is None

    def test_valid_memory_learning(self):
        """Test AgentMemory with learning type."""
        memory = AgentMemory(
            agent_id="agent-456",
            memory_type="learning",
            content={"pattern": "user_prefers_detailed"},
            timestamp="2024-01-15T11:00:00Z",
            ttl=86400,
        )
        assert memory.memory_type == "learning"
        assert memory.ttl == 86400

    def test_valid_memory_preference(self):
        """Test AgentMemory with preference type."""
        memory = AgentMemory(
            agent_id="agent-789",
            memory_type="preference",
            content={"theme": "dark", "language": "python"},
            timestamp="2024-01-15T12:00:00Z",
        )
        assert memory.memory_type == "preference"

    def test_valid_memory_interaction(self):
        """Test AgentMemory with interaction type."""
        memory = AgentMemory(
            agent_id="agent-abc",
            memory_type="interaction",
            content={"user_query": "help", "response": "assistance provided"},
            timestamp="2024-01-15T13:00:00Z",
        )
        assert memory.memory_type == "interaction"

    def test_memory_invalid_type(self):
        """Test AgentMemory rejects invalid memory_type."""
        with pytest.raises(ValidationError):
            AgentMemory(
                agent_id="agent-123",
                memory_type="invalid_type",
                content={},
                timestamp="2024-01-15T10:00:00Z",
            )

    def test_memory_agent_id_min_length(self):
        """Test agent_id must have at least 1 character."""
        with pytest.raises(ValidationError):
            AgentMemory(
                agent_id="",
                memory_type="context",
                content={},
                timestamp="2024-01-15T10:00:00Z",
            )

    def test_memory_extra_fields_forbidden(self):
        """Test AgentMemory rejects extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            AgentMemory(
                agent_id="agent-123",
                memory_type="context",
                content={},
                timestamp="2024-01-15T10:00:00Z",
                extra_field="not allowed",
            )
        assert "extra_field" in str(exc_info.value)


# =============================================================================
# ReviewStatus Type Tests
# =============================================================================

class TestReviewStatus:
    """Test cases for ReviewStatus Literal type."""

    def test_review_status_values(self):
        """Test ReviewStatus accepts valid values."""
        # These should all be valid Literal values
        verdict1 = ReviewVerdict(status="pass", summary="test")
        verdict2 = ReviewVerdict(status="retry", summary="test")
        verdict3 = ReviewVerdict(status="block", summary="test")
        assert verdict1.status == "pass"
        assert verdict2.status == "retry"
        assert verdict3.status == "block"

    @pytest.mark.parametrize("status", ["pass", "retry", "block"])
    def test_all_review_status_values(self, status):
        """Test all ReviewStatus values work."""
        verdict = ReviewVerdict(status=status, summary="test")
        assert verdict.status == status


# =============================================================================
# Model Export Tests
# =============================================================================

def test_all_models_exported():
    """Test that __all__ includes all expected models."""
    from src.services import agent_contracts
    
    expected_exports = [
        "AgentDecision",
        "AgentMemory",
        "DelegationDecision",
        "ReviewStatus",
        "ReviewVerdict",
        "SpecialistRegistration",
        "TaskProposal",
    ]
    
    for export in expected_exports:
        assert export in agent_contracts.__all__
        
    # Ensure no duplicates and all exports exist
    assert len(set(agent_contracts.__all__)) == len(agent_contracts.__all__)
