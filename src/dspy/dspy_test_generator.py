"""DSPyTestGenerator — automated test generation from code."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from src.observability.logger import get_logger

logger = get_logger("dspy.test")


class DSPyTestGenerator:
    """Automated test generator using DSPy."""

    def __init__(self) -> None:
        self._dspy: Any = None
        self._module: Any = None

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

            class TestGenSignature(dspy.Signature):
                source_code = dspy.InputField(desc="Source code to test")
                language = dspy.InputField(desc="Programming language")
                min_coverage = dspy.InputField(desc="Minimum coverage target")
                tests = dspy.OutputField(desc="Complete test code with assertions")

            self._module = dspy.ChainOfThought(TestGenSignature)
            return True
        except Exception as exc:
            logger.warning("dspy unavailable for test generator: %s", exc)
            self._dspy = None
            return False

    def generate(self, source_code: str, language: str, min_coverage: float = 0.7) -> str:
        if self._ensure_dspy():
            try:
                pred = self._module(
                    source_code=source_code,
                    language=language,
                    min_coverage=str(min_coverage)
                )
                return pred.tests.strip()
            except Exception as exc:
                logger.warning("dspy test gen failed: %s", exc)
        return self._fallback_tests(source_code, language)

    def _fallback_tests(self, source_code: str, language: str) -> str:
        if language == "python":
            return f"import pytest\n# Tests for:\n# {source_code[:100]}\n\ndef test_placeholder():\n    assert True"
        elif language == "kotlin":
            return "// Kotlin tests\nfun testPlaceholder() {\n    assert(true)\n}"
        return f"// {language} tests"


__all__ = ["DSPyTestGenerator"]
