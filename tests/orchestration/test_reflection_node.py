import pytest
from src.orchestration.reflection_node import ReflectionNode

def test_reflection_node_performs_gap_analysis():
    node = ReflectionNode()
    state = {"task": "Improve autonomous software generation", "memory": {}, "reflection": []}
    result = node.invoke(state)
    assert "gap" in result["reflection"][0].lower()
    assert len(result["reflection"]) > 0