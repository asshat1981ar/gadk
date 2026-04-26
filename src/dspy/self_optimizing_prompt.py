"""SelfOptimizingPrompt — MIPRO-based prompt self-improvement."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from src.observability.logger import get_logger

logger = get_logger("dspy.prompt")


class SelfOptimizingPrompt:
    """Self-improving prompt system using DSPy MIPRO."""

    def __init__(self) -> None:
        self._dspy: Any = None
        self._module: Any = None
        self._prompt_cache: dict[str, str] = {}

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

            class PromptOptimizerSignature(dspy.Signature):
                task = dspy.InputField(desc="Task description")
                feedback_history = dspy.InputField(desc="Previous attempts with scores")
                optimized_prompt = dspy.OutputField(desc="Improved prompt")

            self._module = dspy.ChainOfThought(PromptOptimizerSignature)
            return True
        except Exception as exc:
            logger.warning("dspy unavailable for prompt optimizer: %s", exc)
            self._dspy = None
            self._module = None
            return False

    def optimize(self, task: str, feedback_history: list[dict[str, Any]]) -> str:
        cache_key = f"{task}:{len(feedback_history)}"
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        history_str = self._format_history(feedback_history)

        if self._ensure_dspy():
            try:
                pred = self._module(task=task, feedback_history=history_str)
                optimized = pred.optimized_prompt.strip()
            except Exception as exc:
                logger.warning("dspy prompt optimize failed: %s", exc)
                optimized = self._fallback_prompt(task)
        else:
            optimized = self._fallback_prompt(task)

        self._prompt_cache[cache_key] = optimized
        return optimized

    def _fallback_prompt(self, task: str) -> str:
        return f"Task: {task}\n\nInstructions: Complete this task thoroughly and carefully."

    def _format_history(self, history: list[dict[str, Any]]) -> str:
        if not history:
            return "No previous attempts."
        return "\n".join(
            f"- Score {h.get('score', '?')}: {h.get('prompt', h.get('task', ''))[:100]}"
            for h in history[-5:]
        )


__all__ = ["SelfOptimizingPrompt"]
