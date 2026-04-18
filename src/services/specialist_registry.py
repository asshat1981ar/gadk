from __future__ import annotations

from src.services.agent_contracts import SpecialistRegistration
from src.services.sdlc_phase import Phase


def _normalize_specialist_name(name: str) -> str:
    return name.strip().casefold()


#: Default ownership of each SDLC phase. Kept as module-level data so any
#: caller (PhaseController, CLI, tests) can look up the owning agent
#: without instantiating the registry. Extend here rather than in-line in
#: callers so the mapping stays a single source of truth.
DEFAULT_PHASE_OWNERS: dict[Phase, tuple[str, ...]] = {
    Phase.PLAN: ("Ideator",),
    Phase.ARCHITECT: ("Architect",),
    Phase.IMPLEMENT: ("Builder",),
    Phase.REVIEW: ("Critic",),
    Phase.GOVERN: ("Governor",),
    Phase.OPERATE: ("Pulse", "FinOps"),
}


class SpecialistRegistry:
    """In-memory registry for typed specialist onboarding contracts."""

    def __init__(self) -> None:
        self._registrations: dict[str, SpecialistRegistration] = {}
        self._phase_owners: dict[Phase, list[str]] = {
            phase: list(owners) for phase, owners in DEFAULT_PHASE_OWNERS.items()
        }

    # -- specialist contracts --------------------------------------------

    def register(self, registration: SpecialistRegistration) -> None:
        key = _normalize_specialist_name(registration.name)
        if key in self._registrations:
            raise ValueError(f"specialist '{registration.name}' is already registered")
        self._registrations[key] = registration

    def get(self, name: str) -> SpecialistRegistration | None:
        return self._registrations.get(_normalize_specialist_name(name))

    def list_all(self) -> list[SpecialistRegistration]:
        return list(self._registrations.values())

    # -- phase ownership -------------------------------------------------

    def owners_of(self, phase: Phase) -> list[str]:
        """Return the agents that own ``phase``."""
        return list(self._phase_owners.get(phase, ()))

    def assign_owner(self, phase: Phase, agent_name: str) -> None:
        """Append an additional owner to a phase. Idempotent."""
        owners = self._phase_owners.setdefault(phase, [])
        if agent_name not in owners:
            owners.append(agent_name)


__all__ = ["DEFAULT_PHASE_OWNERS", "SpecialistRegistry"]
