"""Integration tests for graph orchestrator wired into main."""
import pytest
from src.config import Config


def test_graph_orchestrator_resolves_when_langgraph_disabled():
    """When LANGGRAPH_ENABLED=false, build_workflow returns pure-Python dict."""
    # Ensure LANGGRAPH_ENABLED is false
    assert Config.LANGGRAPH_ENABLED is False

    from src.orchestration.graph_orchestrator import GraphOrchestrator

    orch = GraphOrchestrator()
    wf = orch.build_workflow()
    # Should return pure-Python dict when langgraph_enabled=False
    assert isinstance(wf, dict)
    assert "nodes" in wf
    assert "edges" in wf
    assert wf["nodes"] == ["plan", "build", "review", "reflect", "deliver"]


def test_graph_orchestrator_has_full_workflow_nodes():
    """Full workflow has all 5 required nodes."""
    from src.orchestration.graph_orchestrator import GraphOrchestrator

    orch = GraphOrchestrator()
    wf = orch.build_workflow()
    if isinstance(wf, dict):
        assert set(wf["nodes"]) == {"plan", "build", "review", "reflect", "deliver"}
        # Rework edge: reflect→build, Success edge: reflect→deliver
        assert ("reflect", "build") in wf["edges"]
        assert ("reflect", "deliver") in wf["edges"]


def test_agent_state_is_valid_typed_dict():
    """AgentState TypedDict should accept required fields."""
    from src.orchestration.graph_orchestrator import AgentState

    state: AgentState = {
        "task": "Test workflow",
        "phase": "",
        "memory": {},
        "reflection": [],
        "blueprint": {},
        "build_output": {},
        "review_output": {},
        "status": "running",
    }
    assert state["task"] == "Test workflow"
    assert state["status"] == "running"
