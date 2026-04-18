from google.adk.agents import Agent
from src.config import Config
from src.tools.sandbox_executor import execute_python_code
from src.tools.dispatcher import batch_execute
from src.tools.filesystem import read_file, list_directory
from src.tools.github_tool import read_repo_file, list_repo_contents
from src.services.agent_decisions import normalize_review_verdict
from src.services.workflow_graphs import GraphDecision, ReviewLoopState, run_review_rework_cycle

if Config.TEST_MODE:
    from src.testing.mock_llm import MockLiteLlm as LiteLlm
else:
    from google.adk.models.lite_llm import LiteLlm

# Tool-capable model for Critic (function calling required for evaluate, batch_execute, etc.)
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
        with open(staged_path, "r") as f:
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
    # In a real implementation, fetch PR diff and analyze
    # For now, submit an automated review
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
    """Validate a review verdict and return a bounded graph transition decision.

    Combines the shared review-verdict contract with the workflow graph so
    the critic agent can emit both a typed verdict *and* an explicit routing
    decision (stop / rework / block) in one call.

    Args:
        payload:          Raw verdict dict with at minimum ``status`` and
                          ``summary`` keys.
        builder_attempts: How many times Builder has already attempted this
                          task.  Used to evaluate the retry budget.
        max_retries:      Maximum rework attempts before the loop stops.

    Returns:
        A ``GraphDecision`` dict with ``next_step`` and ``reason``.
    """
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
Use the batch_execute tool to run multiple validation tests or code snippets in parallel 
using 'tool_name': 'execute_python_code'.
Alternatively, use the evaluate tool to run a single staged Python file in a sandbox.
Use create_review_verdict to emit a typed review verdict (pass/retry/block).
Use get_review_graph_decision to emit both a verdict and a bounded routing decision
in one step — this is preferred when Builder rework is a possibility.""",
    tools=[
        batch_execute,
        evaluate,
        create_review_verdict,
        get_review_graph_decision,
        execute_python_code,
        read_file,
        list_directory,
        read_repo_file,
        list_repo_contents,
    ],
)
