"""Comprehensive tests for quality-gate abstractions.

Covers all gate classes:
- ContentGuardGate: low-value content detection
- LintGate: ruff subprocess integration
- TypecheckGate: mypy subprocess integration
- SecurityScanGate: bandit subprocess integration
- TestCoverageGate: coverage XML parsing
- CriticReviewGate: critic review integration

Each gate is tested for:
- Passing case
- Failing case
- Blocking vs advisory behavior
- applies_to phase filtering
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.services.quality_gates import (
    ContentGuardGate,
    CriticReviewGate,
    GateResult,
    LintGate,
    QualityGate,
    SecurityScanGate,
    TestCoverageGate,
    TypecheckGate,
)
from src.services.sdlc_phase import Phase, WorkItem

# -----------------------------------------------------------------------------
# GateResult tests
# -----------------------------------------------------------------------------


def test_gate_result_is_frozen() -> None:
    """GateResult should be immutable."""
    import dataclasses

    result = GateResult(gate="x", passed=True, blocking=True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.passed = False  # type: ignore[misc]


def test_gate_result_structure() -> None:
    """GateResult should have all expected fields."""
    result = GateResult(
        gate="test_gate",
        passed=True,
        blocking=False,
        evidence={"key": "value"},
        message="test message",
    )
    assert result.gate == "test_gate"
    assert result.passed is True
    assert result.blocking is False
    assert result.evidence == {"key": "value"}
    assert result.message == "test message"


def test_gate_result_defaults() -> None:
    """GateResult should have sensible defaults for optional fields."""
    result = GateResult(gate="test", passed=True, blocking=True)
    assert result.evidence == {}
    assert result.message == ""


# -----------------------------------------------------------------------------
# QualityGate base class tests
# -----------------------------------------------------------------------------


def test_should_run_honours_applies_to() -> None:
    """Gate should only run for phases in applies_to."""

    class OnlyReview(QualityGate):
        name = "only_review"
        applies_to = frozenset({Phase.REVIEW})

        def evaluate(self, item: WorkItem) -> GateResult:  # pragma: no cover
            return GateResult(gate=self.name, passed=True, blocking=True)

    gate = OnlyReview()
    assert gate.should_run(Phase.REVIEW)
    assert not gate.should_run(Phase.PLAN)
    assert not gate.should_run(Phase.GOVERN)


def test_should_run_empty_applies_to_runs_on_all_phases() -> None:
    """Gate with empty applies_to should run on all phases."""

    class UniversalGate(QualityGate):
        name = "universal"
        applies_to = frozenset()

        def evaluate(self, item: WorkItem) -> GateResult:  # pragma: no cover
            return GateResult(gate=self.name, passed=True, blocking=True)

    gate = UniversalGate()
    for phase in Phase:
        assert gate.should_run(phase)


def test_should_run_multiple_phases() -> None:
    """Gate should support multiple phases in applies_to."""

    class MultiPhaseGate(QualityGate):
        name = "multi"
        applies_to = frozenset({Phase.REVIEW, Phase.GOVERN})

        def evaluate(self, item: WorkItem) -> GateResult:  # pragma: no cover
            return GateResult(gate=self.name, passed=True, blocking=True)

    gate = MultiPhaseGate()
    assert gate.should_run(Phase.REVIEW)
    assert gate.should_run(Phase.GOVERN)
    assert not gate.should_run(Phase.PLAN)
    assert not gate.should_run(Phase.OPERATE)


# -----------------------------------------------------------------------------
# ContentGuardGate tests
# -----------------------------------------------------------------------------


class TestContentGuardGate:
    """Test ContentGuardGate for low-value content detection."""

    def test_passes_meaningful_content(self) -> None:
        """Gate should pass when content has sufficient substance."""
        gate = ContentGuardGate(min_bytes=10)
        item = WorkItem(
            id="t",
            payload={"body": "This is a real implementation note with enough substance."},
        )
        result = gate.evaluate(item)
        assert result.passed
        assert result.blocking is True
        assert result.gate == "content_guard"
        assert result.message == "ok"

    def test_rejects_empty_body(self) -> None:
        """Gate should fail when body is empty."""
        gate = ContentGuardGate(min_bytes=40)
        item = WorkItem(id="t", payload={"body": ""})
        result = gate.evaluate(item)
        assert not result.passed
        assert result.blocking is True
        assert "low-value" in result.message.lower()

    def test_rejects_missing_body_key(self) -> None:
        """Gate should fail when body key is missing from payload."""
        gate = ContentGuardGate(min_bytes=40)
        item = WorkItem(id="t", payload={})
        result = gate.evaluate(item)
        assert not result.passed
        assert result.evidence["body_len"] == 0

    def test_rejects_short_content(self) -> None:
        """Gate should fail when content is below min_bytes threshold."""
        gate = ContentGuardGate(min_bytes=100)
        item = WorkItem(id="t", payload={"body": "Short text"})
        result = gate.evaluate(item)
        assert not result.passed

    def test_allows_content_at_exact_threshold(self) -> None:
        """Gate should pass when content meets exact threshold."""
        gate = ContentGuardGate(min_bytes=20)
        item = WorkItem(id="t", payload={"body": "Exactly twenty bytes!"})
        result = gate.evaluate(item)
        assert result.passed

    def test_blocking_is_true_by_default(self) -> None:
        """ContentGuardGate should be blocking by default."""
        gate = ContentGuardGate(min_bytes=10)
        assert gate.blocking is True

    def test_applies_to_review_and_govern(self) -> None:
        """ContentGuardGate should only apply to REVIEW and GOVERN phases."""
        gate = ContentGuardGate(min_bytes=10)
        assert gate.applies_to == frozenset({Phase.REVIEW, Phase.GOVERN})
        assert gate.should_run(Phase.REVIEW)
        assert gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.PLAN)
        assert not gate.should_run(Phase.ARCHITECT)
        assert not gate.should_run(Phase.IMPLEMENT)
        assert not gate.should_run(Phase.OPERATE)

    def test_evidence_includes_body_len(self) -> None:
        """Gate result should include body length in evidence."""
        gate = ContentGuardGate(min_bytes=10)
        item = WorkItem(id="t", payload={"body": "Hello world"})
        result = gate.evaluate(item)
        assert result.evidence["body_len"] == 11


# -----------------------------------------------------------------------------
# _SubprocessGate base tests (shared by LintGate, TypecheckGate, SecurityScanGate)
# -----------------------------------------------------------------------------


class TestSubprocessGateBase:
    """Test shared behavior of subprocess-based gates."""

    def test_advisory_by_default(self) -> None:
        """Subprocess gates should be advisory (non-blocking) by default."""
        gate = LintGate(cwd=".")
        assert gate.blocking is False

    def test_blocking_override_in_constructor(self) -> None:
        """Subprocess gates can be made blocking via constructor."""
        gate = LintGate(cwd=".", blocking=True)
        assert gate.blocking is True

    def test_handles_file_not_found(self, tmp_path: Path) -> None:
        """Gate should handle missing binary gracefully."""
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("PATH", str(tmp_path))
        gate = LintGate(cwd=tmp_path, blocking=False)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert "failed to run" in result.message
        assert result.evidence["error"] == "FileNotFoundError"
        monkeypatch.undo()

    @patch("subprocess.run")
    def test_handles_subprocess_timeout(self, mock_run: Mock, tmp_path: Path) -> None:
        """Gate should handle subprocess timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ruff", timeout=120)
        gate = LintGate(cwd=tmp_path, blocking=False)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert result.evidence["error"] == "TimeoutExpired"
        assert "failed to run" in result.message

    def test_uses_config_timeout(self, tmp_path: Path) -> None:
        """Gate should use GATE_SUBPROCESS_TIMEOUT_SEC from config."""
        # Patch subprocess.run to capture the timeout value passed
        captured_timeouts: list[float] = []

        def capture_run(*args, **kwargs):
            captured_timeouts.append(kwargs.get("timeout"))
            mock = Mock()
            mock.returncode = 0
            mock.stdout = "ok"
            mock.stderr = ""
            return mock

        with patch("subprocess.run", side_effect=capture_run):
            # Temporarily set the config attribute via a setattr on the config module
            import src.config

            original = getattr(src.config.Config, "GATE_SUBPROCESS_TIMEOUT_SEC", None)
            src.config.Config.GATE_SUBPROCESS_TIMEOUT_SEC = 60.0
            try:
                gate = LintGate(cwd=tmp_path)
                gate.evaluate(WorkItem(id="t"))
                assert captured_timeouts == [60.0]
            finally:
                if original is not None:
                    src.config.Config.GATE_SUBPROCESS_TIMEOUT_SEC = original
                else:
                    delattr(src.config.Config, "GATE_SUBPROCESS_TIMEOUT_SEC")


# -----------------------------------------------------------------------------
# LintGate tests
# -----------------------------------------------------------------------------


class TestLintGate:
    """Test LintGate ruff integration."""

    def test_default_cmd(self) -> None:
        """LintGate should use correct default command."""
        gate = LintGate(cwd=".")
        assert gate.cmd == ("ruff", "check", "src", "tests")

    def test_name_is_lint(self) -> None:
        """LintGate should have correct name."""
        gate = LintGate(cwd=".")
        assert gate.name == "lint"

    def test_applies_to_review_and_govern(self) -> None:
        """LintGate should only apply to REVIEW and GOVERN phases."""
        gate = LintGate(cwd=".")
        assert gate.applies_to == frozenset({Phase.REVIEW, Phase.GOVERN})

    @patch("subprocess.run")
    def test_passes_on_clean_code(self, mock_run: Mock, tmp_path: Path) -> None:
        """Gate should pass when ruff finds no issues."""
        mock_run.return_value = Mock(returncode=0, stdout="All checks passed\n", stderr="")
        gate = LintGate(cwd=tmp_path)
        result = gate.evaluate(WorkItem(id="t"))
        assert result.passed
        assert result.message == "clean"

    @patch("subprocess.run")
    def test_fails_on_violations(self, mock_run: Mock, tmp_path: Path) -> None:
        """Gate should fail when ruff finds violations."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="src/file.py:1:1: E501 Line too long\n",
            stderr="",
        )
        gate = LintGate(cwd=tmp_path)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert result.message == "violations found"
        assert result.evidence["returncode"] == 1

    @patch("subprocess.run")
    def test_includes_stdout_tail_in_evidence(self, mock_run: Mock, tmp_path: Path) -> None:
        """Gate should include stdout tail in evidence."""
        long_output = "x" * 500
        mock_run.return_value = Mock(returncode=1, stdout=long_output, stderr="")
        gate = LintGate(cwd=tmp_path)
        result = gate.evaluate(WorkItem(id="t"))
        assert len(result.evidence["stdout_tail"]) <= 400
        assert result.evidence["stdout_tail"] == long_output[-400:]


# -----------------------------------------------------------------------------
# TypecheckGate tests
# -----------------------------------------------------------------------------


class TestTypecheckGate:
    """Test TypecheckGate mypy integration."""

    def test_default_cmd(self) -> None:
        """TypecheckGate should use correct default command."""
        gate = TypecheckGate(cwd=".")
        assert gate.cmd == ("mypy", "src")

    def test_name_is_typecheck(self) -> None:
        """TypecheckGate should have correct name."""
        gate = TypecheckGate(cwd=".")
        assert gate.name == "typecheck"

    def test_applies_to_review_and_govern(self) -> None:
        """TypecheckGate should only apply to REVIEW and GOVERN phases."""
        gate = TypecheckGate(cwd=".")
        assert gate.applies_to == frozenset({Phase.REVIEW, Phase.GOVERN})

    @patch("subprocess.run")
    def test_passes_on_clean_code(self, mock_run: Mock, tmp_path: Path) -> None:
        """Gate should pass when mypy finds no issues."""
        mock_run.return_value = Mock(returncode=0, stdout="Success: no issues found\n", stderr="")
        gate = TypecheckGate(cwd=tmp_path)
        result = gate.evaluate(WorkItem(id="t"))
        assert result.passed
        assert result.message == "clean"

    @patch("subprocess.run")
    def test_fails_on_type_errors(self, mock_run: Mock, tmp_path: Path) -> None:
        """Gate should fail when mypy finds type errors."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="src/file.py:1: error: Incompatible types\n",
            stderr="",
        )
        gate = TypecheckGate(cwd=tmp_path)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert result.message == "violations found"


# -----------------------------------------------------------------------------
# SecurityScanGate tests
# -----------------------------------------------------------------------------


class TestSecurityScanGate:
    """Test SecurityScanGate bandit integration."""

    def test_default_cmd(self) -> None:
        """SecurityScanGate should use correct default command."""
        gate = SecurityScanGate(cwd=".")
        assert gate.cmd == ("bandit", "-q", "-r", "src", "-x", "src/staged_agents")

    def test_name_is_security_scan(self) -> None:
        """SecurityScanGate should have correct name."""
        gate = SecurityScanGate(cwd=".")
        assert gate.name == "security_scan"

    def test_blocking_is_false_by_default(self) -> None:
        """SecurityScanGate should be advisory by default."""
        gate = SecurityScanGate(cwd=".")
        assert gate.blocking is False

    def test_can_be_blocking(self) -> None:
        """SecurityScanGate can be made blocking."""
        gate = SecurityScanGate(cwd=".", blocking=True)
        assert gate.blocking is True

    def test_applies_to_govern_only(self) -> None:
        """SecurityScanGate should only apply to GOVERN phase."""
        gate = SecurityScanGate(cwd=".")
        assert gate.applies_to == frozenset({Phase.GOVERN})
        assert gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.REVIEW)
        assert not gate.should_run(Phase.PLAN)

    @patch("subprocess.run")
    def test_passes_on_clean_code(self, mock_run: Mock, tmp_path: Path) -> None:
        """Gate should pass when bandit finds no issues."""
        mock_run.return_value = Mock(returncode=0, stdout="No issues identified.\n", stderr="")
        gate = SecurityScanGate(cwd=tmp_path)
        result = gate.evaluate(WorkItem(id="t"))
        assert result.passed
        assert result.message == "clean"

    @patch("subprocess.run")
    def test_fails_on_security_issues(self, mock_run: Mock, tmp_path: Path) -> None:
        """Gate should fail when bandit finds security issues."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="Issue: [B605] Possible shell injection\n",
            stderr="",
        )
        gate = SecurityScanGate(cwd=tmp_path)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert result.message == "violations found"


# -----------------------------------------------------------------------------
# TestCoverageGate tests
# -----------------------------------------------------------------------------


class TestTestCoverageGate:
    """Test TestCoverageGate coverage XML parsing."""

    def test_blocking_is_true_by_default(self) -> None:
        """TestCoverageGate should be blocking by default."""
        gate = TestCoverageGate(min_coverage=0.65)
        assert gate.blocking is True

    def test_applies_to_govern_only(self) -> None:
        """TestCoverageGate should only apply to GOVERN phase."""
        gate = TestCoverageGate(min_coverage=0.65)
        assert gate.applies_to == frozenset({Phase.GOVERN})
        assert gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.REVIEW)

    def test_fails_when_coverage_file_missing(self, tmp_path: Path) -> None:
        """Gate should fail when coverage.xml is not found."""
        gate = TestCoverageGate(min_coverage=0.8, coverage_file=tmp_path / "missing.xml")
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert result.blocking is True
        assert "not found" in result.message
        assert result.evidence["coverage_file"] == str(tmp_path / "missing.xml")

    def test_passes_when_coverage_above_threshold(self, tmp_path: Path) -> None:
        """Gate should pass when coverage is above threshold."""
        cov = tmp_path / "coverage.xml"
        cov.write_text('<?xml version="1.0" ?><coverage line-rate="0.82"/>')
        gate = TestCoverageGate(min_coverage=0.8, coverage_file=cov)
        result = gate.evaluate(WorkItem(id="t"))
        assert result.passed
        assert result.blocking is True
        assert result.evidence["rate"] == pytest.approx(0.82)
        assert result.evidence["threshold"] == pytest.approx(0.8)
        assert "82.0%" in result.message or "0.82" in result.message

    def test_fails_when_coverage_below_threshold(self, tmp_path: Path) -> None:
        """Gate should fail when coverage is below threshold."""
        cov = tmp_path / "coverage.xml"
        cov.write_text('<?xml version="1.0" ?><coverage line-rate="0.50"/>')
        gate = TestCoverageGate(min_coverage=0.8, coverage_file=cov)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert result.blocking is True
        assert result.evidence["rate"] == pytest.approx(0.50)
        assert result.evidence["threshold"] == pytest.approx(0.8)

    def test_exact_threshold_boundary(self, tmp_path: Path) -> None:
        """Gate should pass when coverage exactly equals threshold."""
        cov = tmp_path / "coverage.xml"
        cov.write_text('<?xml version="1.0" ?><coverage line-rate="0.80"/>')
        gate = TestCoverageGate(min_coverage=0.8, coverage_file=cov)
        result = gate.evaluate(WorkItem(id="t"))
        assert result.passed

    def test_handles_malformed_xml(self, tmp_path: Path) -> None:
        """Gate should fail gracefully on malformed XML."""
        cov = tmp_path / "coverage.xml"
        cov.write_text('<?xml version="1.0" ?><invalid xml here')
        gate = TestCoverageGate(min_coverage=0.8, coverage_file=cov)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert "failed to parse" in result.message
        assert "error" in result.evidence

    def test_handles_missing_line_rate_attribute(self, tmp_path: Path) -> None:
        """Gate should use 0.0 line-rate when attribute is missing."""
        cov = tmp_path / "coverage.xml"
        cov.write_text('<?xml version="1.0" ?><coverage></coverage>')
        gate = TestCoverageGate(min_coverage=0.8, coverage_file=cov)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        # When line-rate is missing, it defaults to 0.0
        assert result.evidence["rate"] == pytest.approx(0.0)

    def test_handles_zero_line_rate(self, tmp_path: Path) -> None:
        """Gate should fail when line-rate is zero."""
        cov = tmp_path / "coverage.xml"
        cov.write_text('<?xml version="1.0" ?><coverage line-rate="0.0"/>')
        gate = TestCoverageGate(min_coverage=0.01, coverage_file=cov)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed

    def test_handles_full_coverage(self, tmp_path: Path) -> None:
        """Gate should pass when coverage is 100%."""
        cov = tmp_path / "coverage.xml"
        cov.write_text('<?xml version="1.0" ?><coverage line-rate="1.0"/>')
        gate = TestCoverageGate(min_coverage=1.0, coverage_file=cov)
        result = gate.evaluate(WorkItem(id="t"))
        assert result.passed

    def test_creates_path_from_string(self, tmp_path: Path) -> None:
        """Gate should accept coverage_file as string path."""
        cov = tmp_path / "coverage.xml"
        cov.write_text('<?xml version="1.0" ?><coverage line-rate="1.0"/>')
        gate = TestCoverageGate(min_coverage=0.8, coverage_file=str(cov))
        result = gate.evaluate(WorkItem(id="t"))
        assert result.passed


# -----------------------------------------------------------------------------
# CriticReviewGate tests
# -----------------------------------------------------------------------------


class TestCriticReviewGate:
    """Test CriticReviewGate critic integration."""

    def test_passes_when_reviewer_returns_pass(self) -> None:
        """Gate should pass when reviewer returns 'pass'."""

        def reviewer(item: WorkItem) -> tuple[str, str]:
            return "pass", "looks good"

        gate = CriticReviewGate(reviewer)
        item = WorkItem(id="t")
        result = gate.evaluate(item)
        assert result.passed
        assert result.blocking is True
        assert result.gate == "critic_review"
        assert result.message == "looks good"
        assert result.evidence["status"] == "pass"

    def test_fails_when_reviewer_returns_retry(self) -> None:
        """Gate should fail when reviewer returns 'retry'."""

        def reviewer(item: WorkItem) -> tuple[str, str]:
            return "retry", "rework requested"

        gate = CriticReviewGate(reviewer)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert result.blocking is True
        assert result.evidence["status"] == "retry"
        assert result.message == "rework requested"

    def test_fails_when_reviewer_returns_block(self) -> None:
        """Gate should fail when reviewer returns 'block'."""

        def reviewer(item: WorkItem) -> tuple[str, str]:
            return "block", "critical issues found"

        gate = CriticReviewGate(reviewer)
        result = gate.evaluate(WorkItem(id="t"))
        assert not result.passed
        assert result.evidence["status"] == "block"

    def test_applies_to_review_only(self) -> None:
        """CriticReviewGate should only apply to REVIEW phase."""

        def reviewer(item: WorkItem) -> tuple[str, str]:
            return "pass", "ok"

        gate = CriticReviewGate(reviewer)
        assert gate.applies_to == frozenset({Phase.REVIEW})
        assert gate.should_run(Phase.REVIEW)
        assert not gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.PLAN)

    def test_block_is_blocking(self) -> None:
        """CriticReviewGate should always be blocking."""

        def reviewer(item: WorkItem) -> tuple[str, str]:
            return "pass", "ok"

        gate = CriticReviewGate(reviewer)
        assert gate.blocking is True

    def test_receives_work_item_in_reviewer_callable(self) -> None:
        """Reviewer callable should receive the work item being evaluated."""
        received_items: list[WorkItem] = []

        def reviewer(item: WorkItem) -> tuple[str, str]:
            received_items.append(item)
            return "pass", "ok"

        gate = CriticReviewGate(reviewer)
        item = WorkItem(id="test-item-123")
        gate.evaluate(item)
        assert len(received_items) == 1
        assert received_items[0].id == "test-item-123"


# -----------------------------------------------------------------------------
# Integration/Edge case tests
# -----------------------------------------------------------------------------


def test_all_gates_have_unique_names() -> None:
    """All gate classes should have unique names."""
    gates = [
        ContentGuardGate(min_bytes=10),
        LintGate(cwd="."),
        TypecheckGate(cwd="."),
        SecurityScanGate(cwd="."),
        TestCoverageGate(min_coverage=0.8),
    ]
    names = [g.name for g in gates]
    assert len(names) == len(set(names)), "Gate names should be unique"


def test_work_item_payload_can_be_any_content() -> None:
    """Work items should accept arbitrary payload content."""
    item = WorkItem(
        id="t",
        payload={
            "body": "test",
            "custom_field": [1, 2, 3],
            "nested": {"key": "value"},
        },
    )
    assert item.payload["custom_field"] == [1, 2, 3]
    assert item.payload["nested"]["key"] == "value"


# -----------------------------------------------------------------------------
# Phase filtering integration tests
# -----------------------------------------------------------------------------


class TestPhaseFiltering:
    """Test that all gates respect applies_to phase filtering."""

    def test_content_guard_gate_phases(self) -> None:
        """ContentGuardGate applies only to REVIEW and GOVERN."""
        gate = ContentGuardGate(min_bytes=10)
        assert gate.should_run(Phase.REVIEW)
        assert gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.PLAN)

    def test_lint_gate_phases(self) -> None:
        """LintGate applies only to REVIEW and GOVERN."""
        gate = LintGate(cwd=".")
        assert gate.should_run(Phase.REVIEW)
        assert gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.PLAN)

    def test_typecheck_gate_phases(self) -> None:
        """TypecheckGate applies only to REVIEW and GOVERN."""
        gate = TypecheckGate(cwd=".")
        assert gate.should_run(Phase.REVIEW)
        assert gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.PLAN)

    def test_security_scan_gate_phases(self) -> None:
        """SecurityScanGate applies only to GOVERN."""
        gate = SecurityScanGate(cwd=".")
        assert gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.REVIEW)
        assert not gate.should_run(Phase.PLAN)

    def test_test_coverage_gate_phases(self) -> None:
        """TestCoverageGate applies only to GOVERN."""
        gate = TestCoverageGate(min_coverage=0.8)
        assert gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.REVIEW)
        assert not gate.should_run(Phase.PLAN)

    def test_critic_review_gate_phases(self) -> None:
        """CriticReviewGate applies only to REVIEW."""

        def reviewer(item: WorkItem) -> tuple[str, str]:
            return "pass", "ok"

        gate = CriticReviewGate(reviewer)
        assert gate.should_run(Phase.REVIEW)
        assert not gate.should_run(Phase.GOVERN)
        assert not gate.should_run(Phase.PLAN)
