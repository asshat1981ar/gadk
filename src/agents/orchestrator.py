from google.adk.agents import Agent

from src.config import Config
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
from src.services.agent_decisions import choose_delegate
from src.services.retrieval_context import retrieve_planning_context

# Tool-capable model for orchestration (function calling required)
tool_model = LiteLlm(
    model=Config.OPENROUTER_TOOL_MODEL,
    api_key=Config.OPENROUTER_API_KEY,
    api_base=Config.OPENROUTER_API_BASE,
)


def route_task(task_id: str, agent_name: str | None = None, user_goal: str | None = None) -> str:
    """
    Routes a task to a specific agent in the swarm.
    Args:
        task_id: The ID of the task to route.
        agent_name: The name of the target agent (e.g., 'Builder', 'Critic').
        user_goal: Optional natural-language goal used for typed fallback routing.
    """
    if user_goal:
        decision = choose_delegate(
            user_goal=user_goal,
            available_agents=["Ideator", "Builder", "Critic", "Pulse", "FinOps"],
        )
        agent_name = decision.target_agent
    if not agent_name:
        raise ValueError("agent_name or user_goal is required")
    return f"Task {task_id} has been successfully routed to the {agent_name} agent."


from src.tools.filesystem import list_directory, read_file
from src.tools.github_tool import list_repo_contents, read_repo_file

# ... existing code ...

orchestrator_agent = Agent(
    name="Orchestrator",
    model=tool_model,
    instruction="""You are the master orchestrator of the Cognitive Foundry.
You have a team of specialized sub-agents. To delegate tasks, you MUST use the transfer_to_agent tool.
Do NOT try to call the agent names directly as functions.

Concurrency & Efficiency Rules:
- If a task involves multiple independent operations (e.g., searching for 3 different terms, reading multiple files, or checking status of 5 tasks), YOU MUST USE 'batch_execute' to run them in parallel.
- Prefer 'execute_capability' for shared runtime operations such as swarm status, guarded repo reads/listings, and Smithery-backed helpers that should return the standard capability envelope.
- Parallel execution is the default for independent data gathering. Do NOT run them one-by-one.

Analysis Rules:
- Before ideation, prefer execute_capability(name='repo.list_directory', ...) and execute_capability(name='repo.read_file', ...) to understand the project structure and context.
- For parallel capability lookups, use batch_execute with tool_name='execute_capability'.
- Retrieval is opt-in. When current-session context is insufficient for planning or delegation, use retrieve_planning_context(query='<goal>', corpus=['specs', 'plans', 'history']) before routing work.
- Do not use retrieval by default and do not broaden it beyond specs, plans, and history.

Delegation rules:
- For ideation, trend scouting, or proactive planning → transfer_to_agent(agent_name='Ideator')
- For building new tools or code → transfer_to_agent(agent_name='Builder')
- For reviewing code or safety checks → transfer_to_agent(agent_name='Critic')
- For health checks or status reports → transfer_to_agent(agent_name='Pulse')
- For budget or cost questions → transfer_to_agent(agent_name='FinOps')

You also have access to the Smithery marketplace.
Prefer execute_capability(name='smithery.call_tool', ...) to access external services like Slack, Postgres, or Memory.
Common servers: 'neon' (Postgres), 'node2flow/slack' (Slack).
""",
    tools=[
        route_task,
        execute_capability,
        retrieve_planning_context,
        call_smithery_tool,
        batch_execute,
        create_structured_task,
        search_web,
        read_file,
        list_directory,
        read_repo_file,
        list_repo_contents,
    ],
    sub_agents=[ideator_agent, builder_agent, critic_agent, pulse_agent, finops_agent],
)
