def should_use_planner_for_autonomous_run(model_name: str) -> bool:
    """Return whether autonomous runs should bypass native ADK tool calling."""
    return model_name.startswith("ollama/elephant")
