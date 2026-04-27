"""Tests for the graph-based memory store."""

import os
import tempfile

from src.memory.graph_store import GraphStore, NodeType


def test_add_and_get_node():
    gs = GraphStore()
    node_id = gs.add_node(
        node_type=NodeType.AGENT,
        name="test_agent",
        attrs={"role": "builder"},
    )
    node = gs.get_node(node_id)
    assert node["type"] == NodeType.AGENT.value
    assert node["name"] == "test_agent"
    assert node["attrs"]["role"] == "builder"


def test_add_and_get_edge():
    gs = GraphStore()
    a = gs.add_node(NodeType.TASK, "task_a")
    b = gs.add_node(NodeType.AGENT, "agent_b")
    gs.add_edge(a, b, "executed_by", {"confidence": 0.9})
    edges = gs.edges_from(a)
    assert len(edges) == 1
    assert edges[0]["label"] == "executed_by"
    assert edges[0]["target"] == b


def test_persistence_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        gs1 = GraphStore(path)
        a = gs1.add_node(NodeType.OUTCOME, "outcome_a")
        b = gs1.add_node(NodeType.TASK, "task_b")
        gs1.add_edge(a, b, "produced")
        gs1.save()

        gs2 = GraphStore(path)
        assert gs2.get_node(a)["name"] == "outcome_a"
        assert len(gs2.edges_from(a)) == 1
    finally:
        os.remove(path)


def test_query_neighbors():
    gs = GraphStore()
    task = gs.add_node(NodeType.TASK, "implement_auth")
    agent = gs.add_node(NodeType.AGENT, "Builder")
    outcome = gs.add_node(NodeType.OUTCOME, "auth_module")
    gs.add_edge(task, agent, "executed_by")
    gs.add_edge(task, outcome, "produced")

    neighbors = gs.neighbors(task)
    assert len(neighbors) == 2
    names = {n["name"] for n in neighbors}
    assert names == {"Builder", "auth_module"}


def test_query_by_type():
    gs = GraphStore()
    gs.add_node(NodeType.AGENT, "Architect")
    gs.add_node(NodeType.TASK, "design_login")
    gs.add_node(NodeType.AGENT, "Builder")

    agents = gs.query_by_type(NodeType.AGENT)
    assert len(agents) == 2
    names = {a["name"] for a in agents}
    assert names == {"Architect", "Builder"}


def test_query_related():
    gs = GraphStore()
    task = gs.add_node(NodeType.TASK, "implement_auth")
    agent = gs.add_node(NodeType.AGENT, "Builder")
    outcome = gs.add_node(NodeType.OUTCOME, "auth_module")
    concept = gs.add_node(NodeType.CONCEPT, "OAuth2")
    gs.add_edge(task, agent, "executed_by")
    gs.add_edge(task, outcome, "produced")
    gs.add_edge(outcome, concept, "implements")

    # Related from task up to depth 2 should get agent, outcome, and concept
    related = gs.query_related(task, max_depth=2)
    names = {r["name"] for r in related}
    assert names == {"Builder", "auth_module", "OAuth2"}
