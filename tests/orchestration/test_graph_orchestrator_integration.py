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

def test_langgraph_workflow_executes_to_done(monkeypatch):
    """When LANGGRAPH_ENABLED=true, graph should execute through all nodes."""
    monkeypatch.setattr("src.config.Config.LANGGRAPH_ENABLED", True, raising=False)
    # Force reimport of graph orchestrator with langgraph enabled
    import importlib

    import src.orchestration.graph_orchestrator as go
    importlib.reload(go)

    orch = go.GraphOrchestrator()
    compiled = orch.build_workflow()

    if not hasattr(compiled, "invoke"):
        pytest.skip("LangGraph not available, pure-Python path")

    from src.orchestration.graph_orchestrator import AgentState
    initial_state: AgentState = {
        "task": "Test graph execution",
        "phase": "",
        "memory": {},
        "reflection": [],
        "blueprint": {},
        "build_output": {"built": True, "artifacts": []},
        "review_output": {"status": "pass"},
        "status": "running",
    }

    result = compiled.invoke(initial_state)
    assert result.get("status") == "done"
    assert result.get("phase") == "DELIVER"

def test_langgraph_workflow_invoke(monkeypatch):
    """Compiled LangGraph workflow should execute to done with correct state."""
    # Check if LangGraph path is available
    import src.orchestration.graph_orchestrator as go
    if not go.LANGGRAPH_AVAILABLE:
        pytest.skip("LangGraph not available")

    from src.orchestration.graph_orchestrator import AgentState, GraphOrchestrator
    orch = GraphOrchestrator()
    compiled = orch.build_workflow()

    if not hasattr(compiled, "invoke"):
        pytest.skip("Pure-Python workflow (no invoke)")

    initial_state: AgentState = {
        "task": "Test graph execution",
        "phase": "",
        "memory": {},
        "reflection": [],
        "blueprint": {},
        "build_output": {"built": True, "artifacts": []},
        "review_output": {"status": "pass"},
        "status": "running",
    }

    result = compiled.invoke(initial_state)
    assert result.get("status") == "done"
    assert result.get("phase") == "DELIVER"
