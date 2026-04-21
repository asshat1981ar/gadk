from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReviewStatus = Literal["pass", "retry", "block"]


class DelegationDecision(BaseModel):
    """Structured routing decision emitted by control and discovery roles."""

    model_config = ConfigDict(extra="forbid")

    target_agent: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    required_capabilities: list[str] = Field(default_factory=list)
    specialist_hint: str | None = None


class TaskProposal(BaseModel):
    """Structured proposal for work discovered by orchestration or specialists."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(default_factory=list)
    recommended_agent: str = Field(min_length=1)
    required_capabilities: list[str] = Field(default_factory=list)


class ReviewVerdict(BaseModel):
    """Typed review result for governance and downstream retry handling."""

    model_config = ConfigDict(extra="forbid")

    status: ReviewStatus
    summary: str = Field(min_length=1)
    concerns: list[str] = Field(default_factory=list)
    retry_reason: str | None = None
    recommended_actions: list[str] = Field(default_factory=list)


class SpecialistRegistration(BaseModel):
    """Typed onboarding contract for future specialist agents."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    description: str = Field(min_length=1)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    capability_needs: list[str] = Field(default_factory=list)
    escalation_target: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class AgentDecision(BaseModel):
    """Structured decision output for all agents with PydanticAI integration.

    This model provides a unified contract for agent handoffs, enabling
    typed decisions, confidence scoring, cost estimation, and approval workflows.
    """

    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(min_length=1, description="Detailed reasoning for the decision")
    action: str = Field(
        min_length=1, description="The action to take (e.g., 'delegate', 'complete', 'retry')"
    )
    payload: dict = Field(
        default_factory=dict, description="Structured data payload for the action"
    )
    estimated_cost_usd: float = Field(
        ge=0.0, default=0.0, description="Estimated cost in USD for this decision"
    )
    estimated_duration_seconds: int = Field(
        ge=0, default=0, description="Estimated duration in seconds"
    )
    required_approvals: list[str] = Field(
        default_factory=list, description="List of approval roles required (empty if none)"
    )


class AgentMemory(BaseModel):
    """Persistent memory entry for agents across sessions."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1, description="Unique agent identifier")
    memory_type: Literal["context", "learning", "preference", "interaction"] = Field(
        description="Type of memory entry"
    )
    content: dict = Field(description="Structured memory content")
    timestamp: str = Field(description="ISO 8601 timestamp")
    ttl: int | None = Field(
        default=None, description="Time-to-live in seconds (None for persistent)"
    )


__all__ = [
    "AgentDecision",
    "AgentMemory",
    "DelegationDecision",
    "ReviewStatus",
    "ReviewVerdict",
    "SpecialistRegistration",
    "TaskProposal",
]
