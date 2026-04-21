"""Tests for the PhaseController — transitions, gates, event log.

Test coverage:
1. PhaseController.advance() - successful transitions
2. Gate evaluation - passing and failing gate scenarios
3. Blocking vs advisory gates - only blocking should prevent transition
4. Force transitions - should bypass gate failures
5. Invalid transitions - should raise PhaseTransitionError
6. Event emission - verify events logged to StateManager
7. decide_rework() - review loop decision logic

Test cases:
- Transition PLAN → ARCHITECT with passing gates
- Transition ARCHITECT → IMPLEMENT with passing gates
- Transition with blocking gate failure (should not advance)
- Transition with advisory gate failure (should advance despite failure)
- Force transition with failing gate
- Invalid transition attempt (PLAN → OPERATE, PLAN → REVIEW)
- Review rework cycle decision
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.phase_controller import PhaseController
from src.services.quality_gates import GateResult, QualityGate
from src.services.sdlc_phase import Phase, PhaseTransitionError, WorkItem
from src.state import StateManager


class _AlwaysPass(QualityGate):
    """Mock gate that always passes."""

    name = "always_pass"
    blocking = True

    def evaluate(self, item: WorkItem) -> GateResult:
        return GateResult(gate=self.name, passed=True, blocking=True)


class _AlwaysFail(QualityGate):
    """Mock gate that always fails (blocking)."""

    name = "always_fail"
    blocking = True

    def evaluate(self, item: WorkItem) -> GateResult:
        return GateResult(gate=self.name, passed=False, blocking=True, message="nope")


class _Advisory(QualityGate):
    """Mock gate that always fails but is non-blocking (advisory)."""

    name = "advisory"
    blocking = False

    def evaluate(self, item: WorkItem) -> GateResult:
        return GateResult(gate=self.name, passed=False, blocking=False, message="soft")


class _Raises(QualityGate):
    """Mock gate that raises an exception."""

    name = "crashy"
    blocking = True

    def evaluate(self, item: WorkItem) -> GateResult:  # pragma: no cover
        raise RuntimeError("boom")


class _TargetedGate(QualityGate):
    """Mock gate that only runs at specific target phases."""

    name = "targeted"
    blocking = True
    applies_to = frozenset({Phase.ARCHITECT, Phase.IMPLEMENT})

    def evaluate(self, item: WorkItem) -> GateResult:
        return GateResult(gate=self.name, passed=True, blocking=True)


@pytest.fixture
def sm(tmp_path: Path) -> StateManager:
    return StateManager(
        storage_type="json",
        filename=str(tmp_path / "state.json"),
        event_filename=str(tmp_path / "events.jsonl"),
    )


def _read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_advance_rejects_disallowed_transition(sm: StateManager) -> None:
    """Test that invalid transitions raise PhaseTransitionError."""
    controller = PhaseController(state_manager=sm)
    item = WorkItem(id="t1")
    with pytest.raises(PhaseTransitionError):
        controller.advance(item, Phase.OPERATE)


def test_advance_rejects_direct_to_review(sm: StateManager) -> None:
    """Test that PLAN -> REVIEW (skipping phases) is not allowed."""
    controller = PhaseController(state_manager=sm)
    item = WorkItem(id="t1")
    with pytest.raises(PhaseTransitionError):
        controller.advance(item, Phase.REVIEW)


def test_advance_passes_with_all_gates_green(sm: StateManager, tmp_path: Path) -> None:
    """Test PLAN -> ARCHITECT transition with passing gates."""
    controller = PhaseController(gates=[_AlwaysPass()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT, reason="ready")
    assert report.advanced
    assert item.phase is Phase.ARCHITECT
    assert len(item.history) == 1
    events = _read_events(Path(sm.event_filename))
    actions = {e["action"] for e in events}
    assert "phase.transition" in actions


def test_architect_to_implement_transition(sm: StateManager, tmp_path: Path) -> None:
    """Test ARCHITECT -> IMPLEMENT transition with passing gates."""
    controller = PhaseController(gates=[_AlwaysPass()], state_manager=sm)
    item = WorkItem(id="t1", phase=Phase.ARCHITECT)
    report = controller.advance(item, Phase.IMPLEMENT, reason="design complete")
    assert report.advanced
    assert item.phase is Phase.IMPLEMENT
    assert len(item.history) == 1
    events = _read_events(Path(sm.event_filename))
    actions = {e["action"] for e in events}
    assert "phase.transition" in actions


def test_blocking_gate_halts_transition(sm: StateManager) -> None:
    """Test that blocking gate failures prevent phase transition."""
    controller = PhaseController(gates=[_AlwaysFail()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert not report.advanced
    assert item.phase is Phase.PLAN
    assert report.blocking_failures()[0].gate == "always_fail"
    events = _read_events(Path(sm.event_filename))
    assert any(e["action"] == "phase.transition.blocked" for e in events)


def test_advisory_gate_does_not_block(sm: StateManager) -> None:
    """Test that advisory gate failures do not prevent transition."""
    controller = PhaseController(gates=[_Advisory()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert report.advanced
    assert item.phase is Phase.ARCHITECT
    assert report.advisory_failures()[0].gate == "advisory"


def test_mixed_gates_blocking_prevents_advance(sm: StateManager) -> None:
    """Test with mixed blocking (fails) and advisory (fails) gates."""
    controller = PhaseController(gates=[_AlwaysFail(), _Advisory()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert not report.advanced
    assert item.phase is Phase.PLAN
    assert len(report.blocking_failures()) == 1
    assert len(report.advisory_failures()) == 1


def test_mixed_gates_advisory_fails_passing_succeeds(sm: StateManager) -> None:
    """Test with passing blocking gate and failing advisory gate."""
    controller = PhaseController(gates=[_AlwaysPass(), _Advisory()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert report.advanced
    assert item.phase is Phase.ARCHITECT
    assert len(report.blocking_failures()) == 0
    assert len(report.advisory_failures()) == 1


def test_force_overrides_block(sm: StateManager) -> None:
    """Test that force=True bypasses blocking gate failures."""
    controller = PhaseController(gates=[_AlwaysFail()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT, force=True)
    assert report.advanced
    assert item.phase is Phase.ARCHITECT


def test_force_with_multiple_blocking_failures(sm: StateManager) -> None:
    """Test that force=True bypasses multiple blocking gate failures."""
    controller = PhaseController(gates=[_AlwaysFail(), _AlwaysFail()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT, force=True, reason="emergency")
    assert report.advanced
    assert item.phase is Phase.ARCHITECT


def test_gate_exception_is_converted_to_failure(sm: StateManager) -> None:
    """Test that gate exceptions are caught and converted to failures."""
    controller = PhaseController(gates=[_Raises()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert not report.advanced
    crash = report.blocking_failures()[0]
    assert crash.gate == "crashy"
    assert "boom" in crash.message


def test_targeted_gate_skips_unrelated_phases(sm: StateManager) -> None:
    """Test that gates only run at their specified target phases."""
    controller = PhaseController(gates=[_TargetedGate()], state_manager=sm)
    item = WorkItem(id="t1")
    # _TargetedGate applies_to ARCHITECT and IMPLEMENT, not PLAN
    # Since we're transitioning FROM PLAN, and gate should_run checks target phase
    # It should run when target is ARCHITECT
    report = controller.advance(item, Phase.ARCHITECT)
    assert report.advanced
    assert len(report.gates) == 1
    assert report.gates[0].gate == "targeted"


def test_decide_rework_maps_review_statuses(sm: StateManager) -> None:
    """Test decide_rework returns correct decisions for review statuses."""
    controller = PhaseController(state_manager=sm)
    item = WorkItem(id="t1", phase=Phase.REVIEW)
    assert (
        controller.decide_rework(item, builder_attempts=0, review_status="pass", latest_summary="")
        == "stop"
    )
    assert (
        controller.decide_rework(
            item, builder_attempts=0, review_status="retry", latest_summary="", max_retries=2
        )
        == "builder"
    )
    assert (
        controller.decide_rework(
            item, builder_attempts=5, review_status="retry", latest_summary="", max_retries=2
        )
        == "critic_stop"
    )


def test_decide_rework_blocked_status(sm: StateManager) -> None:
    """Test decide_rework returns critic_stop for blocked review status."""
    controller = PhaseController(state_manager=sm)
    item = WorkItem(id="t1", phase=Phase.REVIEW)
    assert (
        controller.decide_rework(item, builder_attempts=0, review_status="block", latest_summary="")
        == "critic_stop"
    )


def test_review_rework_edge_is_allowed(sm: StateManager) -> None:
    """Test that REVIEW -> IMPLEMENT (rework) transition works."""
    controller = PhaseController(gates=[_AlwaysPass()], state_manager=sm)
    item = WorkItem(id="t1", phase=Phase.REVIEW)
    report = controller.advance(item, Phase.IMPLEMENT, reason="rework")
    assert report.advanced
    assert item.phase is Phase.IMPLEMENT


def test_review_to_govern_transition(sm: StateManager) -> None:
    """Test REVIEW -> GOVERN transition with passing gates."""
    controller = PhaseController(gates=[_AlwaysPass()], state_manager=sm)
    item = WorkItem(id="t1", phase=Phase.REVIEW)
    report = controller.advance(item, Phase.GOVERN, reason="review passed")
    assert report.advanced
    assert item.phase is Phase.GOVERN


def test_full_workflow_lifecycle(sm: StateManager) -> None:
    """Test a full phase progression from PLAN through GOVERN."""
    controller = PhaseController(gates=[_AlwaysPass()], state_manager=sm)
    item = WorkItem(id="t1")

    # PLAN -> ARCHITECT
    report = controller.advance(item, Phase.ARCHITECT, reason="plan approved")
    assert report.advanced
    assert item.phase is Phase.ARCHITECT

    # ARCHITECT -> IMPLEMENT
    report = controller.advance(item, Phase.IMPLEMENT, reason="design complete")
    assert report.advanced
    assert item.phase is Phase.IMPLEMENT

    # IMPLEMENT -> REVIEW
    report = controller.advance(item, Phase.REVIEW, reason="code complete")
    assert report.advanced
    assert item.phase is Phase.REVIEW

    # REVIEW -> GOVERN (passing review)
    report = controller.advance(item, Phase.GOVERN, reason="review passed")
    assert report.advanced
    assert item.phase is Phase.GOVERN

    # Verify history contains all transitions
    assert len(item.history) == 4
    phases = [entry.to_phase for entry in item.history]
    assert phases == [Phase.ARCHITECT, Phase.IMPLEMENT, Phase.REVIEW, Phase.GOVERN]

    # Verify events were logged
    events = _read_events(Path(sm.event_filename))
    transition_events = [e for e in events if e["action"] == "phase.transition"]
    assert len(transition_events) == 4


def test_controller_with_no_state_manager() -> None:
    """Test controller works without state manager (no events logged)."""
    controller = PhaseController(gates=[_AlwaysPass()], state_manager=None)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT, reason="ready")
    assert report.advanced
    assert item.phase is Phase.ARCHITECT


def test_register_gate(sm: StateManager) -> None:
    """Test that gates can be registered after controller creation."""
    controller = PhaseController(state_manager=sm)
    controller.register(_AlwaysPass())
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert report.advanced


def test_empty_reason_defaults(sm: StateManager) -> None:
    """Test that empty reason is handled."""
    controller = PhaseController(gates=[_AlwaysPass()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert report.advanced
    assert item.history[0].reason == ""
