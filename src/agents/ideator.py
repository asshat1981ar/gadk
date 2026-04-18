import asyncio
from typing import List, Any
from datetime import datetime, timezone
from google.adk.agents import Agent
from src.tools.scraper import ScraperTool
from src.tools.github_tool import GitHubTool
from src.state import StateManager
from src.config import Config
from src.tools.web_search import search_web
from src.tools.dispatcher import batch_execute
from src.tools.filesystem import read_file, list_directory
from src.services.agent_decisions import build_task_proposal

if Config.TEST_MODE:
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
else:
    from google.adk.models.lite_llm import LiteLlm

# Tool-capable model for ideation (function calling required for batch_execute, read_repo_file, etc.)
tool_model = LiteLlm(
    model=Config.OPENROUTER_TOOL_MODEL,
    api_key=Config.OPENROUTER_API_KEY,
    api_base=Config.OPENROUTER_API_BASE,
)

# Initialize core services
if Config.TEST_MODE:
    class MockScraper:
        async def scrape(self, url): return "Mock content for testing"
    scraper_tool = MockScraper()
else:
    scraper_tool = ScraperTool(allowlist=["github.com", "google.com"])
github_tool = GitHubTool()
state_manager = StateManager()

async def create_structured_task(
    title: str, 
    description: str, 
    acceptance_criteria: List[str], 
    priority: int = 3, 
    complexity: str = "medium",
    suggested_agent: str = "Builder",
    tags: List[str] = None
) -> str:
    """
    Creates a high-quality, actionable task in the swarm state.
    Args:
        title: Short, descriptive title.
        description: Detailed explanation of the goal and context.
        acceptance_criteria: Specific points that must be met for completion.
        priority: 1 (Critical) to 5 (Low).
        complexity: 'small', 'medium', or 'large'.
        suggested_agent: The best agent to handle this (e.g., 'Builder', 'Critic').
        tags: Optional category tags.
    """
    proposal = build_task_proposal(
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        suggested_agent=suggested_agent,
    )
    task_id = f"task-{int(asyncio.get_event_loop().time())}-{proposal.title.lower().replace(' ', '-')[:20]}"
    task_data = {
        "title": proposal.title,
        "description": proposal.description,
        "acceptance_criteria": proposal.acceptance_criteria,
        "status": "PENDING",
        "priority": priority,
        "complexity": complexity,
        "suggested_agent": proposal.recommended_agent,
        "tags": tags or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "Ideator"
    }
    
    state_manager.set_task(task_id, task_data, agent="Ideator")
    
    # Also track in GitHub for visibility
    body = f"## Summary\n{proposal.title}\n\n## Description\n{proposal.description}\n\n## Acceptance Criteria\n"
    body += "\n".join([f"- [ ] {ac}" for ac in proposal.acceptance_criteria])
    body += (
        f"\n\n**Priority**: {priority} | **Complexity**: {complexity} "
        f"| **Suggested Agent**: {proposal.recommended_agent}"
    )
    
    await github_tool.create_issue(
        title=f"[SWARM TASK] {proposal.title}",
        body=body
    )
    
    return f"Successfully created structured task: {task_id}"

ideator_agent = Agent(
    name="Ideator",
    model=tool_model,
    description="Proactively scouts technical trends and plans autonomous tasks",
    instruction="""You are the Ideator of the Cognitive Foundry. 
    Your mission is to find high-impact opportunities for codebase improvement, new features, or technical debt reduction.

    STRATEGY:
    1. RESEARCH: Use 'search_web' and 'batch_execute' to scout for latest trends (e.g., "latest FastAPI patterns", "React 19 features").
    2. ANALYZE: For remote GitHub repository exploration, start with 'list_repo_contents' and inspect files with 'read_repo_file'.
    3. PLAN: Use 'create_structured_task' to turn findings into ACTIONABLE work. 

    REMOTE VS LOCAL BOUNDARY:
    - For the remote GitHub repository, use 'list_repo_contents' and 'read_repo_file' directly.
    - Use 'list_directory' and 'read_file' only for local workspace files.
    - Do not use retrieve_planning_context or execute_capability to explore the remote repository; retrieve_planning_context is only for local specs, plans, and history.

    TASK GUIDELINES:
    - BE SPECIFIC: Avoid vague titles like "Improve code". Use "Refactor Error Handling in src/main.py".
    - ACCEPTANCE CRITERIA: Every task must have 3-5 clear points that a Builder agent can follow.
    - PRIORITIZE: Focus on security, performance, and developer experience.

    ALWAYS use 'batch_execute' when you need to perform more than one search or file read to maximize throughput.
    """,
    tools=[
        batch_execute, 
        search_web, 
        create_structured_task, 
        read_file, 
        list_directory, 
        github_tool.read_repo_file, 
        github_tool.list_repo_contents
    ]
)
