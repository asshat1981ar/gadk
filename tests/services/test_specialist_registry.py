"""Tests for SpecialistRegistry phase-owner map."""

from __future__ import annotations

from src.services.agent_contracts import SpecialistRegistration
from src.services.sdlc_phase import Phase
from src.services.specialist_registry import DEFAULT_PHASE_OWNERS, SpecialistRegistry


def test_default_phase_owners_cover_every_phase() -> None:
    for phase in Phase:
        assert DEFAULT_PHASE_OWNERS.get(phase), f"missing owner for {phase}"


def test_owners_of_returns_default_mapping() -> None:
    reg = SpecialistRegistry()
    assert reg.owners_of(Phase.PLAN) == ["Ideator"]
    assert reg.owners_of(Phase.ARCHITECT) == ["Architect"]
    assert reg.owners_of(Phase.GOVERN) == ["Governor"]
    assert reg.owners_of(Phase.OPERATE) == ["Pulse", "FinOps"]


def test_assign_owner_appends_and_is_idempotent() -> None:
    reg = SpecialistRegistry()
    reg.assign_owner(Phase.GOVERN, "SecurityReviewer")
    reg.assign_owner(Phase.GOVERN, "SecurityReviewer")  # idempotent
    assert reg.owners_of(Phase.GOVERN) == ["Governor", "SecurityReviewer"]


def test_register_specialist_still_works() -> None:
    reg = SpecialistRegistry()
    reg.register(
        SpecialistRegistration(
            name="Reviewer",
            role="review",
            description="d",
            escalation_target="Orchestrator",
        )
    )
    assert reg.get("reviewer") is not None
    assert reg.get("missing") is None
