"""DSPyCodeGenerator — declarative code generation for Python, Kotlin, Java."""

from __future__ import annotations

import os
from typing import Any

from src.observability.logger import get_logger

logger = get_logger("dspy.code")


class DSPyCodeGenerator:
    """Declarative code generator using DSPy signatures.

    Falls back to heuristic template generation when DSPy/LM is unavailable.
    """

    def __init__(self) -> None:
        self._dspy = None
        self._module = None

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

            class CodeGenSignature(dspy.Signature):
                description = dspy.InputField(desc="What the code should do")
                language = dspy.InputField(desc="Programming language")
                context = dspy.InputField(desc="Additional context")
                code = dspy.OutputField(desc="Complete working code")

            self._module = dspy.ChainOfThought(CodeGenSignature)
            return True
        except Exception as exc:
            logger.warning("dspy unavailable for code generator: %s", exc)
            self._dspy = None
            return False

    def generate(
        self, description: str, language: str, context: dict[str, Any] | None = None
    ) -> str:
        ctx = context or {}
        context_str = "\n".join(f"{k}: {v}" for k, v in ctx.items())
        if self._ensure_dspy():
            try:
                pred = self._module(description=description, language=language, context=context_str)
                return pred.code.strip()
            except Exception as exc:
                logger.warning("dspy code gen failed: %s", exc)
        return self._fallback_generate(description, language)

    def _fallback_generate(self, description: str, language: str) -> str:
        desc_lower = description.lower()
        if language == "python":
            if "add" in desc_lower or "sum" in desc_lower or "+" in description:
                return f"# Generated Python\n# {description}\ndef add(a, b):\n    return a + b\n"
            if "class" in desc_lower or "object" in desc_lower:
                return f"# Generated Python\n# {description}\nclass Stub:\n    def __init__(self):\n        pass\n"
            return f"# Generated Python\n# {description}\ndef stub():\n    raise NotImplementedError()\n"
        elif language == "kotlin":
            if "add" in desc_lower or "sum" in desc_lower:
                return (
                    f"// Generated Kotlin\n// {description}\nfun add(a: Int, b: Int): Int = a + b\n"
                )
            return f"// Generated Kotlin\n// {description}\nfun main() {{}}\n"
        return f"// Generated {language}\n// {description}\n"

    def generate_with_tests(
        self, description: str, language: str, framework: str = "pytest"
    ) -> dict[str, str]:
        code = self.generate(description, language)
        if language == "python" and framework == "pytest":
            test = "import pytest\n\nfrom stub_module import stub\n\ndef test_stub():\n    with pytest.raises(NotImplementedError):\n        stub()\n"
        else:
            test = f"# Test for {description}"
        return {"code": code, "tests": test}


__all__ = ["DSPyCodeGenerator"]
