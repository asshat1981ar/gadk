from src.orchestration.graph_orchestrator import GraphOrchestrator


def test_graph_orchestrator_creates_workflow():
    """Graph should have reflection and self_correct nodes (skeleton contract)."""
    orchestrator = GraphOrchestrator()
    graph = orchestrator.build_workflow()
    # Pure-Python dict path
    if isinstance(graph, dict):
        assert "reflection" in graph["nodes"] or "reflect" in graph["nodes"]
    else:
        # LangGraph path
        assert "reflection" in graph.nodes or "reflect" in graph.nodes


def test_full_workflow_has_required_nodes():
    """Graph should have plan, build, review, reflect, deliver nodes."""
    orchestrator = GraphOrchestrator()
    compiled = orchestrator.build_workflow()
    if isinstance(compiled, dict):
        assert "plan" in compiled["nodes"]
        assert "build" in compiled["nodes"]
        assert "review" in compiled["nodes"]
        assert "reflect" in compiled["nodes"]
        assert "deliver" in compiled["nodes"]
        # Edges should include rework (reflect→build) and success (reflect→deliver)
        edges = compiled["edges"]
        assert ("reflect", "build") in edges, "Missing rework edge reflect→build"
        assert ("reflect", "deliver") in edges, "Missing success edge reflect→deliver"
    else:
        # LangGraph path
        node_names = set(compiled.nodes)
        assert "plan" in node_names
        assert "build" in node_names
        assert "review" in node_names
        assert "reflect" in node_names
        assert "deliver" in node_names


def test_python_workflow_edges_structure():
    """Pure-Python workflow should have proper edge structure."""
    orchestrator = GraphOrchestrator()
    result = orchestrator._build_python_workflow()
    assert result["nodes"] == ["plan", "build", "review", "reflect", "deliver"]
    assert ("plan", "build") in result["edges"]
    assert ("build", "review") in result["edges"]
    assert ("review", "reflect") in result["edges"]
