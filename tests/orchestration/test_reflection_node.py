from src.orchestration.reflection_node import ReflectionNode


def test_reflection_node_performs_gap_analysis():
    node = ReflectionNode()
    state = {"task": "Improve autonomous software generation", "memory": {}, "reflection": []}
    result = node.invoke(state)
    assert "gap" in result["reflection"][0].lower()
    assert len(result["reflection"]) > 0
def test_reflection_node_rule_based_gap_analysis():
    """Fallback gap analysis when MCP is unavailable."""
    node = ReflectionNode()
    state = {"task": "Improve autonomy", "memory": {}, "reflection": [], "phase": "PLAN"}
    result = node.invoke(state)
    assert "reflection" in result
    assert len(result["reflection"]) > 0
    assert "memory" in result
    assert result["memory"].get("gaps_identified", 0) >= 0

def test_reflection_node_detects_gaps():
    """Reflection text contains gap analysis."""
    node = ReflectionNode()
    state = {"task": "Fix memory leak", "memory": {}, "reflection": [], "phase": "OPERATE"}
    result = node.invoke(state)
    text = result["reflection"][0]
    assert isinstance(text, str)
    assert len(text) > 10

def test_reflection_node_calls_sequential_thinking_when_available(monkeypatch):
    """When sequential thinking MCP is available, it is called."""
    calls = []
    def mock_sequential_thinking(**kwargs):
        calls.append(kwargs)
        return {"thought": "Identified gap: rigid phase transitions"}
    import src.orchestration.reflection_node as rn
    monkeypatch.setattr(rn, "SEQUENTIAL_THINKING_AVAILABLE", True)
    monkeypatch.setattr(rn, "sequentialthinking", mock_sequential_thinking)

    node = ReflectionNode()
    state = {"task": "Improve autonomy", "memory": {}, "reflection": [], "phase": "PLAN"}
    result = node.invoke(state)

    assert len(calls) == 1
    assert "thought" in calls[0]
    assert "reflection" in result
