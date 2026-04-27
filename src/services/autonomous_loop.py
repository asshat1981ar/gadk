"""Main autonomous execution loop — self-correcting graph workflow.

Wires MemoryGraph + BlueprintPlanner + ReflectionNode into a deterministic
loop: plan -> execute (simulate) -> reflect -> record -> (retry if needed).
"""

from __future__ import annotations

from typing import Any

from src.memory.memory_graph import MemoryGraph, TaskOutcome
from src.orchestration.blueprint_planner import BlueprintPlanner
from src.orchestration.reflection_node import ReflectionNode


class AutonomousLoop:
    """Self-correcting execution loop over a MemoryGraph-backed workflow.

    High-level flow for each goal:
      1. Planner generates a WorkflowBlueprint DAG.
      2. Each step is "executed" (simulated) and outcomes gathered.
      3. ReflectionNode evaluates success criteria / gaps.
      4. If gaps: replan and retry up to max_retries.
      5. Final outcome (success / failure) recorded in MemoryGraph.
    """

    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        memory_graph: MemoryGraph | None = None,
        planner: BlueprintPlanner | None = None,
        reflector: ReflectionNode | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        self.memory = memory_graph or MemoryGraph()
        self.planner = planner or BlueprintPlanner(memory_graph=self.memory)
        self.reflector = reflector or ReflectionNode(memory_graph=self.memory)
        self.max_retries = max_retries

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run(self, goal: str, success_criteria: dict[str, str] | None = None) -> dict[str, Any]:
        """Execute the autonomous loop for *goal* and return result dict.

        Returns a dict with keys:
            status        : "success" | "max_retries"
            goal          : original goal string
            attempts      : number of loop iterations performed
            validated     : True if reflection passed on final attempt
            blueprint     : serialised blueprint (goal + steps)
            reflection    : last reflection dict (gaps, suggestions, …)
            gaps          : list of gap strings (empty on success)
        """
        blueprint = self.planner.plan(goal)
        current_state: dict[str, Any] = {
            "task": goal,
            "output": "",
            "attempts": 0,
        }

        for attempt in range(1, self.max_retries + 1):
            # Simulate execution by aggregating expected outputs
            current_state["output"] = self._simulate_execution(blueprint)
            current_state["attempts"] = attempt

            reflection = self.reflector.reflect(
                task=goal,
                phase="OPERATE",
                state=current_state,
                success_criteria=success_criteria or {},
            )

            ref = reflection.get("reflection", {})
            if ref.get("status") == "success":
                self._record_outcome(goal, TaskOutcome.SUCCESS, attempt)
                return self._build_result(
                    status="success",
                    goal=goal,
                    attempt=attempt,
                    validated=True,
                    blueprint=blueprint,
                    reflection=ref,
                )

            # Not validated — replan from gaps and retry
            current_state["gaps"] = ref.get("gaps", [])
            blueprint = self.planner.replan(blueprint, reflection)

        # Exhausted retries
        self._record_outcome(goal, TaskOutcome.FAILURE, self.max_retries)
        return self._build_result(
            status="max_retries",
            goal=goal,
            attempt=self.max_retries,
            validated=False,
            blueprint=blueprint,
            reflection=ref,
            gaps=current_state.get("gaps", []),
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _simulate_execution(self, blueprint) -> str:
        """Aggregate expected outputs from blueprint steps as faux execution.

        In a future iteration this will dispatch to real agent nodes.
        """
        try:
            ordered = blueprint.topological_order()
        except ValueError:
            ordered = blueprint.steps
        outputs = []
        for step in ordered:
            outputs.append(f"[{step.agent}] {step.action} -> {step.expected_output}")
        return "\n".join(outputs)

    def _record_outcome(self, goal: str, outcome: TaskOutcome, attempt: int) -> None:
        """Persist the task outcome to MemoryGraph."""
        self.memory.record_task(
            task_name=goal,
            agent_name="AutonomousLoop",
            outcome=outcome,
            metadata={"retries_used": attempt},
        )

    def _build_result(
        self,
        *,
        status: str,
        goal: str,
        attempt: int,
        validated: bool,
        blueprint,
        reflection: dict[str, Any],
        gaps: list[str] | None = None,
    ) -> dict[str, Any]:
        """Normalise loop result dict for callers."""
        return {
            "status": status,
            "goal": goal,
            "attempts": attempt,
            "validated": validated,
            "blueprint": {
                "goal": blueprint.goal,
                "steps": [
                    {
                        "id": s.id,
                        "action": s.action,
                        "agent": s.agent,
                        "depends_on": s.depends_on,
                    }
                    for s in blueprint.steps
                ],
            },
            "reflection": reflection,
            "gaps": gaps or [],
        }


__all__ = ["AutonomousLoop"]
