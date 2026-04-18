from __future__ import annotations

from src.services.agent_contracts import SpecialistRegistration


def _normalize_specialist_name(name: str) -> str:
    return name.strip().casefold()


class SpecialistRegistry:
    """In-memory registry for typed specialist onboarding contracts."""

    def __init__(self) -> None:
        self._registrations: dict[str, SpecialistRegistration] = {}

    def register(self, registration: SpecialistRegistration) -> None:
        key = _normalize_specialist_name(registration.name)
        if key in self._registrations:
            raise ValueError(f"specialist '{registration.name}' is already registered")
        self._registrations[key] = registration

    def get(self, name: str) -> SpecialistRegistration | None:
        return self._registrations.get(_normalize_specialist_name(name))

    def list_all(self) -> list[SpecialistRegistration]:
        return list(self._registrations.values())


__all__ = ["SpecialistRegistry"]
