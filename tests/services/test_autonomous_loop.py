"""Tests for AutonomousLoop — graph-based self-correcting execution.

Test coverage:
1. run() — basic successful execution and blueprint generation
2. run() with retries — self-correction when reflection finds gaps
3. Task recording — outcomes persisted to MemoryGraph
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.memory.memory_graph import MemoryGraph
from src.orchestration.blueprint_planner import BlueprintPlanner, WorkflowBlueprint, WorkflowStep
from src.orchestration.reflection_node import ReflectionNode, ReflectionResult
from src.services.autonomous_loop import AutonomousLoop


def _make_planner(steps=None, requires_reflection=False):
    planner = MagicMock(spec=BlueprintPlanner)
    blueprint = WorkflowBlueprint(
        goal="test",
        steps=steps or [WorkflowStep(id="s0", action="do", agent="Builder", expected_output="ok")],
        requires_reflection=requires_reflection,
    )
    planner.plan.return_value = blueprint
    planner.replan.return_value = blueprint
    return planner


def _make_reflector(status="success", gaps=None, suggestions=None, confidence=1.0):
    reflector = MagicMock(spec=ReflectionNode)
    result = ReflectionResult(
        status=status,
        gaps=gaps or [],
        suggestions=suggestions or [],
        confidence=confidence,
    )
    reflector.evaluate.return_value = result
    reflector.reflect.return_value = {
        "reflection": {
            "status": status,
            "gaps": gaps or [],
            "suggestions": suggestions or [],
            "confidence": confidence,
            "historical_notes": [],
        },
        "memory_enhanced": False,
        "phase": "TEST",
        "task": "test task",
    }
    return reflector


class TestAutonomousLoopRun:
    def test_run_success_no_reflection(self):
        memory = MemoryGraph()
        planner = _make_planner()
        reflector = _make_reflector(status="success")
        loop = AutonomousLoop(
            memory_graph=memory,
            planner=planner,
            reflector=reflector,
            max_retries=2,
        )

        result = loop.run("Implement auth module")

        assert result["status"] == "success"
        assert result["goal"] == "Implement auth module"
        assert result["attempts"] == 1
        assert result["validated"] is True
        planner.plan.assert_called_once_with("Implement auth module")

    def test_run_with_retries_then_success(self):
        memory = MemoryGraph()
        planner = _make_planner(steps=[
            WorkflowStep(id="s0", action="design", agent="Architect", expected_output="doc"),
        ])

        # First reflection fails, second succeeds
        reflector = MagicMock(spec=ReflectionNode)
        reflector.reflect.side_effect = [
            {
                "reflection": {
                    "status": "failure",
                    "gaps": ["Missing criterion: tests"],
                    "suggestions": ["Add tests"],
                    "confidence": 0.5,
                    "historical_notes": [],
                },
                "memory_enhanced": False,
                "phase": "TEST",
                "task": "test task",
            },
            {
                "reflection": {
                    "status": "success",
                    "gaps": [],
                    "suggestions": [],
                    "confidence": 1.0,
                    "historical_notes": [],
                },
                "memory_enhanced": False,
                "phase": "TEST",
                "task": "test task",
            },
        ]

        loop = AutonomousLoop(
            memory_graph=memory,
            planner=planner,
            reflector=reflector,
            max_retries=3,
        )

        result = loop.run("Refactor login flow")

        assert result["status"] == "success"
        assert result["attempts"] == 2
        assert reflector.reflect.call_count == 2
        planner.replan.assert_called_once()

    def test_run_max_retries_exceeded(self):
        memory = MemoryGraph()
        planner = _make_planner(steps=[
            WorkflowStep(id="s0", action="analyze", agent="RefactorAgent", expected_output="bp"),
        ])
        reflector = MagicMock(spec=ReflectionNode)
        reflector.reflect.return_value = {
            "reflection": {
                "status": "failure",
                "gaps": ["Missing criterion: docstrings"],
                "suggestions": ["Add docstrings"],
                "confidence": 0.4,
                "historical_notes": [],
            },
            "memory_enhanced": False,
            "phase": "TEST",
            "task": "test task",
        }

        loop = AutonomousLoop(
            memory_graph=memory,
            planner=planner,
            reflector=reflector,
            max_retries=2,
        )

        result = loop.run("Refactor login flow")

        assert result["status"] == "max_retries"
        assert result["attempts"] == 2
        assert result["gaps"] == ["Missing criterion: docstrings"]
        assert reflector.reflect.call_count == 2
        assert planner.replan.call_count == 2

    def test_run_records_task_in_memory_graph(self):
        memory = MemoryGraph()
        planner = _make_planner()
        reflector = _make_reflector(status="success")
        loop = AutonomousLoop(
            memory_graph=memory,
            planner=planner,
            reflector=reflector,
        )

        loop.run("Build feature X")

        tasks = memory.query_tasks()
        assert len(tasks) == 1
        assert tasks[0]["name"] == "Build feature X"

    def test_run_records_failure_on_max_retries(self):
        memory = MemoryGraph()
        planner = _make_planner()
        reflector = _make_reflector(status="failure", gaps=["g1"], confidence=0.3)
        loop = AutonomousLoop(
            memory_graph=memory,
            planner=planner,
            reflector=reflector,
            max_retries=1,
        )

        result = loop.run("Build feature Y")

        assert result["status"] == "max_retries"
        history = memory.get_agent_history("AutonomousLoop")
        assert len(history) == 1
        assert history[0]["outcome"] == "failure"

    def test_run_success_records_success_outcome(self):
        memory = MemoryGraph()
        planner = _make_planner()
        reflector = _make_reflector(status="success")
        loop = AutonomousLoop(
            memory_graph=memory,
            planner=planner,
            reflector=reflector,
        )

        loop.run("Build feature Z")

        history = memory.get_agent_history("AutonomousLoop")
        assert len(history) == 1
        assert history[0]["outcome"] == "success"

    def test_run_returns_blueprint_steps(self):
        memory = MemoryGraph()
        steps = [
            WorkflowStep(id="s0", action="plan", agent="Ideator", expected_output="proposal", depends_on=[]),
            WorkflowStep(id="s1", action="code", agent="Builder", expected_output="code", depends_on=["s0"]),
        ]
        planner = _make_planner(steps=steps)
        reflector = _make_reflector(status="success")
        loop = AutonomousLoop(
            memory_graph=memory,
            planner=planner,
            reflector=reflector,
        )

        result = loop.run("Feature")

        assert result["blueprint"]["goal"] == "test"
        assert len(result["blueprint"]["steps"]) == 2
