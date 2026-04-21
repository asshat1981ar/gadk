"""Tests for the SDLC phase model and transition rules."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.services.sdlc_phase import (
    ALLOWED_TRANSITIONS,
    PHASE_ORDER,
    Phase,
    PhaseHistoryEntry,
    WorkItem,
    can_advance,
    next_phase,
)

# =============================================================================
# Phase Enum Tests
# =============================================================================


def test_phase_enum_members():
    """Test that all phase enum members exist and are accessible."""
    assert Phase.PLAN == "PLAN"
    assert Phase.ARCHITECT == "ARCHITECT"
    assert Phase.IMPLEMENT == "IMPLEMENT"
    assert Phase.REVIEW == "REVIEW"
    assert Phase.GOVERN == "GOVERN"
    assert Phase.OPERATE == "OPERATE"


def test_phase_enum_string_conversion():
    """Test Phase enum string conversion uses .value."""
    assert Phase.PLAN.value == "PLAN"
    assert Phase.ARCHITECT.value == "ARCHITECT"
    assert Phase.IMPLEMENT.value == "IMPLEMENT"
    assert Phase.REVIEW.value == "REVIEW"
    assert Phase.GOVERN.value == "GOVERN"
    assert Phase.OPERATE.value == "OPERATE"


def test_phase_enum_is_string_based():
    """Test Phase enum inherits from str properly."""
    assert isinstance(Phase.PLAN, str)
    assert Phase.PLAN.value == "PLAN"


# =============================================================================
# PHASE_ORDER Tests
# =============================================================================


def test_phase_order_is_canonical() -> None:
    assert PHASE_ORDER[0] is Phase.PLAN
    assert PHASE_ORDER[-1] is Phase.OPERATE
    assert len(set(PHASE_ORDER)) == len(PHASE_ORDER)


def test_phase_order_complete_sequence() -> None:
    """Test PHASE_ORDER contains all phases in correct order."""
    assert PHASE_ORDER == (
        Phase.PLAN,
        Phase.ARCHITECT,
        Phase.IMPLEMENT,
        Phase.REVIEW,
        Phase.GOVERN,
        Phase.OPERATE,
    )


def test_phase_order_all_phases_present() -> None:
    """Test that all Phase enum members are in PHASE_ORDER."""
    assert set(PHASE_ORDER) == set(Phase)


# =============================================================================
# ALLOWED_TRANSITIONS Tests
# =============================================================================


def test_allowed_transitions_structure() -> None:
    """Test ALLOWED_TRANSITIONS has correct keys."""
    assert set(ALLOWED_TRANSITIONS.keys()) == set(Phase)


def test_allowed_transitions_forward_edges() -> None:
    """Test forward transitions between phases."""
    assert ALLOWED_TRANSITIONS[Phase.PLAN] == frozenset({Phase.ARCHITECT})
    assert ALLOWED_TRANSITIONS[Phase.ARCHITECT] == frozenset({Phase.IMPLEMENT})
    assert ALLOWED_TRANSITIONS[Phase.IMPLEMENT] == frozenset({Phase.REVIEW})
    assert ALLOWED_TRANSITIONS[Phase.GOVERN] == frozenset({Phase.OPERATE})


def test_allowed_transitions_review_rework_edge() -> None:
    """Test REVIEW has both forward and rework edges."""
    assert Phase.GOVERN in ALLOWED_TRANSITIONS[Phase.REVIEW]
    assert Phase.IMPLEMENT in ALLOWED_TRANSITIONS[Phase.REVIEW]
    assert len(ALLOWED_TRANSITIONS[Phase.REVIEW]) == 2


def test_operate_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS[Phase.OPERATE] == frozenset()


# =============================================================================
# can_advance() Tests
# =============================================================================


def test_can_advance_allows_all_valid_forward_transitions() -> None:
    """Test all valid forward transitions are allowed."""
    # PLAN → ARCHITECT
    assert can_advance(Phase.PLAN, Phase.ARCHITECT) is True
    # ARCHITECT → IMPLEMENT
    assert can_advance(Phase.ARCHITECT, Phase.IMPLEMENT) is True
    # IMPLEMENT → REVIEW
    assert can_advance(Phase.IMPLEMENT, Phase.REVIEW) is True
    # REVIEW → GOVERN
    assert can_advance(Phase.REVIEW, Phase.GOVERN) is True
    # GOVERN → OPERATE
    assert can_advance(Phase.GOVERN, Phase.OPERATE) is True


def test_can_advance_allows_review_rework_edge() -> None:
    """Test REVIEW → IMPLEMENT rework edge is allowed."""
    assert can_advance(Phase.REVIEW, Phase.IMPLEMENT) is True


def test_can_advance_rejects_skip() -> None:
    """Test skipping phases is not allowed."""
    assert can_advance(Phase.PLAN, Phase.REVIEW) is False
    assert can_advance(Phase.PLAN, Phase.IMPLEMENT) is False
    assert can_advance(Phase.PLAN, Phase.GOVERN) is False
    assert can_advance(Phase.PLAN, Phase.OPERATE) is False


def test_can_advance_rejects_backwards_except_rework() -> None:
    """Test backward transitions (except REVIEW→IMPLEMENT) are rejected."""
    assert can_advance(Phase.ARCHITECT, Phase.PLAN) is False
    assert can_advance(Phase.IMPLEMENT, Phase.PLAN) is False
    assert can_advance(Phase.IMPLEMENT, Phase.ARCHITECT) is False
    assert can_advance(Phase.REVIEW, Phase.PLAN) is False
    assert can_advance(Phase.REVIEW, Phase.ARCHITECT) is False
    assert can_advance(Phase.GOVERN, Phase.IMPLEMENT) is False
    assert can_advance(Phase.GOVERN, Phase.REVIEW) is False
    assert can_advance(Phase.GOVERN, Phase.ARCHITECT) is False
    assert can_advance(Phase.OPERATE, Phase.GOVERN) is False
    assert can_advance(Phase.OPERATE, Phase.IMPLEMENT) is False


def test_can_advance_same_phase_is_invalid() -> None:
    """Test staying in same phase is not a valid advance."""
    assert can_advance(Phase.PLAN, Phase.PLAN) is False
    assert can_advance(Phase.ARCHITECT, Phase.ARCHITECT) is False
    assert can_advance(Phase.OPERATE, Phase.OPERATE) is False


# =============================================================================
# next_phase() Tests
# =============================================================================


def test_next_phase_walks_forward() -> None:
    assert next_phase(Phase.PLAN) is Phase.ARCHITECT
    assert next_phase(Phase.ARCHITECT) is Phase.IMPLEMENT
    assert next_phase(Phase.IMPLEMENT) is Phase.REVIEW
    assert next_phase(Phase.REVIEW) is Phase.GOVERN
    assert next_phase(Phase.GOVERN) is Phase.OPERATE


def test_next_phase_terminal_returns_none() -> None:
    """Test next_phase returns None for terminal phase."""
    assert next_phase(Phase.OPERATE) is None


def test_next_phase_covers_all_non_terminal_phases() -> None:
    """Test next_phase works for all non-terminal phases."""
    for phase in Phase:
        if phase is not Phase.OPERATE:
            result = next_phase(phase)
            assert result is not None
            assert result in Phase


# =============================================================================
# PhaseHistoryEntry Tests
# =============================================================================


def test_phase_history_entry_creation():
    """Test PhaseHistoryEntry can be created with all fields."""
    now = datetime.now(UTC)
    entry = PhaseHistoryEntry(
        from_phase=Phase.PLAN,
        to_phase=Phase.ARCHITECT,
        at=now,
        reason="Design ready",
        evidence_refs=["doc-1", "doc-2"],
    )
    assert entry.from_phase is Phase.PLAN
    assert entry.to_phase is Phase.ARCHITECT
    assert entry.at == now
    assert entry.reason == "Design ready"
    assert entry.evidence_refs == ["doc-1", "doc-2"]


def test_phase_history_entry_defaults():
    """Test PhaseHistoryEntry default values."""
    entry = PhaseHistoryEntry(to_phase=Phase.ARCHITECT, at=datetime.now(UTC))
    assert entry.from_phase is None
    assert entry.reason == ""
    assert entry.evidence_refs == []


def test_phase_history_entry_from_phase_none():
    """Test PhaseHistoryEntry handles from_phase=None (initial entry)."""
    entry = PhaseHistoryEntry(from_phase=None, to_phase=Phase.PLAN, at=datetime.now(UTC))
    assert entry.from_phase is None
    assert entry.to_phase is Phase.PLAN


# =============================================================================
# WorkItem Tests
# =============================================================================


def test_work_item_defaults() -> None:
    item = WorkItem(id="task-1")
    assert item.phase is Phase.PLAN
    assert item.payload == {}
    assert item.history == []


def test_work_item_creation_with_fields():
    """Test WorkItem creation with all fields specified."""
    item = WorkItem(
        id="task-123", phase=Phase.REVIEW, payload={"key": "value", "number": 42}, history=[]
    )
    assert item.id == "task-123"
    assert item.phase is Phase.REVIEW
    assert item.payload == {"key": "value", "number": 42}
    assert item.history == []


def test_work_item_id_min_length_enforced() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WorkItem(id="")


def test_work_item_id_max_length_enforced():
    """Test WorkItem id max length is enforced."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WorkItem(id="x" * 81)  # 81 chars exceeds max_length of 80


def test_work_item_valid_id_lengths():
    """Test WorkItem accepts valid id lengths."""
    item1 = WorkItem(id="a")  # min_length=1
    assert item1.id == "a"

    item80 = WorkItem(id="x" * 80)  # exactly max_length
    assert item80.id == "x" * 80


def test_work_item_payload_defaults_to_empty_dict():
    """Test WorkItem payload defaults to empty dict."""
    item = WorkItem(id="task-1")
    assert item.payload == {}


def test_work_item_payload_arbitrary_data():
    """Test WorkItem payload can hold various data types."""
    payload = {
        "string": "value",
        "number": 42,
        "boolean": True,
        "list": [1, 2, 3],
        "nested": {"key": "value"},
        "none": None,
    }
    item = WorkItem(id="task-1", payload=payload)
    assert item.payload == payload


def test_work_item_record_appends_history() -> None:
    item = WorkItem(id="task-1")
    item.record(Phase.ARCHITECT, reason="ready", evidence_refs=["lint"])
    assert len(item.history) == 1
    entry = item.history[0]
    assert isinstance(entry, PhaseHistoryEntry)
    assert entry.from_phase is Phase.PLAN
    assert entry.to_phase is Phase.ARCHITECT
    assert entry.reason == "ready"
    assert entry.evidence_refs == ["lint"]


def test_work_item_record_updates_not_automatic():
    """Test that record() doesn't automatically update phase - caller must do it."""
    item = WorkItem(id="task-1", phase=Phase.PLAN)
    item.record(Phase.ARCHITECT, reason="advance")
    # Phase should still be PLAN (caller must mutate it)
    assert item.phase is Phase.PLAN
    # After record, manually update phase
    item.phase = Phase.ARCHITECT
    assert item.phase is Phase.ARCHITECT


def test_work_item_record_multiple_entries():
    """Test WorkItem record adds multiple history entries."""
    item = WorkItem(id="task-1")

    # First transition
    item.record(Phase.ARCHITECT, reason="design complete")
    item.phase = Phase.ARCHITECT

    # Second transition
    item.record(Phase.IMPLEMENT, reason="architecture approved")
    item.phase = Phase.IMPLEMENT

    assert len(item.history) == 2

    # Verify first entry
    assert item.history[0].from_phase is Phase.PLAN
    assert item.history[0].to_phase is Phase.ARCHITECT
    assert item.history[0].reason == "design complete"

    # Verify second entry
    assert item.history[1].from_phase is Phase.ARCHITECT
    assert item.history[1].to_phase is Phase.IMPLEMENT
    assert item.history[1].reason == "architecture approved"


def test_work_item_record_with_empty_evidence_refs():
    """Test WorkItem record with empty evidence_refs."""
    item = WorkItem(id="task-1")
    item.record(Phase.ARCHITECT, reason="advance")
    assert item.history[0].evidence_refs == []


def test_work_item_record_evidence_refs_is_copied():
    """Test that evidence_refs is copied, not referenced."""
    item = WorkItem(id="task-1")
    refs = ["ref-1"]
    item.record(Phase.ARCHITECT, evidence_refs=refs)
    # Modify original list
    refs.append("ref-2")
    # Entry should not be affected
    assert item.history[0].evidence_refs == ["ref-1"]


def test_work_item_empty_history():
    """Test WorkItem with empty history list."""
    item = WorkItem(id="task-1", history=[])
    assert item.history == []


def test_work_item_full_phase_transition_simulation():
    """Simulate a realistic workflow through all phases."""
    item = WorkItem(id="req-123", payload={"description": "Build feature X"})

    # PLAN → ARCHITECT
    assert can_advance(item.phase, Phase.ARCHITECT)
    item.record(Phase.ARCHITECT, reason="Requirements gathered", evidence_refs=["req-doc"])
    item.phase = Phase.ARCHITECT

    # ARCHITECT → IMPLEMENT
    assert can_advance(item.phase, Phase.IMPLEMENT)
    item.record(Phase.IMPLEMENT, reason="Design complete", evidence_refs=["arch-doc"])
    item.phase = Phase.IMPLEMENT

    # IMPLEMENT → REVIEW
    assert can_advance(item.phase, Phase.REVIEW)
    item.record(Phase.REVIEW, reason="Code complete", evidence_refs=["pr-42"])
    item.phase = Phase.REVIEW

    # REVIEW → GOVERN (approve path)
    assert can_advance(item.phase, Phase.GOVERN)
    item.record(Phase.GOVERN, reason="Review passed", evidence_refs=["review-ok"])
    item.phase = Phase.GOVERN

    # GOVERN → OPERATE
    assert can_advance(item.phase, Phase.OPERATE)
    item.record(Phase.OPERATE, reason="Deployed", evidence_refs=["deploy-log"])
    item.phase = Phase.OPERATE

    assert len(item.history) == 5
    assert item.phase is Phase.OPERATE


def test_work_item_rework_transition_simulation():
    """Simulate a workflow with rework from REVIEW to IMPLEMENT."""
    item = WorkItem(id="req-456")

    # Move to REVIEW
    item.phase = Phase.IMPLEMENT
    item.phase = Phase.REVIEW
    item.history = [  # Mock history
        PhaseHistoryEntry(
            from_phase=Phase.PLAN,
            to_phase=Phase.IMPLEMENT,
            at=datetime.now(UTC),
            reason="skip arch",
        ),
    ]

    # REVIEW → IMPLEMENT (rework)
    assert can_advance(Phase.REVIEW, Phase.IMPLEMENT)
    item.record(Phase.IMPLEMENT, reason="Needs rework", evidence_refs=["review-fail"])
    item.phase = Phase.IMPLEMENT

    assert item.phase is Phase.IMPLEMENT
    assert item.history[-1].to_phase is Phase.IMPLEMENT
    assert item.history[-1].reason == "Needs rework"


def test_work_item_history_timestamp_is_datetime():
    """Test history entries have proper datetime timestamps."""
    item = WorkItem(id="task-1")
    before = datetime.now(UTC)
    item.record(Phase.ARCHITECT)
    after = datetime.now(UTC)

    entry = item.history[0]
    assert isinstance(entry.at, datetime)
    assert before <= entry.at <= after
    assert entry.at.tzinfo == UTC


# =============================================================================
# Edge Case Tests
# =============================================================================


@pytest.mark.parametrize("phase", list(Phase))
def test_all_phases_have_allowed_transitions_defined(phase):
    """Test that every phase has an entry in ALLOWED_TRANSITIONS."""
    assert phase in ALLOWED_TRANSITIONS


def test_history_entry_prevents_extra_fields():
    """Test PhaseHistoryEntry model_config extra='forbid'."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        PhaseHistoryEntry(to_phase=Phase.ARCHITECT, at=datetime.now(UTC), extra_field="not allowed")
    assert "extra_field" in str(exc_info.value)


def test_work_item_prevents_extra_fields():
    """Test WorkItem model_config extra='forbid'."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        WorkItem(id="task-1", unknown_field="value")
    assert "unknown_field" in str(exc_info.value)
