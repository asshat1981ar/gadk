"""Refactor Agent v2 — autonomous code refactoring with self-correction loop."""

from __future__ import annotations

from typing import Any

from src.orchestration.blueprint_planner import BlueprintPlanner
from src.orchestration.reflection_node import ReflectionNode
from src.memory.memory_graph import MemoryGraph, TaskOutcome


class RefactorAgentNode:
    """Autonomous Refactor Agent using the v2 graph components.

    Combines BlueprintPlanner (deterministic DAG), ReflectionNode (structured
evaluation), and MemoryGraph (persistent contextual memory) into a
self-correcting loop: plan → execute → reflect → (if fail) replan → retry.
    """

    MAX_RETRIES = 3

    def __init__(self, memory_graph: MemoryGraph | None = None):
        self.planner = BlueprintPlanner(memory_graph=memory_graph)
        self.reflector = ReflectionNode(memory_graph=memory_graph)
        self.memory = memory_graph or MemoryGraph()

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        """Single-pass: generate blueprint and reflect on gaps."""
        task = state.get("task", "Improve GADK codebase")

        blueprint = self.planner.plan(f"Refactor: {task}")
        reflect_state = self.reflector.reflect(
            task=task,
            phase="REFACTOR",
            state=state,
            success_criteria={},
        )

        validated = reflect_state["reflection"]["status"] != "failure"

        return {
            "blueprint": {
                "goal": blueprint.goal,
                "steps": [(s.id, s.action, s.agent, s.depends_on) for s in blueprint.steps],
                "requires_reflection": blueprint.requires_reflection,
            },
            "reflection": reflect_state.get("reflection", {}),
            "validated": validated,
            "agent": "refactor",
            "next_action": "implement" if validated else "abort",
            "memory": reflect_state.get("memory", {}),
        }

    def invoke_with_correction(self, state: dict[str, Any]) -> dict[str, Any]:
        """Self-correcting loop: plan → reflect → (retry if gaps)."""
        task = state.get("task", "Refactor codebase")
        attempts = state.get("attempts", 0)

        blueprint = self.planner.plan(task)
        current_state = dict(state)

        while attempts < self.MAX_RETRIES:
            reflection = self.reflector.reflect(
                task=task,
                phase="REFACTOR",
                state=current_state,
                success_criteria={},
            )

            if reflection["reflection"]["status"] == "success":
                self.memory.record_task(
                    task_name=task,
                    agent_name="RefactorAgent",
                    outcome=TaskOutcome.SUCCESS,
                )
                return {
                    "status": "success",
                    "attempts": attempts + 1,
                    "blueprint": {
                        "goal": blueprint.goal,
                        "steps": [(s.id, s.action, s.agent) for s in blueprint.steps],
                    },
                    "reflection": reflection["reflection"],
                }

            # Generate revised plan from gaps
            blueprint = self.planner.replan(
                blueprint,
                reflection,
            )
            attempts += 1
            current_state["attempts"] = attempts
            current_state["gaps"] = reflection["reflection"]["gaps"]

        self.memory.record_task(
            task_name=task,
            agent_name="RefactorAgent",
            outcome=TaskOutcome.FAILURE,
        )
        return {
            "status": "max_retries",
            "attempts": attempts,
            "blueprint": {
                "goal": blueprint.goal,
                "steps": [(s.id, s.action, s.agent) for s in blueprint.steps],
            },
            "gaps": current_state.get("gaps", []),
        }


__all__ = ["RefactorAgentNode"]
