"""Deterministic task-to-workflow planner. No LLM required for routing decisions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorkflowStep:
    action: str
    agent: str
    inputs: dict
    expected_output: str


@dataclass
class WorkflowBlueprint:
    goal: str
    steps: list[WorkflowStep] = field(default_factory=list)
    estimated_duration: str = "unknown"


class BlueprintPlanner:
    """Deterministic task-to-workflow planner.

    Maps natural-language goals to structured WorkflowBlueprints using
    keyword matching. Zero LLM overhead for routing decisions.

    Workflows:
      - auth     → Architect → Builder → Critic
      - refactor → RefactorAgent → Builder → Critic
      - feature  → Ideator → Architect → Builder → Critic
      - default  → Ideator → Architect → Builder → Critic
    """

    KEYWORDS_TO_WORKFLOW: dict[str, list[WorkflowStep]] = {
        "auth": [
            WorkflowStep("design", "Architect", {}, "auth design doc"),
            WorkflowStep("implement", "Builder", {}, "auth module"),
            WorkflowStep("review", "Critic", {}, "review verdict"),
        ],
        "refactor": [
            WorkflowStep("analyze", "RefactorAgent", {}, "refactor blueprint"),
            WorkflowStep("implement", "Builder", {}, "refactored code"),
            WorkflowStep("review", "Critic", {}, "review verdict"),
        ],
        "feature": [
            WorkflowStep("ideate", "Ideator", {}, "task proposal"),
            WorkflowStep("design", "Architect", {}, "design doc"),
            WorkflowStep("implement", "Builder", {}, "feature code"),
            WorkflowStep("review", "Critic", {}, "review verdict"),
        ],
    }

    def plan(self, goal: str) -> WorkflowBlueprint:
        """Map a goal string to a WorkflowBlueprint."""
        goal_lower = goal.lower()
        for keyword, workflow_steps in self.KEYWORDS_TO_WORKFLOW.items():
            if keyword in goal_lower:
                return WorkflowBlueprint(goal=goal, steps=workflow_steps)
        # Default: feature workflow
        return WorkflowBlueprint(goal=goal, steps=self.KEYWORDS_TO_WORKFLOW["feature"])


__all__ = ["BlueprintPlanner", "WorkflowBlueprint", "WorkflowStep"]
