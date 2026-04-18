"""Quality-gate abstractions used by the phase controller.

A ``QualityGate`` evaluates a ``WorkItem`` at a phase boundary and returns
a ``GateResult``. Gates can be blocking (failure halts the transition) or
advisory (failure is recorded but the transition proceeds). Concrete
gates in this module delegate to existing subsystems so this module adds
no new behaviors — only a uniform evaluation surface.

Composition order is significant: the controller stops at the first
blocking failure, so cheaper gates (lint, content) should be listed
before expensive ones (coverage, review).
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.services.sdlc_phase import Phase, WorkItem
from src.tools.content_guards import is_low_value_content


@dataclass(frozen=True)
class GateResult:
    """Outcome of a single gate evaluation."""

    gate: str
    passed: bool
    blocking: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    message: str = ""


class QualityGate(ABC):
    """Evaluate a work item at a phase boundary."""

    name: str = "unnamed"
    blocking: bool = True
    #: Phases at which this gate fires. Empty means "all phases".
    applies_to: frozenset[Phase] = frozenset()

    def should_run(self, phase: Phase) -> bool:
        return not self.applies_to or phase in self.applies_to

    @abstractmethod
    def evaluate(self, item: WorkItem) -> GateResult: ...


# ---------------------------------------------------------------------------
# Concrete gates — delegate to existing subsystems; avoid re-implementing.
# ---------------------------------------------------------------------------


class ContentGuardGate(QualityGate):
    """Reject low-value or leakage-only payloads before they advance.

    Wraps ``src.tools.content_guards.is_low_value_content``. Looks at
    the ``body`` key of the work item's payload.
    """

    name = "content_guard"
    blocking = True
    applies_to = frozenset({Phase.REVIEW, Phase.GOVERN})

    def __init__(self, min_bytes: int = 40) -> None:
        self._min_bytes = min_bytes

    def evaluate(self, item: WorkItem) -> GateResult:
        body = str(item.payload.get("body", ""))
        low = is_low_value_content(body, min_bytes=self._min_bytes)
        return GateResult(
            gate=self.name,
            passed=not low,
            blocking=self.blocking,
            evidence={"body_len": len(body)},
            message="body is low-value or only leakage" if low else "ok",
        )


class _SubprocessGate(QualityGate):
    """Helper base for gates that shell out to a linter / typechecker."""

    cmd: tuple[str, ...] = ()
    name = "subprocess"
    blocking = False  # advisory by default

    def __init__(self, cwd: Path | str | None = None, *, blocking: bool | None = None) -> None:
        self._cwd = Path(cwd) if cwd else None
        if blocking is not None:
            self.blocking = blocking

    def evaluate(self, item: WorkItem) -> GateResult:
        try:
            completed = subprocess.run(
                list(self.cmd),
                cwd=self._cwd,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            return GateResult(
                gate=self.name,
                passed=False,
                blocking=self.blocking,
                evidence={"error": type(exc).__name__},
                message=f"{self.name} failed to run: {exc}",
            )
        return GateResult(
            gate=self.name,
            passed=completed.returncode == 0,
            blocking=self.blocking,
            evidence={
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-400:],
                "stderr_tail": completed.stderr[-400:],
            },
            message="clean" if completed.returncode == 0 else "violations found",
        )


class LintGate(_SubprocessGate):
    name = "lint"
    cmd = ("ruff", "check", "src", "tests")
    applies_to = frozenset({Phase.REVIEW, Phase.GOVERN})


class TypecheckGate(_SubprocessGate):
    name = "typecheck"
    cmd = ("mypy", "src")
    applies_to = frozenset({Phase.REVIEW, Phase.GOVERN})


class SecurityScanGate(_SubprocessGate):
    name = "security_scan"
    cmd = ("bandit", "-q", "-r", "src", "-x", "src/staged_agents")
    applies_to = frozenset({Phase.GOVERN})


class TestCoverageGate(QualityGate):
    """Parse ``coverage.xml`` (Cobertura) and assert a floor."""

    __test__ = False  # tell pytest this isn't a test class despite the name
    name = "test_coverage"
    blocking = True
    applies_to = frozenset({Phase.GOVERN})

    def __init__(self, min_coverage: float = 0.65, coverage_file: Path | str = "coverage.xml") -> None:
        self._min = min_coverage
        self._path = Path(coverage_file)

    def evaluate(self, item: WorkItem) -> GateResult:
        if not self._path.exists():
            return GateResult(
                gate=self.name,
                passed=False,
                blocking=self.blocking,
                evidence={"coverage_file": str(self._path)},
                message="coverage.xml not found — run coverage first",
            )
        try:
            import xml.etree.ElementTree as ET

            root = ET.parse(self._path).getroot()
            rate = float(root.attrib.get("line-rate", 0.0))
        except (ET.ParseError, ValueError, KeyError) as exc:
            return GateResult(
                gate=self.name,
                passed=False,
                blocking=self.blocking,
                evidence={"error": str(exc)},
                message="failed to parse coverage.xml",
            )
        passed = rate >= self._min
        return GateResult(
            gate=self.name,
            passed=passed,
            blocking=self.blocking,
            evidence={"rate": rate, "threshold": self._min},
            message=f"coverage {rate:.1%} vs threshold {self._min:.0%}",
        )


class CriticReviewGate(QualityGate):
    """Adapter around the Critic agent for REVIEW-phase enforcement.

    Accepts an injectable callable so tests don't need a real LLM runner.
    The callable receives the work item and returns
    ``("pass" | "retry" | "block", summary)``.
    """

    name = "critic_review"
    blocking = True
    applies_to = frozenset({Phase.REVIEW})

    def __init__(self, reviewer: Callable[[WorkItem], tuple[str, str]]) -> None:
        self._review = reviewer

    def evaluate(self, item: WorkItem) -> GateResult:
        status, summary = self._review(item)
        return GateResult(
            gate=self.name,
            passed=status == "pass",
            blocking=self.blocking,
            evidence={"status": status},
            message=summary,
        )


__all__ = [
    "ContentGuardGate",
    "CriticReviewGate",
    "GateResult",
    "LintGate",
    "QualityGate",
    "SecurityScanGate",
    "TestCoverageGate",
    "TypecheckGate",
]
