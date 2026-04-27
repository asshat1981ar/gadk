"""Reflection node for graph-based autonomy — structured evaluation v2.

Replaces the stub with structured gap analysis backed by MemoryGraph.
Uses success criteria to evaluate agent outputs, queries past failures
for contextual feedback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReflectionResult:
    """Structured output of a reflection evaluation."""

    status: str  # success, failure, partial
    gaps: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    confidence: float = 1.0


class ReflectionNode:
    """Structured reflection node with MemoryGraph integration.

    Evaluates agent outputs against success criteria. If MemoryGraph is
    available, queries historical similar failures for contextual feedback.
    """

    def __init__(self, memory_graph=None):
        self._memory = memory_graph

    def evaluate(
        self,
        task: str,
        phase: str,
        output_code: str | None = None,
        success_criteria: list[str] | None = None,
    ) -> ReflectionResult:
        """Evaluate output against success criteria."""
        gaps: list[str] = []
        suggestions: list[str] = []

        criteria = success_criteria or []
        for criterion in criteria:
            if not self._check_criterion(output_code or "", criterion):
                gaps.append(f"Missing criterion: {criterion}")
                suggestions.append(f"Add implementation for: {criterion}")

        if gaps:
            return ReflectionResult(
                status="failure",
                gaps=gaps,
                suggestions=suggestions,
                confidence=max(0.5, 1.0 - len(gaps) * 0.2),
            )
        return ReflectionResult(status="success", confidence=1.0)

    def _check_criterion(self, output: str, criterion: str) -> bool:
        """Check if criterion is met in output."""
        keywords = [w.lower() for w in criterion.split() if len(w) > 3]
        output_lower = output.lower()
        return any(kw in output_lower for kw in keywords)

    def reflect(
        self,
        task: str,
        phase: str,
        state: dict[str, Any],
        success_criteria: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Full reflection with MemoryGraph historical context."""
        output = state.get("output", "")
        criteria = list((success_criteria or {}).values())
        result = self.evaluate(task, phase, output, criteria)

        memory_enhanced = False
        historical_notes: list[str] = []
        if self._memory:
            similar = self._memory.find_similar(task, max_results=3)
            for s in similar:
                from src.memory.graph_store import NodeType

                # Find agent that executed similar task via predecessors
                # (edge direction: agent --executed_by--> task)
                preds = self._memory._store.predecessors(s["id"])
                for pred in preds:
                    if pred.get("type") == NodeType.AGENT.value:
                        history = self._memory.get_agent_history(pred["name"])
                        for h in history:
                            if h.get("outcome") == "failure":
                                historical_notes.append(
                                    f"Similar task '{h['task']}' previously failed"
                                )
                                memory_enhanced = True

        return {
            "reflection": {
                "status": result.status,
                "gaps": result.gaps,
                "suggestions": result.suggestions,
                "confidence": result.confidence,
                "historical_notes": historical_notes,
            },
            "memory_enhanced": memory_enhanced,
            "phase": phase,
            "task": task,
        }


__all__ = ["ReflectionNode", "ReflectionResult"]
