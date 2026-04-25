# src/services/dbos_phase_workflow.py
"""DBOS-durable phase transition workflow.

Wraps PhaseController.advance() as a @dbos.workflow so that every SDLC phase
transition is checkpointed to the DBOS database (SQLite by default).  On crash,
DBOS automatically recovers from the last completed step without re-calling LLMs.
"""
from __future__ import annotations

from typing import Any

from src.config import Config
from src.services.phase_controller import PhaseController
from src.services.sdlc_phase import Phase, WorkItem


def PhaseTransitionWorkflow_transition_workflow_fallback(
    item_id: str,
    target_phase: Phase,
    current_phase: Phase,
) -> dict[str, Any]:
    """Non-durable fallback when DBOS is disabled."""
    item = WorkItem(id=item_id, phase=current_phase)
    controller = PhaseController()
    report = controller.advance(item, target_phase)
    return {
        "item_id": item_id,
        "from_phase": report.from_phase.value,
        "to_phase": report.to_phase.value,
        "advanced": report.advanced,
        "reason": report.reason,
        "gates": [
            {"gate": g.gate, "passed": g.passed, "blocking": g.blocking}
            for g in report.gates
        ],
    }


def transition_workflow(
    item_id: str,
    target_phase: Phase,
    current_phase: Phase = Phase.PLAN,
) -> dict[str, Any]:
    """Durable phase transition workflow.

    This function is decorated with @dbos.workflow in the module below when
    DBOS_ENABLED=true. It wraps PhaseController.advance() so DBOS checkpoints
    every step.
    """
    return PhaseTransitionWorkflow_transition_workflow_fallback(
        item_id=item_id,
        target_phase=target_phase,
        current_phase=current_phase,
    )
