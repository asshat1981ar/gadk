"""Reflection node for graph-based autonomy — replaces SelfPromptEngine.

Uses structured thinking (MCP sequential_thinking when available, local
rule-based fallback) to perform gap analysis on the current workflow state.
"""
from __future__ import annotations

from typing import Any

# Try to wire MCP sequential_thinking; graceful fallback if unavailable
try:
    from mcp_sequential_thinking import sequentialthinking

    SEQUENTIAL_THINKING_AVAILABLE = True
except ImportError:
    SEQUENTIAL_THINKING_AVAILABLE = False
    sequentialthinking = None  # type: ignore[assignment]


class ReflectionNode:
    """Reflection node for graph-based autonomy.

    Performs structured gap analysis on the current workflow state.
    Uses MCP sequential_thinking when available, falls back to rule-based
    gap detection otherwise.
    """

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        """Perform reflection and gap analysis on current state."""
        task = state.get("task", "Improve autonomous software creation")
        phase = state.get("phase", "unknown")

        if SEQUENTIAL_THINKING_AVAILABLE and sequentialthinking:
            # Use MCP sequential thinking for structured reflection
            thought = (
                f"Analyze the current autonomous software creation system for gaps. "
                f"Task: {task}. Current phase: {phase}. "
                f"Identify: (1) rigid phase transitions, (2) missing self-correction, "
                f"(3) context loss between cycles. "
                f"Memory: {state.get('memory', {})}"
            )
            try:
                result = sequentialthinking(
                    thought=thought,
                    next_thought_needed=False,
                    thought_number=1,
                    total_thoughts=1,
                )
                reflection_text = result.get("thought", self._rule_based_gap_analysis(task, phase))
            except Exception:
                # MCP call failed — fall back to rule-based
                reflection_text = self._rule_based_gap_analysis(task, phase)
        else:
            reflection_text = self._rule_based_gap_analysis(task, phase)

        reflection = [reflection_text]

        return {
            "reflection": reflection,
            "memory": {
                **state.get("memory", {}),
                "last_reflection": reflection_text,
                "gaps_identified": reflection_text.lower().count("gap"),
                "reflection_phase": phase,
            },
        }

    def _rule_based_gap_analysis(self, task: str, phase: str) -> str:
        """Rule-based fallback gap analysis when MCP is unavailable."""
        gaps: list[str] = []

        # Detect rigid phase transition issues
        if phase in ("PLAN", "ARCHITECT"):
            gaps.append("rigid phase transitions — consider dynamic routing")

        # Detect missing self-correction
        if phase in ("IMPLEMENT", "REVIEW"):
            gaps.append("limited self-correction between implement and review")

        # Detect context loss
        gaps.append(f"task '{task}' may suffer from context loss between cycles")

        gap_str = "; ".join(gaps) if gaps else "No critical gaps identified"
        return f"GAP ANALYSIS [{phase}]: {gap_str}."


__all__ = ["ReflectionNode", "SEQUENTIAL_THINKING_AVAILABLE"]
