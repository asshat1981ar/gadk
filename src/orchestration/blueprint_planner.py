"""Deterministic DAG workflow planner with reflection hooks.

Generates structured execution plans (directed acyclic graphs) from
natural-language goals using keyword matching + complexity heuristics.
Reflection hooks enable self-correction loops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStep:
    """A single step in a workflow DAG."""

    id: str
    action: str
    agent: str
    inputs: dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    depends_on: list[str] = field(default_factory=list)


@dataclass
class WorkflowBlueprint:
    """A deterministic workflow plan represented as a DAG."""

    goal: str
    steps: list[WorkflowStep] = field(default_factory=list)
    estimated_duration: str = "unknown"
    requires_reflection: bool = False

    def step_by_id(self, step_id: str) -> WorkflowStep | None:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def topological_order(self) -> list[WorkflowStep]:
        """Return steps in dependency order (Kahn's algorithm)."""
        in_degree = {s.id: 0 for s in self.steps}
        adj = {s.id: [] for s in self.steps}
        for s in self.steps:
            for dep in s.depends_on:
                adj[dep].append(s.id)
                in_degree[s.id] += 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        order = []
        while queue:
            current = queue.pop(0)
            step = self.step_by_id(current)
            if step:
                order.append(step)
            for neighbor in adj[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.steps):
            raise ValueError("Circular dependency detected in workflow")
        return order


class BlueprintPlanner:
    """Deterministic DAG workflow planner.

    Maps natural-language goals to structured WorkflowBlueprints using
    keyword matching + complexity heuristics. Zero LLM overhead for routing.

    If task complexity exceeds threshold, injects reflection hooks.
    """

    KEYWORDS_TO_WORKFLOW: dict[str, list[tuple[str, str, str, list[str]]]] = {
        "auth": [
            ("design", "Architect", "auth design doc", []),
            ("implement", "Builder", "auth module", ["design"]),
            ("review", "Critic", "review verdict", ["implement"]),
        ],
        "refactor": [
            ("analyze", "RefactorAgent", "refactor blueprint", []),
            ("implement", "Builder", "refactored code", ["analyze"]),
            ("review", "Critic", "review verdict", ["implement"]),
        ],
        "feature": [
            ("ideate", "Ideator", "task proposal", []),
            ("design", "Architect", "design doc", ["ideate"]),
            ("implement", "Builder", "feature code", ["design"]),
            ("review", "Critic", "review verdict", ["implement"]),
        ],
        "test": [
            ("generate_tests", "Builder", "test cases", []),
            ("run_tests", "Critic", "test results", ["generate_tests"]),
        ],
    }

    # Tasks with multiple keywords or more than 3 steps get reflection
    COMPLEXITY_THRESHOLD = 3

    def __init__(self, memory_graph=None):
        self._memory = memory_graph

    def plan(self, goal: str) -> WorkflowBlueprint:
        """Map a goal string to a WorkflowBlueprint DAG."""
        goal_lower = goal.lower()
        matched_workflow: list[tuple[str, str, str, list[str]]] | None = None

        for keyword, workflow_steps in self.KEYWORDS_TO_WORKFLOW.items():
            if keyword in goal_lower:
                matched_workflow = workflow_steps
                break

        if matched_workflow is None:
            matched_workflow = self.KEYWORDS_TO_WORKFLOW["feature"]

        steps: list[WorkflowStep] = []
        step_map: dict[str, str] = {}  # action name -> step_id
        for idx, (action, agent, output, deps) in enumerate(matched_workflow):
            step_id = f"step_{idx}"
            step_map[action] = step_id
            step_deps = [step_map[d] for d in deps if d in step_map]
            steps.append(
                WorkflowStep(
                    id=step_id,
                    action=action,
                    agent=agent,
                    expected_output=output,
                    depends_on=step_deps,
                )
            )

        # Complexity heuristic: add reflection if many keywords or steps
        requires_reflection = len(matched_workflow) >= self.COMPLEXITY_THRESHOLD
        if requires_reflection:
            reflect_step = WorkflowStep(
                id="step_reflect",
                action="reflect",
                agent="ReflectionNode",
                expected_output="gap report",
                depends_on=[steps[-1].id],
            )
            steps.append(reflect_step)

        return WorkflowBlueprint(
            goal=goal,
            steps=steps,
            requires_reflection=requires_reflection,
        )

    def replan(
        self,
        original: WorkflowBlueprint,
        reflection_result: dict[str, Any],
    ) -> WorkflowBlueprint:
        """Generate a revised plan based on reflection gaps."""
        gaps = reflection_result.get("reflection", {}).get("gaps", [])
        if not gaps:
            return original

        new_steps = list(original.steps)
        for gap in gaps:
            fix_step = WorkflowStep(
                id=f"step_fix_{len(new_steps)}",
                action=f"fix_gap: {gap[:40]}",
                agent="Builder",
                expected_output="fixed code",
                depends_on=[new_steps[-1].id] if new_steps else [],
            )
            new_steps.append(fix_step)

        # Add verification step after fixes
        verify_step = WorkflowStep(
            id="step_verify",
            action="verify",
            agent="Critic",
            expected_output="verification report",
            depends_on=[new_steps[-1].id],
        )
        new_steps.append(verify_step)

        return WorkflowBlueprint(
            goal=original.goal,
            steps=new_steps,
            requires_reflection=True,
        )


__all__ = ["BlueprintPlanner", "WorkflowBlueprint", "WorkflowStep"]
