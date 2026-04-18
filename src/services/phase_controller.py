"""Controller that advances ``WorkItem`` s through SDLC phases under gates.

Reuses:
- ``src.services.sdlc_phase`` for the phase model and transition rules.
- ``src.services.quality_gates`` for the pluggable evaluation surface.
- ``src.services.workflow_graphs.run_review_rework_cycle`` for the REVIEW
  → IMPLEMENT bounded retry decision (so phase-gate controller and
  existing review loops stay semantically consistent).
- ``src.state.StateManager`` for durable event logging via the existing
  ``events.jsonl`` append path.

Contract: ``advance(item, target)`` returns an ``AdvanceReport``. Blocking
gate failures leave the item's phase unchanged; advisory failures are
recorded but the transition still happens.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.observability.logger import get_logger
from src.services.quality_gates import GateResult, QualityGate
from src.services.sdlc_phase import (
    ALLOWED_TRANSITIONS,
    Phase,
    PhaseTransitionError,
    WorkItem,
)
from src.services.workflow_graphs import (
    ReviewLoopState,
    run_review_rework_cycle,
)
from src.state import StateManager

logger = get_logger("phase_controller")


@dataclass
class AdvanceReport:
    """Outcome of a single ``advance`` call."""

    item: WorkItem
    from_phase: Phase
    to_phase: Phase
    advanced: bool
    gates: list[GateResult] = field(default_factory=list)
    reason: str = ""

    def blocking_failures(self) -> list[GateResult]:
        return [g for g in self.gates if g.blocking and not g.passed]

    def advisory_failures(self) -> list[GateResult]:
        return [g for g in self.gates if not g.blocking and not g.passed]


class PhaseController:
    """Advance ``WorkItem`` s through phases, evaluating gates per transition."""

    def __init__(
        self,
        gates: Iterable[QualityGate] | None = None,
        state_manager: StateManager | None = None,
    ) -> None:
        self._gates: list[QualityGate] = list(gates or [])
        self._sm = state_manager

    def register(self, gate: QualityGate) -> None:
        self._gates.append(gate)

    # -- public API -------------------------------------------------------

    def advance(
        self,
        item: WorkItem,
        target: Phase,
        *,
        reason: str = "",
        force: bool = False,
    ) -> AdvanceReport:
        """Attempt to move ``item`` from its current phase to ``target``."""
        from_phase = item.phase
        if not force and target not in ALLOWED_TRANSITIONS.get(from_phase, frozenset()):
            raise PhaseTransitionError(f"disallowed transition {from_phase.value} → {target.value}")

        results = self._evaluate(item, target)
        blockers = [r for r in results if r.blocking and not r.passed]

        if blockers and not force:
            self._emit_event(
                item,
                action="phase.transition.blocked",
                from_phase=from_phase,
                to_phase=target,
                reason=reason or "blocked by gate",
                gates=results,
            )
            return AdvanceReport(
                item=item,
                from_phase=from_phase,
                to_phase=from_phase,
                advanced=False,
                gates=results,
                reason="blocked by gate: " + ", ".join(r.gate for r in blockers),
            )

        evidence_refs = [r.gate for r in results if r.passed]
        item.record(target, reason=reason, evidence_refs=evidence_refs)
        item.phase = target

        self._emit_event(
            item,
            action="phase.transition",
            from_phase=from_phase,
            to_phase=target,
            reason=reason,
            gates=results,
        )
        logger.info(
            "phase.transition task=%s %s -> %s gates_ok=%d gates_failed=%d",
            item.id,
            from_phase.value,
            target.value,
            sum(1 for r in results if r.passed),
            sum(1 for r in results if not r.passed),
        )
        return AdvanceReport(
            item=item,
            from_phase=from_phase,
            to_phase=target,
            advanced=True,
            gates=results,
            reason=reason,
        )

    def decide_rework(
        self,
        item: WorkItem,
        *,
        builder_attempts: int,
        review_status: str,
        latest_summary: str,
        max_retries: int = 2,
    ) -> str:
        """Wrap ``run_review_rework_cycle`` so callers in the REVIEW phase
        route consistently with the existing workflow-graph semantics.

        Returns one of ``"stop"``, ``"builder"``, ``"critic_stop"``.
        """
        decision = run_review_rework_cycle(
            ReviewLoopState(
                builder_attempts=builder_attempts,
                review_status=review_status,
                latest_summary=latest_summary,
            ),
            max_retries=max_retries,
        )
        self._emit_event(
            item,
            action="phase.review.decision",
            from_phase=item.phase,
            to_phase=item.phase,
            reason=decision.reason,
            gates=[],
        )
        return decision.next_step

    # -- internals --------------------------------------------------------

    def _evaluate(self, item: WorkItem, target: Phase) -> list[GateResult]:
        results: list[GateResult] = []
        for gate in self._gates:
            if not gate.should_run(target):
                continue
            try:
                results.append(gate.evaluate(item))
            except Exception as exc:
                logger.error("gate %s raised: %s", gate.name, exc, exc_info=True)
                results.append(
                    GateResult(
                        gate=gate.name,
                        passed=False,
                        blocking=gate.blocking,
                        evidence={"exception": type(exc).__name__},
                        message=f"gate crashed: {exc}",
                    )
                )
        return results

    def _emit_event(
        self,
        item: WorkItem,
        *,
        action: str,
        from_phase: Phase,
        to_phase: Phase,
        reason: str,
        gates: list[GateResult],
    ) -> None:
        if self._sm is None:
            return
        self._sm._append_event(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "task_id": item.id,
                "agent": "PhaseController",
                "action": action,
                "from_phase": from_phase.value,
                "to_phase": to_phase.value,
                "reason": reason,
                "gates": [
                    {
                        "gate": g.gate,
                        "passed": g.passed,
                        "blocking": g.blocking,
                        "message": g.message,
                    }
                    for g in gates
                ],
            }
        )


__all__ = ["AdvanceReport", "PhaseController"]
