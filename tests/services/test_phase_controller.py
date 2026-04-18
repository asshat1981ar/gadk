"""Tests for the PhaseController — transitions, gates, event log."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.phase_controller import PhaseController
from src.services.quality_gates import GateResult, QualityGate
from src.services.sdlc_phase import Phase, PhaseTransitionError, WorkItem
from src.state import StateManager


class _AlwaysPass(QualityGate):
    name = "always_pass"
    blocking = True

    def evaluate(self, item: WorkItem) -> GateResult:
        return GateResult(gate=self.name, passed=True, blocking=True)


class _AlwaysFail(QualityGate):
    name = "always_fail"
    blocking = True

    def evaluate(self, item: WorkItem) -> GateResult:
        return GateResult(gate=self.name, passed=False, blocking=True, message="nope")


class _Advisory(QualityGate):
    name = "advisory"
    blocking = False

    def evaluate(self, item: WorkItem) -> GateResult:
        return GateResult(gate=self.name, passed=False, blocking=False, message="soft")


class _Raises(QualityGate):
    name = "crashy"
    blocking = True

    def evaluate(self, item: WorkItem) -> GateResult:  # pragma: no cover
        raise RuntimeError("boom")


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
    controller = PhaseController(state_manager=sm)
    item = WorkItem(id="t1")
    with pytest.raises(PhaseTransitionError):
        controller.advance(item, Phase.OPERATE)


def test_advance_passes_with_all_gates_green(sm: StateManager, tmp_path: Path) -> None:
    controller = PhaseController(gates=[_AlwaysPass()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT, reason="ready")
    assert report.advanced
    assert item.phase is Phase.ARCHITECT
    assert len(item.history) == 1
    events = _read_events(Path(sm.event_filename))
    actions = {e["action"] for e in events}
    assert "phase.transition" in actions


def test_blocking_gate_halts_transition(sm: StateManager) -> None:
    controller = PhaseController(gates=[_AlwaysFail()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert not report.advanced
    assert item.phase is Phase.PLAN
    assert report.blocking_failures()[0].gate == "always_fail"
    events = _read_events(Path(sm.event_filename))
    assert any(e["action"] == "phase.transition.blocked" for e in events)


def test_advisory_gate_does_not_block(sm: StateManager) -> None:
    controller = PhaseController(gates=[_Advisory()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert report.advanced
    assert item.phase is Phase.ARCHITECT
    assert report.advisory_failures()[0].gate == "advisory"


def test_force_overrides_block(sm: StateManager) -> None:
    controller = PhaseController(gates=[_AlwaysFail()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT, force=True)
    assert report.advanced
    assert item.phase is Phase.ARCHITECT


def test_gate_exception_is_converted_to_failure(sm: StateManager) -> None:
    controller = PhaseController(gates=[_Raises()], state_manager=sm)
    item = WorkItem(id="t1")
    report = controller.advance(item, Phase.ARCHITECT)
    assert not report.advanced
    crash = report.blocking_failures()[0]
    assert crash.gate == "crashy"
    assert "boom" in crash.message


def test_decide_rework_maps_review_statuses(sm: StateManager) -> None:
    controller = PhaseController(state_manager=sm)
    item = WorkItem(id="t1", phase=Phase.REVIEW)
    assert controller.decide_rework(
        item, builder_attempts=0, review_status="pass", latest_summary=""
    ) == "stop"
    assert controller.decide_rework(
        item, builder_attempts=0, review_status="retry", latest_summary="", max_retries=2
    ) == "builder"
    assert controller.decide_rework(
        item, builder_attempts=5, review_status="retry", latest_summary="", max_retries=2
    ) == "critic_stop"


def test_review_rework_edge_is_allowed(sm: StateManager) -> None:
    controller = PhaseController(gates=[_AlwaysPass()], state_manager=sm)
    item = WorkItem(id="t1", phase=Phase.REVIEW)
    report = controller.advance(item, Phase.IMPLEMENT, reason="rework")
    assert report.advanced
    assert item.phase is Phase.IMPLEMENT
