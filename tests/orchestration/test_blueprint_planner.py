"""Tests for deterministic DAG blueprint planner v2."""

import pytest

from src.orchestration.blueprint_planner import BlueprintPlanner, WorkflowStep


def test_plan_auth_workflow():
    planner = BlueprintPlanner()
    bp = planner.plan("Implement authentication system")
    assert bp.goal == "Implement authentication system"
    agents = [s.agent for s in bp.steps]
    assert "Architect" in agents
    assert "Builder" in agents
    assert "Critic" in agents


def test_plan_with_reflection_hook():
    planner = BlueprintPlanner()
    bp = planner.plan("Refactor database layer and add tests")
    # Should include reflection step when complexity is high (>3 steps)
    has_reflection = any("reflect" in s.action.lower() for s in bp.steps)
    assert has_reflection


def test_dag_dependencies():
    planner = BlueprintPlanner()
    bp = planner.plan("Build new feature")
    # Verify no circular deps, all steps reachable
    step_ids = {s.id for s in bp.steps}
    for s in bp.steps:
        for dep in s.depends_on:
            assert dep in step_ids, f"Dependency {dep} not in steps"


def test_topological_order():
    planner = BlueprintPlanner()
    bp = planner.plan("Build auth system")
    ordered = bp.topological_order()
    # Earlier steps should not depend on later steps
    seen = set()
    for step in ordered:
        for dep in step.depends_on:
            assert dep in seen, f"Step {step.id} depends on {dep} which hasn't been seen"
        seen.add(step.id)


def test_replan_from_reflection():
    planner = BlueprintPlanner()
    bp = planner.plan("Build auth system")
    reflection_result = {
        "reflection": {
            "gaps": ["Missing token validation"],
        }
    }
    new_bp = planner.replan(bp, reflection_result)
    assert len(new_bp.steps) >= len(bp.steps)
    # Should have fix and verify steps
    assert any("fix" in s.action.lower() for s in new_bp.steps)
    assert any("verify" in s.action.lower() for s in new_bp.steps)
