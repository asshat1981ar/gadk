"""Tests for RefactorAgent v2 with self-correction."""

import pytest

from src.agents.refactor_agent import RefactorAgentNode
from src.memory.memory_graph import MemoryGraph


def test_invoke_generates_blueprint():
    agent = RefactorAgentNode()
    result = agent.invoke({"task": "Refactor auth module"})
    assert result["blueprint"] is not None
    assert len(result["blueprint"]["steps"]) >= 2
    assert result["validated"] is True


def test_invoke_with_memory():
    mg = MemoryGraph()
    agent = RefactorAgentNode(memory_graph=mg)
    result = agent.invoke({"task": "Refactor auth module"})
    assert result["memory"] is not None
    assert "reflection" in result


def test_self_correction_loop():
    agent = RefactorAgentNode()
    result = agent.invoke_with_correction({
        "task": "Build new feature",
        "attempts": 1,
    })
    assert result["attempts"] <= 3
    assert result["status"] in ("success", "max_retries")
