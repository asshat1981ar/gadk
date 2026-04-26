"""DSPyAdaptiveRAG — adaptive retrieval with self-correction."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from src.observability.logger import get_logger

logger = get_logger("dspy.rag")


class DSPyAdaptiveRAG:
    """Adaptive RAG using DSPy for retrieval and self-correction."""

    def __init__(self) -> None:
        self._dspy: Any = None
        self._retrieve: Any = None
        self._correct: Any = None
        self._corpus: list[dict[str, str]] = []

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

            class RAGQuerySignature(dspy.Signature):
                query = dspy.InputField(desc="Natural language query")
                context = dspy.InputField(desc="Additional context")
                documents = dspy.OutputField(desc="Relevant document summaries")
                confidence = dspy.OutputField(desc="Confidence score 0.0-1.0")

            class SelfCorrectionSignature(dspy.Signature):
                initial_results = dspy.InputField(desc="Initial retrieval results")
                critique = dspy.InputField(desc="Critique of results")
                corrected_results = dspy.OutputField(desc="Improved results")

            self._retrieve = dspy.ChainOfThought(RAGQuerySignature)
            self._correct = dspy.ChainOfThought(SelfCorrectionSignature)
            return True
        except Exception as exc:
            logger.warning("dspy unavailable for RAG: %s", exc)
            self._dspy = None
            return False

    def load_corpus(self, documents: list[dict[str, str]]) -> None:
        self._corpus = documents
        logger.info("rag.corpus.loaded count=%d", len(documents))

    def query(self, query: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ctx = context or {}
        if self._ensure_dspy():
            try:
                pred = self._retrieve(query=query, context=str(ctx))
                docs = pred.documents.strip() if pred.documents else ""
                confidence = float(pred.confidence) if pred.confidence else 0.5
            except Exception as exc:
                logger.warning("dspy rag query failed: %s", exc)
                docs = ""
                confidence = 0.0
        else:
            docs = f"Result for: {query}"
            confidence = 0.5
        return [{"content": docs, "score": confidence, "query": query}]

    def self_correct(self, results: list[dict[str, Any]], critique: str) -> list[dict[str, Any]]:
        if self._ensure_dspy():
            try:
                initial_str = "\n".join(f"- {r.get('content', '')[:200]}" for r in results)
                pred = self._correct(initial_results=initial_str, critique=critique)
                corrected = pred.corrected_results.strip()
                return [{"content": corrected, "score": 0.85, "corrected": True}]
            except Exception as exc:
                logger.warning("dspy rag self_correct failed: %s", exc)
        return results


__all__ = ["DSPyAdaptiveRAG"]
