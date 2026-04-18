"""Tests for the phase-gated AutonomousSDLCEngine.

These tests mock the network-touching primitives (_discover, _plan,
_build, _review, _deliver, GitHubTool) so the migrated orchestration
can be exercised without real API calls. What they verify:

- Each phase transition emits exactly one `phase.transition` event.
- Early returns (no tasks, no artifact, review blocked, delivery
  crashed) do not trigger spurious transitions.
- The rework loop uses `controller.decide_rework` and advances to
  REVIEW only when the verdict is "pass".
- `register_external_gate` is called at the GOVERN step and its
  result is captured in the WorkItem payload.
- `save_work_item` is invoked at every exit path so state is durable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.phase_controller import PhaseController
from src.services.phase_store import load_work_item
from src.services.sdlc_phase import Phase
from src.state import StateManager


def _read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _transition_actions(events: list[dict]) -> list[str]:
    return [e["action"] for e in events if e.get("action", "").startswith("phase.")]


class _FakeGitHub:
    """Minimal stub mimicking the GitHubTool surface the engine uses."""

    async def list_pull_requests(self, state: str = "open") -> list:
        return []


@pytest.fixture
def engine_with_mocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Build an AutonomousSDLCEngine with filesystem + GitHub mocked out.

    The fixture yields a tuple of (engine, events_path) so tests can
    inspect the emitted `phase.transition` audit trail.
    """
    state_file = tmp_path / "state.json"
    events_file = tmp_path / "events.jsonl"
    sm = StateManager(
        storage_type="json",
        filename=str(state_file),
        event_filename=str(events_file),
    )
    controller = PhaseController(state_manager=sm)

    from src import autonomous_sdlc as mod

    engine = mod.AutonomousSDLCEngine.__new__(mod.AutonomousSDLCEngine)
    engine.sm = sm
    engine.gh = _FakeGitHub()
    engine.controller = controller
    engine.cycle = 0
    engine.tasks_completed = 0
    engine.tasks_failed = 0

    return engine, events_file


@pytest.mark.asyncio
async def test_full_happy_path_emits_every_phase_transition(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, events_file = engine_with_mocks

    async def _discover() -> list[dict]:
        return [{"title": "Add retries to dispatch", "priority": "HIGH", "description": "x"}]

    async def _plan(tasks: list) -> dict:
        return {
            "task_id": "sdlc-add-retries",
            "title": "Add retries to dispatch",
            "priority": "HIGH",
        }

    async def _build(task: dict) -> str:
        return "src/staged_agents/retries.py"

    async def _review(artifact: str, task: dict) -> str:
        return "Status: pass\n\nThe retries look good."

    async def _deliver(artifact: str, task: dict, review: str) -> str:
        return "https://github.com/example/repo/pull/42"

    monkeypatch.setattr(engine, "_discover", _discover)
    monkeypatch.setattr(engine, "_plan", _plan)
    monkeypatch.setattr(engine, "_build", _build)
    monkeypatch.setattr(engine, "_review", _review)
    monkeypatch.setattr(engine, "_deliver", _deliver)

    result = await engine.run_cycle()
    assert result is True
    assert engine.tasks_completed == 1
    assert engine.tasks_failed == 0

    # Five forward transitions: PLAN→ARCHITECT, ARCHITECT→IMPLEMENT,
    # IMPLEMENT→REVIEW (via decide_rework.stop), REVIEW→GOVERN, GOVERN→OPERATE.
    actions = _transition_actions(_read_events(events_file))
    assert actions.count("phase.transition") >= 5, f"expected 5+ transitions, got {actions}"
    # The rework decision event is also logged.
    assert "phase.review.decision" in actions

    # WorkItem persisted at OPERATE with the PR URL in the payload.
    item = load_work_item(engine.sm, "sdlc-add-retries")
    assert item is not None
    assert item.phase is Phase.OPERATE
    assert item.payload["pr_url"] == "https://github.com/example/repo/pull/42"


@pytest.mark.asyncio
async def test_no_tasks_discovered_returns_false_without_transitions(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, events_file = engine_with_mocks

    async def _discover() -> list[dict]:
        return []

    monkeypatch.setattr(engine, "_discover", _discover)

    result = await engine.run_cycle()
    assert result is False
    # No WorkItem created, no phase transitions emitted.
    assert _transition_actions(_read_events(events_file)) == []


@pytest.mark.asyncio
async def test_plan_returns_none_short_circuits(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, events_file = engine_with_mocks

    async def _discover() -> list[dict]:
        return [{"title": "whatever", "priority": "LOW"}]

    async def _plan(tasks: list) -> None:
        return None

    monkeypatch.setattr(engine, "_discover", _discover)
    monkeypatch.setattr(engine, "_plan", _plan)

    result = await engine.run_cycle()
    assert result is False
    assert _transition_actions(_read_events(events_file)) == []


@pytest.mark.asyncio
async def test_build_returns_none_advances_to_architect_then_fails(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, events_file = engine_with_mocks

    async def _discover() -> list[dict]:
        return [{"title": "X", "priority": "HIGH", "description": "x"}]

    async def _plan(tasks: list) -> dict:
        return {"task_id": "sdlc-x", "title": "X", "priority": "HIGH"}

    async def _build(task: dict) -> None:
        return None

    monkeypatch.setattr(engine, "_discover", _discover)
    monkeypatch.setattr(engine, "_plan", _plan)
    monkeypatch.setattr(engine, "_build", _build)

    result = await engine.run_cycle()
    assert result is False
    assert engine.tasks_failed == 1

    # PLAN→ARCHITECT happened (build gate is post-ARCHITECT), but no
    # further transitions since build returned None.
    events = _read_events(events_file)
    targets = [e.get("to_phase") for e in events if e.get("action") == "phase.transition"]
    assert targets == ["ARCHITECT"]

    item = load_work_item(engine.sm, "sdlc-x")
    assert item is not None
    assert item.phase is Phase.ARCHITECT


@pytest.mark.asyncio
async def test_review_blocked_does_not_advance_past_implement(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, events_file = engine_with_mocks

    async def _discover() -> list[dict]:
        return [{"title": "X", "priority": "HIGH", "description": "x"}]

    async def _plan(tasks: list) -> dict:
        return {"task_id": "sdlc-x", "title": "X"}

    async def _build(task: dict) -> str:
        return "src/staged_agents/x.py"

    async def _review(artifact: str, task: dict) -> str:
        return "Status: block\n\nThis is unsafe."

    monkeypatch.setattr(engine, "_discover", _discover)
    monkeypatch.setattr(engine, "_plan", _plan)
    monkeypatch.setattr(engine, "_build", _build)
    monkeypatch.setattr(engine, "_review", _review)

    result = await engine.run_cycle()
    assert result is False
    assert engine.tasks_failed == 1

    # Reached IMPLEMENT but not REVIEW.
    events = _read_events(events_file)
    targets = [e.get("to_phase") for e in events if e.get("action") == "phase.transition"]
    assert targets == ["ARCHITECT", "IMPLEMENT"]

    # REVIEW_BLOCKED state recorded.
    task_state = engine.sm.get_task("sdlc-x")
    assert task_state["status"] == "REVIEW_BLOCKED"


@pytest.mark.asyncio
async def test_review_retry_rebuilds_then_passes(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, events_file = engine_with_mocks
    build_calls = 0
    review_calls = 0

    async def _discover() -> list[dict]:
        return [{"title": "X", "priority": "HIGH", "description": "x"}]

    async def _plan(tasks: list) -> dict:
        return {"task_id": "sdlc-retry", "title": "X"}

    async def _build(task: dict) -> str:
        nonlocal build_calls
        build_calls += 1
        return f"src/staged_agents/attempt-{build_calls}.py"

    async def _review(artifact: str, task: dict) -> str:
        nonlocal review_calls
        review_calls += 1
        if review_calls == 1:
            return "Status: retry\n\nMissing docstring."
        return "Status: pass\n\nGood now."

    async def _deliver(artifact: str, task: dict, review: str) -> str:
        return "https://github.com/example/repo/pull/7"

    monkeypatch.setattr(engine, "_discover", _discover)
    monkeypatch.setattr(engine, "_plan", _plan)
    monkeypatch.setattr(engine, "_build", _build)
    monkeypatch.setattr(engine, "_review", _review)
    monkeypatch.setattr(engine, "_deliver", _deliver)

    result = await engine.run_cycle()
    assert result is True
    assert build_calls == 2, "rework loop must rebuild exactly once before the pass"
    assert review_calls == 2

    # Full five-transition ladder still reached.
    events = _read_events(events_file)
    targets = [e.get("to_phase") for e in events if e.get("action") == "phase.transition"]
    assert targets == ["ARCHITECT", "IMPLEMENT", "REVIEW", "GOVERN", "OPERATE"]


@pytest.mark.asyncio
async def test_delivery_crash_does_not_advance_to_operate(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, events_file = engine_with_mocks

    async def _discover() -> list[dict]:
        return [{"title": "X", "priority": "HIGH", "description": "x"}]

    async def _plan(tasks: list) -> dict:
        return {"task_id": "sdlc-deliver-fail", "title": "X"}

    async def _build(task: dict) -> str:
        return "src/staged_agents/x.py"

    async def _review(artifact: str, task: dict) -> str:
        return "Status: pass\n\nfine."

    async def _deliver(artifact: str, task: dict, review: str) -> str:
        raise RuntimeError("github 503")

    monkeypatch.setattr(engine, "_discover", _discover)
    monkeypatch.setattr(engine, "_plan", _plan)
    monkeypatch.setattr(engine, "_build", _build)
    monkeypatch.setattr(engine, "_review", _review)
    monkeypatch.setattr(engine, "_deliver", _deliver)

    result = await engine.run_cycle()
    assert result is False
    assert engine.tasks_failed == 1

    events = _read_events(events_file)
    targets = [e.get("to_phase") for e in events if e.get("action") == "phase.transition"]
    # ARCHITECT → IMPLEMENT → REVIEW → GOVERN, but NOT OPERATE (delivery failed).
    assert targets == ["ARCHITECT", "IMPLEMENT", "REVIEW", "GOVERN"]

    # FAILED state recorded with the reason.
    task_state = engine.sm.get_task("sdlc-deliver-fail")
    assert task_state["status"] == "FAILED"
    assert "github 503" in task_state["reason"]


@pytest.mark.asyncio
async def test_governance_gate_is_skipped_when_flag_off(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With Config.SDLC_MCP_ENABLED=false (the default), the governance
    verdict is recorded as `skipped` but the cycle still advances to
    OPERATE — dormancy doesn't block delivery."""
    from src.config import Config

    monkeypatch.setattr(Config, "SDLC_MCP_ENABLED", False)
    engine, _ = engine_with_mocks

    async def _discover() -> list[dict]:
        return [{"title": "X", "priority": "HIGH", "description": "x"}]

    async def _plan(tasks: list) -> dict:
        return {"task_id": "sdlc-gov-skip", "title": "X"}

    async def _build(task: dict) -> str:
        return "src/staged_agents/x.py"

    async def _review(artifact: str, task: dict) -> str:
        return "Status: pass"

    async def _deliver(artifact: str, task: dict, review: str) -> str:
        return "https://github.com/example/repo/pull/99"

    for name, fn in {
        "_discover": _discover,
        "_plan": _plan,
        "_build": _build,
        "_review": _review,
        "_deliver": _deliver,
    }.items():
        monkeypatch.setattr(engine, name, fn)

    result = await engine.run_cycle()
    assert result is True

    item = load_work_item(engine.sm, "sdlc-gov-skip")
    assert item is not None
    assert item.payload["governance"]["status"] == "sdlc.gate.skipped"


def test_legacy_modules_are_deleted() -> None:
    """Batch B-5: the parallel legacy engines must be gone from the tree.

    Their removal is part of the phase-gated consolidation; if anything
    re-introduces them the import will succeed and this test will fail.
    """
    import importlib

    for modname in (
        "src.planned_main",
        "src.chimera_ideation",
        "src.android_rpg_sdlc",
    ):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(modname)


# ---------------------------------------------------------------------------
# Batch F: ARCHITECT-phase ADR synthesis
# ---------------------------------------------------------------------------


def test_architecture_note_from_task_produces_valid_adr() -> None:
    """Happy path: task with title + description + priority yields a
    populated ADR payload with the expected audit fields."""
    from src.autonomous_sdlc import _architecture_note_from_task

    adr = _architecture_note_from_task(
        {
            "task_id": "sdlc-add-x",
            "title": "Add X to Y",
            "description": "The X feature is missing from Y.",
            "priority": "HIGH",
            "file_hint": "src/y.py",
        }
    )
    assert adr is not None
    assert adr["title"] == "Add X to Y"
    assert "X feature is missing" in adr["context"]
    assert any("HIGH" in c for c in adr["consequences"])
    assert adr["touched_paths"] == ["src/y.py"]
    assert adr["alternatives_considered"]


def test_architecture_note_from_task_returns_none_when_missing_fields() -> None:
    """Degraded path: tasks that lack the minimum fields for an ADR
    are rejected, so the caller can degrade to a forced-skip rather
    than halt the cycle with a pydantic ValidationError."""
    from src.autonomous_sdlc import _architecture_note_from_task

    # Missing title
    assert _architecture_note_from_task({"task_id": "x", "description": "d"}) is None
    # Missing description
    assert _architecture_note_from_task({"task_id": "x", "title": "t"}) is None
    # Blank title and description
    assert _architecture_note_from_task({"task_id": "x", "title": "", "description": ""}) is None


@pytest.mark.asyncio
async def test_run_cycle_stores_adr_in_payload(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ARCHITECT transition stashes the synthesized ADR on the
    WorkItem so the audit trail ties each PR back to its rationale."""
    engine, _ = engine_with_mocks

    async def _discover() -> list[dict]:
        return [
            {
                "title": "Add retries",
                "priority": "HIGH",
                "description": "dispatch needs retries",
                "file_hint": "src/tools/dispatcher.py",
            }
        ]

    async def _plan(tasks: list) -> dict:
        return {
            "task_id": "sdlc-retries",
            "title": "Add retries",
            "priority": "HIGH",
            "description": "dispatch needs retries",
            "file_hint": "src/tools/dispatcher.py",
        }

    async def _build(task: dict) -> str:
        return "src/staged_agents/retries.py"

    async def _review(artifact: str, task: dict) -> str:
        return "Status: pass"

    async def _deliver(artifact: str, task: dict, review: str) -> str:
        return "https://example/pr/1"

    for name, fn in {
        "_discover": _discover,
        "_plan": _plan,
        "_build": _build,
        "_review": _review,
        "_deliver": _deliver,
    }.items():
        monkeypatch.setattr(engine, name, fn)

    result = await engine.run_cycle()
    assert result is True

    item = load_work_item(engine.sm, "sdlc-retries")
    assert item is not None
    assert "architecture" in item.payload
    assert item.payload["architecture"]["title"] == "Add retries"
    assert item.payload["architecture"]["touched_paths"] == ["src/tools/dispatcher.py"]


@pytest.mark.asyncio
async def test_run_cycle_degrades_when_adr_synthesis_fails(
    engine_with_mocks, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A task with missing description should force-skip ARCHITECT
    (emits the degraded warning) but still advance the cycle. The
    skip must still emit a `phase.transition` event so the audit
    trail shows the ARCHITECT step happened."""
    engine, events_file = engine_with_mocks

    async def _discover() -> list[dict]:
        return [{"title": "X", "priority": "HIGH"}]  # no description

    async def _plan(tasks: list) -> dict:
        # task_id present, title present, description MISSING → ADR fails
        return {"task_id": "sdlc-no-desc", "title": "X", "priority": "HIGH"}

    async def _build(task: dict) -> str:
        return "src/staged_agents/x.py"

    async def _review(artifact: str, task: dict) -> str:
        return "Status: pass"

    async def _deliver(artifact: str, task: dict, review: str) -> str:
        return "https://example/pr/2"

    for name, fn in {
        "_discover": _discover,
        "_plan": _plan,
        "_build": _build,
        "_review": _review,
        "_deliver": _deliver,
    }.items():
        monkeypatch.setattr(engine, name, fn)

    result = await engine.run_cycle()
    assert result is True  # cycle completes despite ADR synthesis failure

    item = load_work_item(engine.sm, "sdlc-no-desc")
    assert item is not None
    # ARCHITECT transition still fired (forced skip).
    events = _read_events(events_file)
    targets = [e.get("to_phase") for e in events if e.get("action") == "phase.transition"]
    assert "ARCHITECT" in targets
    # But payload has no `architecture` key since synthesis degraded.
    assert "architecture" not in item.payload
