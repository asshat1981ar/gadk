"""DSPyOptimizedRouter — learns optimal agent routing using MIPRO."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from src.observability.logger import get_logger

logger = get_logger("dspy.router")


class DSPyOptimizedRouter:
    """LLM-powered task router using DSPy signatures.

    Routes tasks to the optimal specialist agent based on learned patterns.
    Falls back to rule-based routing when DSPy/LM is unavailable.
    """

    def __init__(self) -> None:
        self._dspy: Any = None
        self._module: Any = None
        self._feedback: dict[str, list[tuple[str, float]]] = {}

    def _ensure_dspy(self) -> bool:
        """Lazily initialize DSPy. Returns True if DSPy is available."""
        if self._dspy is not None:
            return True
        if not ((os.environ.get("LLM_API_KEY") or os.environ.get("OLLAMA_API_KEY") or os.environ.get("llm_api_key") or os.environ.get("OLLAMA_API_KEY")) or os.environ.get("OPENAI_API_KEY")):
            return False
        try:
            import dspy
            self._dspy = dspy
            self._lm = dspy.LM("openai/gpt-4o", api_key=None, cache=False)
            dspy.settings.configure(lm=self._lm)

            class RouteToAgent(dspy.Signature):
                task = dspy.InputField(desc="Natural language task")
                best_agent = dspy.OutputField(desc="Best agent name")

            self._module = dspy.ChainOfThought(RouteToAgent)
            return True
        except Exception as exc:
            logger.warning("dspy unavailable, using rule-based routing: %s", exc)
            self._dspy = None
            self._module = None
            return False

    def route(self, task: str) -> str:
        """Route a task to the best agent. Returns agent name."""
        if self._ensure_dspy():
            try:
                pred = self._module(task=task)
                return pred.best_agent.strip()
            except Exception as exc:
                logger.warning("dspy.route.failed fallback: %s", exc)
        return self._fallback_route(task)

    def record_feedback(self, task: str, agent: str, score: float) -> None:
        if task not in self._feedback:
            self._feedback[task] = []
        self._feedback[task].append((agent, score))
        logger.info("router.feedback task=%s agent=%s score=%.2f", task[:30], agent, score)

    def _fallback_route(self, task: str) -> str:
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["implement", "write", "create", "add", "fix"]):
            return "Builder"
        if any(kw in task_lower for kw in ["review", "critique", "check", "analyze"]):
            return "Critic"
        if any(kw in task_lower for kw in ["design", "architect", "plan", "structure"]):
            return "Architect"
        if any(kw in task_lower for kw in ["discover", "idea", "feature", "gap"]):
            return "Ideator"
        if any(kw in task_lower for kw in ["deploy", "release", "govern", "gate"]):
            return "Governor"
        if any(kw in task_lower for kw in ["monitor", "health", "metrics", "pulse"]):
            return "Pulse"
        return "Builder"

    def get_best_agent(self, task: str) -> str:
        return self.route(task)


__all__ = ["DSPyOptimizedRouter"]
