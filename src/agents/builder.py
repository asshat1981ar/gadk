import os

from google.adk.agents import Agent

from src.config import Config
from src.tools.filesystem import list_directory, read_file, write_file

if Config.TEST_MODE:
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
else:
    from google.adk.models.lite_llm import LiteLlm

# Elephant-alpha for Builder — optimized for code generation.
# Tool calling is simpler here (build_tool, write_file) than multi-agent orchestration.
code_model = LiteLlm(
    model=Config.OPENROUTER_MODEL,
    api_key=Config.OPENROUTER_API_KEY,
    api_base=Config.OPENROUTER_API_BASE,
)


async def build_tool(tool_spec: dict) -> str:
    """
    Writes a new tool to the staged agents directory.
    Args:
        tool_spec: Dictionary with 'name' and 'code' keys.
    """
    os.makedirs("src/staged_agents", exist_ok=True)
    path = os.path.join("src/staged_agents", f"{tool_spec['name']}.py")
    with open(path, "w") as f:
        f.write(tool_spec["code"])

    # Create PR for the new tool
    from src.tools.github_tool import GitHubTool

    gh = GitHubTool()
    pr_url = await gh.create_pull_request(
        title=f"[BUILDER] Add tool: {tool_spec['name']}",
        body=f"Autonomously generated tool `{tool_spec['name']}`.",
        head=f"feature/{tool_spec['name']}",
    )
    return pr_url or path


builder_agent = Agent(
    name="Builder",
    model=code_model,
    description="Builds new tools and writes code to the codebase",
    instruction="""You are the Builder of the Cognitive Foundry.
Your job is to write new tools and code to the codebase.
Use the build_tool function to stage new Python tools in src/staged_agents/.""",
    tools=[build_tool, read_file, write_file, list_directory],
)
