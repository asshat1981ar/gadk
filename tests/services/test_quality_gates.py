"""Tests for quality-gate abstractions."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.services.quality_gates import (
    ContentGuardGate,
    CriticReviewGate,
    GateResult,
    LintGate,
    QualityGate,
    TestCoverageGate,
)
from src.services.sdlc_phase import Phase, WorkItem


def test_gate_result_is_frozen() -> None:
    import dataclasses

    result = GateResult(gate="x", passed=True, blocking=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.passed = False  # type: ignore[misc]


def test_should_run_honours_applies_to() -> None:
    class OnlyReview(QualityGate):
        name = "only_review"
        applies_to = frozenset({Phase.REVIEW})

        def evaluate(self, item: WorkItem) -> GateResult:  # pragma: no cover
            return GateResult(gate=self.name, passed=True, blocking=True)

    gate = OnlyReview()
    assert gate.should_run(Phase.REVIEW)
    assert not gate.should_run(Phase.PLAN)


def test_content_guard_gate_rejects_empty_body() -> None:
    gate = ContentGuardGate(min_bytes=40)
    item = WorkItem(id="t", payload={"body": ""})
    result = gate.evaluate(item)
    assert not result.passed
    assert result.blocking is True


def test_content_guard_gate_passes_meaningful_body() -> None:
    gate = ContentGuardGate(min_bytes=10)
    item = WorkItem(
        id="t",
        payload={"body": "This is a real implementation note with enough substance."},
    )
    result = gate.evaluate(item)
    assert result.passed


def test_critic_review_gate_wraps_reviewer_callable() -> None:
    def reviewer(item: WorkItem) -> tuple[str, str]:
        return "pass", "looks good"

    gate = CriticReviewGate(reviewer)
    item = WorkItem(id="t")
    result = gate.evaluate(item)
    assert result.passed
    assert result.message == "looks good"


def test_critic_review_gate_blocks_on_retry() -> None:
    def reviewer(item: WorkItem) -> tuple[str, str]:
        return "retry", "rework requested"

    gate = CriticReviewGate(reviewer)
    result = gate.evaluate(WorkItem(id="t"))
    assert not result.passed
    assert result.evidence["status"] == "retry"


def test_lint_gate_handles_missing_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))  # ensure ruff is not found
    gate = LintGate(cwd=tmp_path, blocking=False)
    result = gate.evaluate(WorkItem(id="t"))
    assert not result.passed
    assert "failed to run" in result.message


def test_test_coverage_gate_missing_file(tmp_path: Path) -> None:
    gate = TestCoverageGate(min_coverage=0.8, coverage_file=tmp_path / "missing.xml")
    result = gate.evaluate(WorkItem(id="t"))
    assert not result.passed
    assert "not found" in result.message


def test_test_coverage_gate_parses_rate(tmp_path: Path) -> None:
    cov = tmp_path / "coverage.xml"
    cov.write_text('<?xml version="1.0" ?><coverage line-rate="0.82"/>', encoding="utf-8")
    gate = TestCoverageGate(min_coverage=0.8, coverage_file=cov)
    result = gate.evaluate(WorkItem(id="t"))
    assert result.passed
    assert result.evidence["rate"] == pytest.approx(0.82)


def test_test_coverage_gate_below_threshold(tmp_path: Path) -> None:
    cov = tmp_path / "coverage.xml"
    cov.write_text('<?xml version="1.0" ?><coverage line-rate="0.50"/>', encoding="utf-8")
    gate = TestCoverageGate(min_coverage=0.8, coverage_file=cov)
    result = gate.evaluate(WorkItem(id="t"))
    assert not result.passed
