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


__all__ = [
    "DelegationDecision",
    "ReviewStatus",
    "ReviewVerdict",
    "SpecialistRegistration",
    "TaskProposal",
]
