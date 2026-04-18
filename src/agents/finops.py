import os

from google.adk.agents import Agent
from src.config import Config
from src.observability.cost_tracker import CostTracker

if Config.TEST_MODE:
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
else:
    from google.adk.models.lite_llm import LiteLlm

# General-purpose model for FinOps (simple reports, no function calling needed)
report_model = LiteLlm(
    model=Config.OPENROUTER_MODEL,
    api_key=Config.OPENROUTER_API_KEY,
    api_base=Config.OPENROUTER_API_BASE,
)

# Initialize CostTracker for use by the FinOps agent
tracker = CostTracker()
budget_usd = float(os.getenv("BUDGET_USD", "10.0"))


async def check_quota(task_id: str = "global", cost_usd: float = 0.0) -> dict:
    """
    Checks whether a task is within budget.
    Args:
        task_id: Identifier for the task.
        cost_usd: Cost of the task in USD.
    """
    tracker.record_cost(task_id, "system", cost_usd)
    total = tracker.get_total_spend()
    if total > budget_usd:
        return {
            "status": "BUDGET_EXCEEDED",
            "limit_usd": budget_usd,
            "current_usd": total,
        }
    return {
        "status": "OK",
        "current_usd": total,
        "budget_usd": budget_usd,
    }


async def get_report() -> dict:
    """Returns a summary of current costs and budget usage."""
    return tracker.get_summary()


finops_agent = Agent(
    name="FinOps",
    model=report_model,
    description="Tracks costs, budgets, and token usage",
    instruction="""You are the FinOps agent of the Cognitive Foundry.
Your job is to track costs, budgets, and token usage.
Use check_quota to verify tasks stay within budget and get_report to summarize spend.""",
    tools=[check_quota, get_report],
)
