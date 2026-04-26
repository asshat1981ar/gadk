"""MultiAgentEnsemble — routes to multiple agents, selects best."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from src.observability.logger import get_logger

logger = get_logger("dspy.ensemble")


class MultiAgentEnsemble:
    """Multi-agent ensemble: run task through multiple agents, select best via DSPy."""

    def __init__(self, agents: list[str]) -> None:
        self.agents = agents
        self._dspy: Any = None
        self._selector: Any = None

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

            class EnsembleSelectionSignature(dspy.Signature):
                responses = dspy.InputField(desc="List of agent responses")
                task = dspy.InputField(desc="Original task")
                best_response = dspy.OutputField(desc="Best response and reasoning")
                best_agent = dspy.OutputField(desc="Name of best agent")

            self._selector = dspy.ChainOfThought(EnsembleSelectionSignature)
            return True
        except Exception as exc:
            logger.warning("dspy unavailable for ensemble: %s", exc)
            self._dspy = None
            return False

    def run_all(self, task: str) -> list[dict[str, Any]]:
        results = []
        for agent in self.agents:
            try:
                output = self._call_agent(agent, task)
                results.append({"agent": agent, "output": output, "score": self._score_output(output)})
            except Exception as exc:
                logger.warning("ensemble agent failed agent=%s: %s", agent, exc)
                results.append({"agent": agent, "output": "", "score": 0.0, "error": str(exc)})
        return results

    def select_best(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        if not results:
            return {"agent": "none", "output": "", "score": 0.0}
        if len(results) == 1:
            return results[0]
        if self._ensure_dspy():
            try:
                task = results[0].get("task", "complete this task")
                responses_str = "\n".join(f"[{r['agent']}]: {r.get('output', '')[:200]}" for r in results)
                pred = self._selector(responses=responses_str, task=task)
                best_agent = pred.best_agent.strip()
                for r in results:
                    if r["agent"] == best_agent:
                        r["score"] = r.get("score", 0.9) + 0.1
                        return r
            except Exception as exc:
                logger.warning("ensemble select_best failed: %s", exc)
        return max(results, key=lambda r: r.get("score", 0.0))

    def _call_agent(self, agent: str, task: str) -> str:
        return f"[{agent}] executed: {task[:50]}... (simulated)"

    def _score_output(self, output: str) -> float:
        if not output or len(output) < 10:
            return 0.1
        return min(0.9, 0.5 + len(output) / 1000)


__all__ = ["MultiAgentEnsemble"]
