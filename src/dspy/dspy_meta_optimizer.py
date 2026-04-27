"""DSPyMetaOptimizer — automatic prompt and signature optimization."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from src.observability.logger import get_logger

logger = get_logger("dspy.meta")


class DSPyMetaOptimizer:
    """Meta-layer optimizer that automatically tunes DSPy signatures via MIPRO."""

    def __init__(self) -> None:
        self._dspy: Any = None
        self._module: Any = None

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

            class SigOpt(dspy.Signature):
                input_spec = dspy.InputField(desc="Input field description")
                output_spec = dspy.InputField(desc="Output field description")
                examples = dspy.InputField(desc="Example task-output pairs")
                optimized = dspy.OutputField(desc="Improved field descriptions")

            self._module = dspy.ChainOfThought(SigOpt)
            return True
        except Exception as exc:
            logger.warning("dspy unavailable for meta optimizer: %s", exc)
            self._dspy = None
            return False

    def optimize_signature(
        self, signature: dict[str, str], tasks: list[dict[str, Any]]
    ) -> dict[str, str]:
        inp = signature.get("input", "task description")
        out = signature.get("output", "solution")
        examples_str = "\n".join(
            f"Input: {t.get('input', '')} -> Output: {t.get('output', '')}" for t in tasks[:5]
        )
        if self._ensure_dspy():
            try:
                pred = self._module(input_spec=inp, output_spec=out, examples=examples_str)
                optimized_text = pred.optimized.strip()
            except Exception as exc:
                logger.warning("dspy meta optimize failed: %s", exc)
                optimized_text = out
        else:
            optimized_text = out
        return {"input": inp, "output": optimized_text}

    def bootstrap(self, tasks: list[dict[str, Any]], num_demos: int = 3) -> dict[str, str]:
        if not tasks:
            return {"input": "task", "output": "solution"}
        return self.optimize_signature(
            {"input": "task description", "output": "task output"}, tasks
        )


__all__ = ["DSPyMetaOptimizer"]
