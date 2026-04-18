"""SDLC phase model and transition rules.

Defines the ordered set of SDLC phases a ``WorkItem`` traverses and the
default allowed transitions between them. The ``PhaseController`` in
``src/services/phase_controller.py`` uses these types; quality gates in
``src/services/quality_gates.py`` evaluate them.

Design notes:
- Phases form a DAG with one forward edge per pair plus a rework edge
  (REVIEW → IMPLEMENT) for bounded retry cycles. Skipping phases is
  rejected so the audit trail stays linear.
- ``WorkItem`` is intentionally minimal; richer domain fields live in
  the opaque ``payload`` dict so this module avoids coupling to any
  specific agent or task schema.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Phase(str, Enum):  # noqa: UP042 — keep str mixin for pydantic/JSON serialization
    """Ordered SDLC phases."""

    PLAN = "PLAN"
    ARCHITECT = "ARCHITECT"
    IMPLEMENT = "IMPLEMENT"
    REVIEW = "REVIEW"
    GOVERN = "GOVERN"
    OPERATE = "OPERATE"


#: Forward order used for progression checks. Index-based lookups make
#: "can I advance to X from Y?" a single comparison.
PHASE_ORDER: tuple[Phase, ...] = (
    Phase.PLAN,
    Phase.ARCHITECT,
    Phase.IMPLEMENT,
    Phase.REVIEW,
    Phase.GOVERN,
    Phase.OPERATE,
)


#: Allowed transitions: forward edge + one rework edge (REVIEW → IMPLEMENT).
#: Governors requesting a jump outside this set must do so explicitly with
#: ``PhaseController.advance(..., force=True)``.
ALLOWED_TRANSITIONS: dict[Phase, frozenset[Phase]] = {
    Phase.PLAN: frozenset({Phase.ARCHITECT}),
    Phase.ARCHITECT: frozenset({Phase.IMPLEMENT}),
    Phase.IMPLEMENT: frozenset({Phase.REVIEW}),
    Phase.REVIEW: frozenset({Phase.GOVERN, Phase.IMPLEMENT}),  # rework edge
    Phase.GOVERN: frozenset({Phase.OPERATE}),
    Phase.OPERATE: frozenset(),
}


class PhaseTransitionError(ValueError):
    """Raised when a requested transition violates :data:`ALLOWED_TRANSITIONS`."""


class PhaseHistoryEntry(BaseModel):
    """One recorded phase transition."""

    model_config = ConfigDict(extra="forbid")

    from_phase: Phase | None = None
    to_phase: Phase
    at: datetime
    reason: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class WorkItem(BaseModel):
    """A work item traversing the SDLC."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    phase: Phase = Phase.PLAN
    payload: dict[str, Any] = Field(default_factory=dict)
    history: list[PhaseHistoryEntry] = Field(default_factory=list)

    def record(self, to_phase: Phase, *, reason: str = "", evidence_refs: list[str] | None = None) -> None:
        """Append a history entry; the caller is responsible for mutating ``phase``."""
        self.history.append(
            PhaseHistoryEntry(
                from_phase=self.phase,
                to_phase=to_phase,
                at=datetime.now(UTC),
                reason=reason,
                evidence_refs=list(evidence_refs or []),
            )
        )


def can_advance(current: Phase, target: Phase) -> bool:
    """Return True iff ``current → target`` is in :data:`ALLOWED_TRANSITIONS`."""
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def next_phase(current: Phase) -> Phase | None:
    """Return the canonical forward phase from ``current`` (ignoring rework edge)."""
    try:
        idx = PHASE_ORDER.index(current)
    except ValueError:
        return None
    if idx + 1 >= len(PHASE_ORDER):
        return None
    return PHASE_ORDER[idx + 1]


__all__ = [
    "ALLOWED_TRANSITIONS",
    "PHASE_ORDER",
    "Phase",
    "PhaseHistoryEntry",
    "PhaseTransitionError",
    "WorkItem",
    "can_advance",
    "next_phase",
]
