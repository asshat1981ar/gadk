"""Tests for structured reflection node v2."""


from src.memory.memory_graph import MemoryGraph, TaskOutcome
from src.orchestration.reflection_node import ReflectionNode


def test_evaluate_success():
    node = ReflectionNode()
    result = node.evaluate(
        task="Implement auth module",
        phase="IMPLEMENT",
        output_code="def login(): pass",
        success_criteria=["Must have login function"],
    )
    assert result.status == "success"
    assert result.gaps == []
    assert result.confidence == 1.0


def test_evaluate_failure_and_gap():
    node = ReflectionNode()
    result = node.evaluate(
        task="Implement auth module",
        phase="IMPLEMENT",
        output_code="print('hello')",
        success_criteria=["Must have login function"],
    )
    assert result.status == "failure"
    assert any("login" in gap.lower() for gap in result.gaps)
    assert result.confidence < 1.0


def test_reflect_with_memory():
    mg = MemoryGraph()
    mg.record_task("auth_module", "Builder", TaskOutcome.FAILURE, {"error": "missing_token"})

    node = ReflectionNode(memory_graph=mg)
    result = node.reflect(
        task="Build auth system",
        phase="IMPLEMENT",
        state={"output": "def login(): pass"},
        success_criteria={"login": "Must have login function"},
    )
    assert "reflection" in result
    assert result.get("memory_enhanced", False) is True
    assert len(result["reflection"]["historical_notes"]) >= 1


def test_reflect_without_memory():
    node = ReflectionNode()
    result = node.reflect(
        task="Build auth system",
        phase="IMPLEMENT",
        state={"output": "def login(): pass"},
        success_criteria={"login": "Must have login function"},
    )
    assert "reflection" in result
    assert result.get("memory_enhanced", False) is False
    assert result["reflection"]["status"] == "success"
