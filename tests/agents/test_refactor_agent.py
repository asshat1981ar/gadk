from src.agents.refactor_agent import RefactorAgentNode


def test_refactor_agent_returns_blueprint():
    """RefactorAgent should return a blueprint with steps."""
    node = RefactorAgentNode()
    state = {"task": "Refactor state manager", "memory": {}, "reflection": []}
    result = node.invoke(state)
    assert "blueprint" in result
    assert "reflection" in result
    assert result["agent"] == "refactor"
    assert result["validated"] is True


def test_refactor_agent_uses_blueprint_planner():
    """RefactorAgent should delegate to BlueprintPlanner."""
    node = RefactorAgentNode()
    state = {"task": "Refactor memory module", "memory": {}, "reflection": []}
    result = node.invoke(state)
    blueprint = result["blueprint"]
    assert "goal" in blueprint
    assert len(blueprint.get("steps", [])) >= 2  # at least analyze + implement


def test_refactor_agent_adds_reflection():
    """RefactorAgent should add reflection entries."""
    node = RefactorAgentNode()
    state = {"task": "Refactor", "memory": {}, "reflection": []}
    result = node.invoke(state)
    assert len(result["reflection"]) > 0


def test_refactor_agent_invalid_blueprint_not_validated():
    """If blueprint has < 2 steps, validated should be False."""
    node = RefactorAgentNode()
    # Patch planner to return empty steps
    node.planner.plan = lambda goal: type("BP", (), {"goal": goal, "steps": []})()
    state = {"task": "X", "memory": {}, "reflection": []}
    result = node.invoke(state)
    assert result["validated"] is False
