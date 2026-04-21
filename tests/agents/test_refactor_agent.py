import pytest
from src.agents.refactor_agent import RefactorAgentNode

def test_refactor_agent_generates_blueprint():
    agent = RefactorAgentNode()
    result = agent.invoke({"task": "Reduce complexity in retrieval_context"})
    assert "blueprint" in result
    assert "tasks" in result["blueprint"]
    assert len(result["blueprint"]["tasks"]) > 0

def test_refactor_agent_performs_self_reflection_and_validation():
    agent = RefactorAgentNode()
    state = {
        "task": "Optimize MemoryGraph caching",
        "memory": {},
        "reflection": []
    }
    result = agent.invoke(state)
    assert len(result.get("reflection", [])) > 0
    assert "quality_gate" in result or "validated" in str(result).lower()