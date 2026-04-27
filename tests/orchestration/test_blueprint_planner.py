from src.orchestration.blueprint_planner import BlueprintPlanner, WorkflowBlueprint


def test_blueprint_planner_returns_workflow_blueprint():
    planner = BlueprintPlanner()
    blueprint = planner.plan("Add user authentication")
    assert isinstance(blueprint, WorkflowBlueprint)
    assert len(blueprint.steps) > 0
    assert blueprint.goal == "Add user authentication"


def test_blueprint_planner_auth_keyword():
    planner = BlueprintPlanner()
    bp = planner.plan("Add JWT authentication to API")
    assert bp.steps[0].action == "design"
    assert bp.steps[0].agent == "Architect"


def test_blueprint_planner_refactor_keyword():
    planner = BlueprintPlanner()
    bp = planner.plan("Refactor the state manager module")
    assert bp.steps[0].agent == "RefactorAgent"


def test_blueprint_planner_unknown_falls_back_to_feature():
    planner = BlueprintPlanner()
    bp = planner.plan("Do something completely new")
    assert bp.steps[0].agent == "Ideator"
