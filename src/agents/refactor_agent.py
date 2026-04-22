"""Refactor Agent — autonomous code refactoring using graph-based workflow."""
from __future__ import annotations

from typing import Any

from src.orchestration.blueprint_planner import BlueprintPlanner
from src.orchestration.reflection_node import ReflectionNode


class RefactorAgentNode:
    """Autonomous Refactor Agent using the v2 graph components.

    Combines BlueprintPlanner (deterministic workflow) with ReflectionNode
    (gap analysis) to produce self-correcting refactor plans.
    """

    def __init__(self):
        self.planner = BlueprintPlanner()
        self.reflector = ReflectionNode()

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        """Analyze task, generate refactor blueprint, reflect on approach."""
        task = state.get("task", "Improve GADK codebase")

        # Step 1: Generate deterministic refactor blueprint
        blueprint = self.planner.plan(f"Refactor: {task}")

        # Step 2: Reflect on the blueprint for gaps
        reflect_state = {
            "task": task,
            "phase": "REFACTOR",
            "memory": state.get("memory", {}),
            "reflection": state.get("reflection", []),
        }
        reflected = self.reflector.invoke(reflect_state)

        # Step 3: Validate blueprint has required steps
        steps_valid = len(blueprint.steps) >= 2

        return {
            "blueprint": {
                "goal": blueprint.goal,
                "steps": [(s.action, s.agent) for s in blueprint.steps],
            },
            "reflection": reflected.get("reflection", []),
            "validated": steps_valid,
            "agent": "refactor",
            "next_action": "implement" if steps_valid else "abort",
            "memory": reflected.get("memory", {}),
        }


__all__ = ["RefactorAgentNode"]
