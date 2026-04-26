"""MetaLearningOrchestrator — self-optimizing orchestration pipeline."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from src.observability.logger import get_logger

logger = get_logger("dspy.orchestrator")


class MetaLearningOrchestrator:
    """Self-optimizing orchestration pipeline using DSPy."""

    def __init__(self) -> None:
        self._dspy: Any = None
        self._plan_module: Any = None
        self._improve_module: Any = None
        self._iteration_count = 0

    def _ensure_dspy(self) -> bool:
        if not ((os.environ.get("LLM_API_KEY") or os.environ.get("OLLAMA_API_KEY") or os.environ.get("llm_api_key") or os.environ.get("OLLAMA_API_KEY")) or os.environ.get("OPENAI_API_KEY")):
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

            class OrchestrationPlanSignature(dspy.Signature):
                goal = dspy.InputField(desc="High-level goal")
                constraints = dspy.InputField(desc="Constraints")
                plan = dspy.OutputField(desc="Orchestration plan with steps")

            class SelfImproveSignature(dspy.Signature):
                plan = dspy.InputField(desc="Current plan")
                feedback = dspy.InputField(desc="Feedback to improve")
                improved_plan = dspy.OutputField(desc="Improved plan")

            self._plan_module = dspy.ChainOfThought(OrchestrationPlanSignature)
            self._improve_module = dspy.ChainOfThought(SelfImproveSignature)
            return True
        except Exception as exc:
            logger.warning("dspy unavailable for orchestrator: %s", exc)
            self._dspy = None
            return False

    def orchestrate(self, goal: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
        constraints = constraints or {}
        constraints_str = ", ".join(f"{k}={v}" for k, v in constraints.items())
        self._iteration_count += 1

        if self._ensure_dspy():
            try:
                pred = self._plan_module(goal=goal, constraints=constraints_str)
                plan_text = pred.plan.strip()
            except Exception as exc:
                logger.warning("dspy orchestrate failed: %s", exc)
                plan_text = self._fallback_plan(goal)
        else:
            plan_text = self._fallback_plan(goal)

        return self._parse_plan(plan_text, goal)

    def self_improve(self, plan: dict[str, Any], feedback: dict[str, Any]) -> dict[str, Any]:
        plan_str = str(plan)
        feedback_str = f"score={feedback.get('score', '?')}, notes={feedback.get('notes', '')}"

        if self._ensure_dspy():
            try:
                pred = self._improve_module(plan=plan_str, feedback=feedback_str)
                improved_text = pred.improved_plan.strip()
            except Exception as exc:
                logger.warning("dspy self_improve failed: %s", exc)
                return plan
        else:
            return plan

        return self._parse_plan(improved_text, plan.get("goal", ""))

    def _parse_plan(self, plan_text: str, goal: str) -> dict[str, Any]:
        steps = []
        for i, line in enumerate(plan_text.split("\n")):
            if line.strip():
                steps.append({"step": i + 1, "description": line.strip()})
        return {"goal": goal, "steps": steps, "iterations": self._iteration_count}

    def _fallback_plan(self, goal: str) -> str:
        return f"1. Analyze: {goal}\n2. Route to agent\n3. Execute and review"


__all__ = ["MetaLearningOrchestrator"]
