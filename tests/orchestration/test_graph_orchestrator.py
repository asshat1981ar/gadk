import pytest
from src.orchestration.graph_orchestrator import GraphOrchestrator

def test_graph_orchestrator_creates_workflow():
    orchestrator = GraphOrchestrator()
    graph = orchestrator.build_workflow()
    assert "reflection" in graph.nodes
    assert "self_correct" in graph.nodes