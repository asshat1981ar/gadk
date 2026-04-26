from google.adk.agents import Agent

from src.config import Config
from src.services.agent_decisions import choose_delegate
from src.services.retrieval_context import retrieve_planning_context
from src.tools.dispatcher import batch_execute, execute_capability
from src.tools.smithery_bridge import call_smithery_tool
from src.tools.web_search import search_web

if Config.TEST_MODE:
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
else:
    from google.adk.models.lite_llm import LiteLlm

from src.agents.builder import builder_agent
from src.agents.critic import critic_agent
from src.agents.finops import finops_agent
from src.agents.ideator import create_structured_task, ideator_agent
from src.agents.pulse import pulse_agent

tool_model = LiteLlm(
    model=Config.LLM_MODEL,
    api_key=Config.LLM_API_KEY,
    api_base=Config.LLM_API_BASE,
)


def route_task(task_id: str, agent_name: str | None = None, user_goal: str | None = None) -> str:
    if user_goal:
        decision = choose_delegate(
            user_goal=user_goal,
            available_agents=["Ideator", "Builder", "Critic", "Pulse", "FinOps"],
        )
        agent_name = decision.target_agent

    if not agent_name:
        agent_name = "Ideator"

    return f"Task {task_id} has been successfully routed to the {agent_name} agent."


orchestrator_agent = Agent(
    name="Orchestrator",
    model=tool_model,
    instruction="""You are the master orchestrator of the Cognitive Foundry.

Delegate tasks to your specialized sub-agents based on the user's request:
- For ideation, trend scouting, or proactive planning, transfer to Ideator.
- For building new tools or code, transfer to Builder.
- For reviewing code or safety checks, transfer to Critic.
- For health checks or status reports, transfer to Pulse.
- For budget or cost questions, transfer to FinOps.

For remote GitHub repository exploration in the autonomous runtime, use read_repo_file and list_repo_contents directly.
Use execute_capability for shared operational and guarded local capabilities, not for browsing the remote GitHub repository.
Before ideation or specialist routing, use retrieve_planning_context only for local specs, plans, and history when current-session context is insufficient.
Continue using batch_execute for independent parallel work.
You also have access to the Smithery marketplace when an external tool is needed.""",
    tools=[
        batch_execute,
        execute_capability,
        retrieve_planning_context,
        route_task,
        search_web,
        call_smithery_tool,
        create_structured_task,
    ],
    sub_agents=[
        ideator_agent,
        builder_agent,
        critic_agent,
        pulse_agent,
        finops_agent,
    ],
)
