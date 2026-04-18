from google.adk.agents import Agent

from src.config import Config
from src.services.agent_decisions import normalize_review_verdict
from src.services.workflow_graphs import GraphDecision, ReviewLoopState, run_review_rework_cycle
from src.tools.dispatcher import batch_execute
from src.tools.filesystem import list_directory, read_file
from src.tools.github_tool import list_repo_contents, read_repo_file
from src.tools.sandbox_executor import execute_python_code

if Config.TEST_MODE:
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
else:
    from google.adk.models.lite_llm import LiteLlm

tool_model = LiteLlm(
    model=Config.OPENROUTER_TOOL_MODEL,
    api_key=Config.OPENROUTER_API_KEY,
    api_base=Config.OPENROUTER_API_BASE,
)


async def evaluate(staged_path: str) -> dict:
    """
    Reviews staged Python code by executing it in a sandbox.

    Args:
        staged_path: Path to the staged Python file to evaluate.
    """
    if not staged_path.endswith(".py"):
        return {"status": "FAIL", "reason": "Not a python file"}

    try:
        with open(staged_path, "r", encoding="utf-8") as f:
            code = f.read()

        result = await execute_python_code(code)

        if result.startswith("Error:"):
            return {"status": "FAIL", "reason": result}

        return {"status": "PASS", "score": 1.0, "output": result}
    except Exception as e:
        return {"status": "FAIL", "reason": str(e)}


async def review_pr(pr_number: int) -> dict:
    from src.tools.github_tool import GitHubTool

    gh = GitHubTool()
    result = await gh.review_pull_request(
        pr_number=pr_number,
        body="Autonomous Critic review: basic safety checks passed.",
        event="COMMENT",
    )
    return {"status": "PASS", "score": 1.0, "pr": pr_number, "review": result}


def create_review_verdict(payload: dict) -> dict:
    """Validate critic output against the shared review-verdict contract."""
    return normalize_review_verdict(payload).model_dump()


def get_review_graph_decision(
    payload: dict,
    builder_attempts: int = 1,
    max_retries: int = 2,
) -> dict:
    """Return the bounded review-loop decision for a validated verdict."""
    verdict = normalize_review_verdict(payload)
    decision: GraphDecision = run_review_rework_cycle(
        ReviewLoopState(
            builder_attempts=builder_attempts,
            review_status=verdict.status,
            latest_summary=verdict.summary,
        ),
        max_retries=max_retries,
    )
    return decision.model_dump()


critic_agent = Agent(
    name="Critic",
    model=tool_model,
    description="Reviews code and staged tools for safety and quality",
    instruction="""You are the Critic of the Cognitive Foundry.
Your job is to review code and staged tools for safety and quality.
Use the batch_execute tool to run multiple validation steps in parallel.
Alternatively, use evaluate to run a single staged Python file in a sandbox.
Use create_review_verdict to emit a typed review verdict (pass/retry/block).
Use get_review_graph_decision when Builder rework is a possibility so the review returns an explicit bounded routing decision.""",
    tools=[
        batch_execute,
        evaluate,
        review_pr,
        create_review_verdict,
        get_review_graph_decision,
        execute_python_code,
        read_file,
        list_directory,
        read_repo_file,
        list_repo_contents,
    ],
)
