import importlib

import pytest
from pydantic import ValidationError

import src.config as config_module
from src.services.agent_contracts import (
    DelegationDecision,
    ReviewVerdict,
    SpecialistRegistration,
    TaskProposal,
)
from src.services.specialist_registry import SpecialistRegistry


def _reload_config_module(monkeypatch):
    return importlib.reload(config_module)


class TestAgentContracts:
    def test_delegation_decision_requires_target_agent(self):
        decision = DelegationDecision(
            target_agent="Critic",
            reason="needs structured review",
            required_capabilities=["repo.read_file"],
        )

        assert decision.target_agent == "Critic"
        assert decision.required_capabilities == ["repo.read_file"]
        assert decision.specialist_hint is None

    def test_task_proposal_preserves_acceptance_criteria(self):
        proposal = TaskProposal(
            title="Add typed specialist contract",
            summary="Create shared models for specialist onboarding",
            description="Introduce additive Pydantic models for downstream services.",
            acceptance_criteria=[
                "specialists declare inputs",
                "specialists declare outputs",
            ],
            recommended_agent="Builder",
            required_capabilities=["repo.read_file", "repo.write_file"],
        )

        assert proposal.acceptance_criteria == [
            "specialists declare inputs",
            "specialists declare outputs",
        ]
        assert proposal.required_capabilities == ["repo.read_file", "repo.write_file"]

    def test_review_verdict_preserves_retry_reason(self):
        verdict = ReviewVerdict(
            status="retry",
            summary="missing schema validation",
            retry_reason="builder omitted required contract fields",
            recommended_actions=["add validation for specialist inputs"],
        )

        assert verdict.status == "retry"
        assert verdict.retry_reason == "builder omitted required contract fields"
        assert verdict.recommended_actions == ["add validation for specialist inputs"]

    def test_review_verdict_rejects_unknown_status(self):
        with pytest.raises(ValidationError):
            ReviewVerdict(status="unknown", summary="bad status")

    def test_specialist_registration_captures_onboarding_contract(self):
        registration = SpecialistRegistration(
            name="Architecture Specialist",
            role="architecture-review",
            description="Reviews module boundaries and integration seams.",
            inputs=["task proposal", "repo context"],
            outputs=["architecture recommendations"],
            capability_needs=["repo.read_file"],
            escalation_target="Orchestrator",
            tags=["architecture", "review"],
        )

        assert registration.inputs == ["task proposal", "repo context"]
        assert registration.outputs == ["architecture recommendations"]
        assert registration.capability_needs == ["repo.read_file"]


class TestSpecialistRegistry:
    def test_specialist_registry_registers_and_resolves_specialist(self):
        registry = SpecialistRegistry()
        registration = SpecialistRegistration(
            name="Architecture Specialist",
            role="architecture-review",
            description="Reviews module boundaries and integration seams.",
            inputs=["task proposal"],
            outputs=["review verdict"],
            capability_needs=["repo.read_file"],
            escalation_target="Orchestrator",
        )

        registry.register(registration)

        assert registry.get("architecture specialist") == registration
        assert registry.list_all() == [registration]

    def test_specialist_registry_rejects_duplicate_registration(self):
        registry = SpecialistRegistry()
        registration = SpecialistRegistration(
            name="Architecture Specialist",
            role="architecture-review",
            description="Reviews module boundaries and integration seams.",
            inputs=["task proposal"],
            outputs=["review verdict"],
            capability_needs=["repo.read_file"],
            escalation_target="Orchestrator",
        )

        registry.register(registration)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(
                SpecialistRegistration(
                    name=" architecture specialist ",
                    role="architecture-review",
                    description="Duplicate entry with different spacing and case.",
                    inputs=["task proposal"],
                    outputs=["review verdict"],
                    capability_needs=["repo.read_file"],
                    escalation_target="Orchestrator",
                )
            )


class TestTaskOneConfigFlags:
    def test_settings_parse_framework_feature_flags(self, monkeypatch):
        monkeypatch.setenv("PYDANTIC_AI_ENABLED", "true")
        monkeypatch.setenv("INSTRUCTOR_ENABLED", "true")
        monkeypatch.setenv("LANGGRAPH_ENABLED", "false")

        settings = config_module.Settings(_env_file=None)

        assert settings.pydantic_ai_enabled is True
        assert settings.instructor_enabled is True
        assert settings.langgraph_enabled is False

    def test_config_preserves_legacy_uppercase_feature_flags(self, monkeypatch):
        monkeypatch.setenv("PYDANTIC_AI_ENABLED", "true")
        monkeypatch.setenv("INSTRUCTOR_ENABLED", "false")
        monkeypatch.setenv("LANGGRAPH_ENABLED", "true")

        module = _reload_config_module(monkeypatch)

        assert module.Config.PYDANTIC_AI_ENABLED is True
        assert module.Config.INSTRUCTOR_ENABLED is False
        assert module.Config.LANGGRAPH_ENABLED is True
