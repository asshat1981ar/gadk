"""Tests for the self-prompting loop."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.config import Config
from src.services import self_prompt as sp
from src.services.sdlc_phase import Phase
from src.state import StateManager


@pytest.fixture
def sm(tmp_path: Path) -> StateManager:
    return StateManager(
        storage_type="json",
        filename=str(tmp_path / "state.json"),
        event_filename=str(tmp_path / "events.jsonl"),
    )


def _write_coverage(path: Path, files: list[tuple[str, float]]) -> None:
    classes = "".join(f'<class filename="{name}" line-rate="{rate}"/>' for name, rate in files)
    path.write_text(f'<?xml version="1.0" ?><coverage>{classes}</coverage>')


def test_collect_coverage_flags_low_rate_modules(tmp_path: Path) -> None:
    cov = tmp_path / "coverage.xml"
    _write_coverage(cov, [("src/high.py", 0.95), ("src/low.py", 0.10), ("src/mid.py", 0.60)])
    signals = sp.collect_coverage_signals(cov)
    names = {s.evidence[0] for s in signals}
    assert "src/low.py" in names
    assert "src/high.py" not in names
    assert "src/mid.py" not in names


def test_collect_event_log_signals_only_blocked(sm: StateManager) -> None:
    sm._append_event({"action": "phase.transition", "task_id": "ok", "reason": "ok"})
    sm._append_event({"action": "phase.transition.blocked", "task_id": "t1", "reason": "gate"})
    signals = sp.collect_event_log_signals(sm)
    assert len(signals) == 1
    assert signals[0].phase is Phase.REVIEW
    assert "t1" in signals[0].intent


def test_collect_backlog_signals_filters_by_age(tmp_path: Path) -> None:
    q = tmp_path / "prompt_queue.jsonl"
    now = datetime.now(UTC)
    old = (now - timedelta(hours=24)).isoformat()
    fresh = now.isoformat()
    q.write_text(
        json.dumps({"timestamp": old, "user_id": "a", "prompt": "old one"})
        + "\n"
        + json.dumps({"timestamp": fresh, "user_id": "b", "prompt": "fresh one"})
        + "\n"
    )
    signals = sp.collect_backlog_signals(q, max_age_hours=12.0)
    assert len(signals) == 1
    assert "old one" in "".join(signals[0].evidence)


def test_synthesize_dedups_same_intent() -> None:
    signal = sp.GapSignal(source="x", intent="Do a Thing", phase=Phase.IMPLEMENT)
    prompts = sp.synthesize([signal, signal])
    assert len(prompts) == 1


def test_synthesize_respects_generation_cap() -> None:
    signal = sp.GapSignal(source="x", intent="Recursive", phase=Phase.PLAN)
    out = sp.synthesize([signal], parent_generation=sp.MAX_GENERATION)
    assert out == []


def test_rate_limiter_caps_per_hour(sm: StateManager) -> None:
    limiter = sp.RateLimiter(sm, max_per_hour=2)
    assert limiter.try_consume()
    assert limiter.try_consume()
    assert not limiter.try_consume()


def test_dispatch_writes_prompts_and_respects_limiter(sm: StateManager, tmp_path: Path) -> None:
    q = tmp_path / "prompt_queue.jsonl"
    limiter = sp.RateLimiter(sm, max_per_hour=1)
    prompts = [
        sp.SelfPrompt(phase=Phase.PLAN, intent="a", generation=1),
        sp.SelfPrompt(phase=Phase.PLAN, intent="b", generation=1),
    ]
    written = sp.dispatch(prompts, queue_path=q, rate_limiter=limiter)
    assert len(written) == 1
    lines = [json.loads(line) for line in q.read_text().splitlines() if line]
    assert len(lines) == 1
    assert lines[0]["user_id"] == "self_prompt"
    assert lines[0]["self_prompt"]["intent"] == "a"


def test_off_switch_blocks_run_once(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Config, "SELF_PROMPT_ENABLED", True)
    (tmp_path / sp.SELF_PROMPT_OFF_SENTINEL).write_text("stop")
    written = sp.run_once(
        sm=sm,
        coverage_xml=tmp_path / "none.xml",
        queue_path=tmp_path / "q.jsonl",
        sentinel_dir=tmp_path,
    )
    assert written == []


def test_run_once_disabled_by_default(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Config, "SELF_PROMPT_ENABLED", False)
    written = sp.run_once(
        sm=sm, coverage_xml=tmp_path / "none.xml", queue_path=tmp_path / "q.jsonl"
    )
    assert written == []


def test_run_once_happy_path(
    sm: StateManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Config, "SELF_PROMPT_ENABLED", True)
    monkeypatch.setattr(Config, "SELF_PROMPT_MAX_PER_HOUR", 10)
    cov = tmp_path / "coverage.xml"
    _write_coverage(cov, [("src/low.py", 0.10)])
    q = tmp_path / "q.jsonl"
    written = sp.run_once(sm=sm, coverage_xml=cov, queue_path=q, sentinel_dir=tmp_path)
    assert len(written) == 1
    assert written[0].phase is Phase.IMPLEMENT
    # dedup window persisted in state
    dedup = sm.data["self_prompt"]["dedup"]
    assert len(dedup) == 1
