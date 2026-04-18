from google.adk.agents import Agent
from src.config import Config

if Config.TEST_MODE:
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
else:
    from google.adk.models.lite_llm import LiteLlm

# General-purpose model for Pulse (simple reports, no function calling needed)
report_model = LiteLlm(
    model=Config.OPENROUTER_MODEL,
    api_key=Config.OPENROUTER_API_KEY,
    api_base=Config.OPENROUTER_API_BASE,
)


async def generate_report(state_data: dict) -> dict:
    """
    Monitors swarm health and reports on task status.
    Args:
        state_data: Dictionary of tasks with status information.
    """
    total_tasks = len(state_data)
    stalled_tasks = sum(1 for t in state_data.values() if t.get("status") == "STALLED")
    return {
        "summary": f"Swarm Pulse: {total_tasks} total tasks, {stalled_tasks} stalled.",
        "status": "HEALTHY" if stalled_tasks == 0 else "DEGRADED",
    }


pulse_agent = Agent(
    name="Pulse",
    model=report_model,
    description="Monitors swarm health and reports on task status",
    instruction="""You are the Pulse of the Cognitive Foundry.
Your job is to monitor swarm health and report on task status.
Use the generate_report tool to produce health summaries from state data.""",
    tools=[generate_report],
)
