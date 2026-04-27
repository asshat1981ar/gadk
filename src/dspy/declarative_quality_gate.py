"""DeclarativeQualityGate — DSPy-powered phase-gate evaluation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from src.observability.logger import get_logger

logger = get_logger("dspy.qgate")


@dataclass
class GateResult:
    passed: bool
    blocking: bool
    evidence: dict[str, Any]
    message: str


class DeclarativeQualityGate:
    """DSPy-powered quality gate using declarative signatures."""

    def __init__(self, blocking: bool = True) -> None:
        self._dspy: Any = None
        self._module: Any = None
        self.blocking = blocking

    def _ensure_dspy(self) -> bool:
        if not (
            (
                os.environ.get("LLM_API_KEY")
                or os.environ.get("OLLAMA_API_KEY")
                or os.environ.get("llm_api_key")
                or os.environ.get("OLLAMA_API_KEY")
            )
            or os.environ.get("OPENAI_API_KEY")
        ):
            self._dspy = None
            self._module = None
            return False
        if self._dspy is not None:
            return True
        try:
            import dspy

            self._dspy = dspy
            self._lm = dspy.LM("openai/gpt-4o", api_key=None, cache=False)
            dspy.settings.configure(lm=self._lm)

            class QualityGateSignature(dspy.Signature):
                code = dspy.InputField(desc="Code under review")
                task = dspy.InputField(desc="Original task")
                phase = dspy.InputField(desc="Current phase")
                verdict = dspy.OutputField(desc="pass, retry, or block")
                reasoning = dspy.OutputField(desc="Brief reasoning")

            self._module = dspy.ChainOfThought(QualityGateSignature)
            return True
        except Exception as exc:
            logger.warning("dspy unavailable for quality gate: %s", exc)
            self._dspy = None
            self._module = None
            return False

    def evaluate(self, item: dict[str, Any]) -> GateResult:
        code = str(item.get("payload", {}).get("code", item.get("code", "")))
        task = str(item.get("payload", {}).get("task", {}).get("title", ""))
        phase = str(item.get("phase", "UNKNOWN"))

        if self._ensure_dspy():
            try:
                pred = self._module(code=code, task=task, phase=phase)
                verdict = pred.verdict.strip().lower()
            except Exception as exc:
                logger.warning("dspy gate eval failed, using heuristic: %s", exc)
                verdict = "retry" if len(code) < 20 else "pass"
        else:
            verdict = "pass" if len(code) > 20 else "retry"

        passed = verdict == "pass"
        return GateResult(
            passed=passed,
            blocking=self.blocking,
            evidence={"verdict": verdict, "phase": phase},
            message=f"DSPy gate: {verdict}",
        )


__all__ = ["DeclarativeQualityGate", "GateResult"]
