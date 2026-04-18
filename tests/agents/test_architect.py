"""Tests for the Architect agent's pure tool functions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.agents.architect import (
    ArchitectureNote,
    architecture_gate_payload,
    draft_architecture_note,
)
from src.services.sdlc_phase import Phase


def test_draft_architecture_note_returns_validated_dict() -> None:
    note = draft_architecture_note(
        task_id="sdlc-stabilize-codebase",
        title="Introduce phase-gate controller",
        context="The swarm has no explicit SDLC phase ledger.",
        decision="Add WorkItem + PhaseController driven by QualityGate.",
        consequences=["New module surface", "Better auditability"],
        alternatives=["Use LangGraph nodes only"],
        touched_paths=["src/services/phase_controller.py"],
    )
    assert note["task_id"] == "sdlc-stabilize-codebase"
    assert "Decision" not in note  # it's a dict, not rendered text
    assert note["consequences"] == ["New module surface", "Better auditability"]
    assert note["touched_paths"] == ["src/services/phase_controller.py"]


def test_draft_architecture_note_rejects_empty_fields() -> None:
    with pytest.raises(ValidationError):
        draft_architecture_note(
            task_id="", title="x", context="x", decision="x"
        )


def test_architecture_note_markdown_contains_all_sections() -> None:
    note = ArchitectureNote(
        task_id="t1",
        title="Test",
        context="Why",
        decision="Do X",
        consequences=["up", "down"],
        alternatives_considered=["Y"],
        touched_paths=["a.py"],
    )
    md = note.as_markdown()
    for section in ("# Test", "## Context", "## Decision", "## Alternatives", "## Consequences", "## Touched paths"):
        assert section in md


def test_architecture_gate_payload_shape_matches_content_guard_gate() -> None:
    note = draft_architecture_note(
        task_id="t1",
        title="T",
        context="enough context here to make the markdown substantial",
        decision="and the decision field is also substantial enough",
        consequences=["c1"],
    )
    payload = architecture_gate_payload(note)
    assert payload["phase"] == Phase.ARCHITECT.value
    assert "body" in payload
    assert len(payload["body"]) > 40  # should survive default ContentGuardGate
