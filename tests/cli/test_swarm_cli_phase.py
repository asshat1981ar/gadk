"""Tests for swarm_cli `phase` and `self-prompt` subcommands."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cli import swarm_cli
from src.config import Config
from src.services.phase_store import load_work_item, save_work_item
from src.services.sdlc_phase import Phase, WorkItem


@pytest.fixture
def tmp_state(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "state.json", tmp_path / "events.jsonl"


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    rc = swarm_cli.main(list(argv))
    out = capsys.readouterr().out
    return rc, out


def test_phase_status_missing_task(
    capsys: pytest.CaptureFixture[str], tmp_state: tuple[Path, Path]
) -> None:
    state, events = tmp_state
    rc, out = _run(
        capsys,
        "phase",
        "status",
        "nope",
        "--state-file",
        str(state),
        "--events-file",
        str(events),
    )
    assert rc == 1
    assert "No work item" in out


def test_phase_advance_creates_and_moves(
    capsys: pytest.CaptureFixture[str], tmp_state: tuple[Path, Path]
) -> None:
    state, events = tmp_state
    rc, out = _run(
        capsys,
        "phase",
        "advance",
        "task-a",
        "ARCHITECT",
        "--no-gates",
        "--state-file",
        str(state),
        "--events-file",
        str(events),
    )
    assert rc == 0
    assert "PLAN -> ARCHITECT" in out

    # Status now shows the new phase + one history entry.
    rc, status_out = _run(
        capsys,
        "phase",
        "status",
        "task-a",
        "--state-file",
        str(state),
        "--events-file",
        str(events),
    )
    assert rc == 0
    assert "Current phase: ARCHITECT" in status_out
    assert "PLAN -> ARCHITECT" in status_out


def test_phase_advance_rejects_disallowed_transition(
    capsys: pytest.CaptureFixture[str], tmp_state: tuple[Path, Path]
) -> None:
    state, events = tmp_state
    rc, out = _run(
        capsys,
        "phase",
        "advance",
        "task-b",
        "OPERATE",
        "--no-gates",
        "--state-file",
        str(state),
        "--events-file",
        str(events),
    )
    assert rc == 1
    assert "Disallowed transition" in out


def test_phase_advance_rejects_unknown_phase(
    capsys: pytest.CaptureFixture[str], tmp_state: tuple[Path, Path]
) -> None:
    state, events = tmp_state
    rc, out = _run(
        capsys,
        "phase",
        "advance",
        "task-c",
        "MYSTERY",
        "--no-gates",
        "--state-file",
        str(state),
        "--events-file",
        str(events),
    )
    assert rc == 2
    assert "Invalid target phase" in out


def test_phase_advance_force_overrides_gate(
    capsys: pytest.CaptureFixture[str], tmp_state: tuple[Path, Path]
) -> None:
    state, events = tmp_state
    # Pre-stage item in REVIEW so we hit the ContentGuardGate (applies to REVIEW).
    from src.state import StateManager

    sm = StateManager(
        storage_type="json",
        filename=str(state),
        event_filename=str(events),
    )
    item = WorkItem(id="task-d", phase=Phase.IMPLEMENT, payload={"body": ""})
    save_work_item(sm, item)

    rc_block, out_block = _run(
        capsys,
        "phase",
        "advance",
        "task-d",
        "REVIEW",
        "--reason",
        "testing block",
        "--state-file",
        str(state),
        "--events-file",
        str(events),
    )
    assert rc_block == 1
    assert "[BLOCK" in out_block

    # Force through.
    rc_force, out_force = _run(
        capsys,
        "phase",
        "advance",
        "task-d",
        "REVIEW",
        "--force",
        "--reason",
        "override",
        "--state-file",
        str(state),
        "--events-file",
        str(events),
    )
    assert rc_force == 0
    assert "IMPLEMENT -> REVIEW" in out_force

    # Rehydrate from disk — the CLI uses its own StateManager instance
    # per invocation, so the fixture's in-memory `sm` is stale.
    fresh = StateManager(
        storage_type="json",
        filename=str(state),
        event_filename=str(events),
    )
    reloaded = load_work_item(fresh, "task-d")
    assert reloaded is not None
    assert reloaded.phase is Phase.REVIEW


def test_self_prompt_dry_run_does_not_write_queue(
    capsys: pytest.CaptureFixture[str],
    tmp_state: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, events = tmp_state
    queue = tmp_path / "queue.jsonl"
    coverage = tmp_path / "coverage.xml"
    coverage.write_text(
        '<?xml version="1.0" ?><coverage><class filename="src/low.py" line-rate="0.10"/></coverage>'
    )

    # Even with SELF_PROMPT_ENABLED off, --dry-run still collects and synthesizes.
    monkeypatch.setattr(Config, "SELF_PROMPT_ENABLED", False)

    rc, out = _run(
        capsys,
        "self-prompt",
        "--dry-run",
        "--coverage-file",
        str(coverage),
        "--queue-file",
        str(queue),
        "--state-file",
        str(state),
        "--events-file",
        str(events),
    )
    assert rc == 0
    assert "signals=" in out
    assert "dry-run" in out
    assert not queue.exists()
    # Config flag restored.
    assert Config.SELF_PROMPT_ENABLED is False


def test_self_prompt_rejects_dry_run_with_write(
    capsys: pytest.CaptureFixture[str], tmp_state: tuple[Path, Path]
) -> None:
    """Reviewer feedback on #11: --dry-run and --write must not be
    combinable. argparse raises SystemExit(2) on mutex violations."""
    state, events = tmp_state
    with pytest.raises(SystemExit):
        swarm_cli.main(
            [
                "self-prompt",
                "--dry-run",
                "--write",
                "--state-file",
                str(state),
                "--events-file",
                str(events),
            ]
        )


def test_self_prompt_write_appends_to_queue(
    capsys: pytest.CaptureFixture[str],
    tmp_state: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, events = tmp_state
    queue = tmp_path / "queue.jsonl"
    coverage = tmp_path / "coverage.xml"
    coverage.write_text(
        '<?xml version="1.0" ?><coverage><class filename="src/low.py" line-rate="0.10"/></coverage>'
    )

    monkeypatch.setattr(Config, "SELF_PROMPT_ENABLED", True)
    monkeypatch.setattr(Config, "SELF_PROMPT_MAX_PER_HOUR", 10)
    monkeypatch.chdir(tmp_path)

    rc, out = _run(
        capsys,
        "self-prompt",
        "--write",
        "--coverage-file",
        str(coverage),
        "--queue-file",
        str(queue),
        "--state-file",
        str(state),
        "--events-file",
        str(events),
    )
    assert rc == 0
    assert queue.exists()
    assert "wrote" in out
