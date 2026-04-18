import asyncio
import os

from google.adk.runners import Runner
from google.genai import types

from src.agents.orchestrator import orchestrator_agent
from src.capabilities.contracts import CapabilityRequest
from src.services.retrieval_context import (
    PLANNING_RETRIEVAL_CAPABILITY,
    RetrievalQuery,
    retrieve_context,
    retrieve_planning_context,
)
from src.services.session_store import SQLiteSessionService
from src.tools.dispatcher import (
    _register_capability,
    execute_capability,
    register_runtime_capabilities,
    register_tool,
)
from src.tools.filesystem import list_directory, read_file, write_file
from src.tools.github_tool import list_repo_contents, read_repo_file
from src.tools.sandbox_executor import execute_python_code
from src.tools.smithery_bridge import call_smithery_tool
from src.tools.web_search import search_web

# Register core tools for the Multiplexed Dispatcher
register_runtime_capabilities()
register_tool("execute_capability", execute_capability)
register_tool("search_web", search_web)
register_tool("execute_python_code", execute_python_code)
register_tool("call_smithery_tool", call_smithery_tool)
register_tool("read_file", read_file)
register_tool("write_file", write_file)
register_tool("list_directory", list_directory)
register_tool("read_repo_file", read_repo_file)
register_tool("list_repo_contents", list_repo_contents)
register_tool("retrieve_planning_context", retrieve_planning_context)


def _planning_retrieval_handler(request: CapabilityRequest) -> dict[str, object]:
    query = RetrievalQuery.model_validate(request.arguments)
    return retrieve_context(query)


_register_capability(
    name=PLANNING_RETRIEVAL_CAPABILITY,
    description="Retrieve planning context from approved specs, plans, and history.",
    backend="retrieval",
    handler=_planning_retrieval_handler,
)

try:
    from src.testing.test_tools import delay_tool

    register_tool("delay_tool", delay_tool)
except ImportError:
    pass

from src.cli.swarm_ctl import (
    clear_pid,
    clear_shutdown,
    dequeue_prompts,
    is_shutdown_requested,
    write_pid,
)
from src.observability.adk_callbacks import ObservabilityCallback
from src.observability.logger import configure_logging, get_logger, set_session_id, set_trace_id

logger = get_logger("main")
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    json_format=os.getenv("JSON_LOGS", "true").lower() == "true",
)


async def process_prompt(runner, session, user_query: str) -> None:
    """Process a single user prompt through the swarm."""
    content = types.Content(role="user", parts=[types.Part(text=user_query)])
    logger.info(f"Processing prompt: {user_query}", extra={"session_id": session.id})

    events = runner.run_async(session_id=session.id, user_id="swarm_admin", new_message=content)

    try:
        async for event in events:
            if hasattr(event, "content") and event.content and event.content.parts:
                text = event.content.parts[0].text
                if text:
                    logger.info(f"Swarm response: {text}", extra={"session_id": session.id})
    except Exception as e:
        logger.exception("Error during swarm execution")
        if "AttributeError" not in str(e):
            logger.error("Error during swarm execution: %s", e)


async def run_swarm_loop(session_service, session, runner) -> None:
    """Run the swarm in autonomous loop mode, checking for prompts and shutdown."""
    initial_query = (
        "First, use 'list_repo_contents' to explore the 'project-chimera' repository. "
        "Read key files in that repository (like build.gradle.kts or major Kotlin files) to understand its current state. "
        "Then, identify high-priority improvements or missing features for Project Chimera, "
        "create structured tasks for them, and start the proactive ideation process. "
        "Remember: You are the Cognitive Foundry swarm, and Project Chimera is your development target."
    )
    await process_prompt(runner, session, initial_query)

    while True:
        if is_shutdown_requested():
            logger.info("Shutdown sentinel detected. Exiting swarm loop.")
            break

        # Check for injected prompts
        prompts = dequeue_prompts()
        for entry in prompts:
            prompt_text = entry.get("prompt", "")
            user_id = entry.get("user_id", "cli_user")
            logger.info(
                f"Injected prompt from {user_id}: {prompt_text}",
                extra={"session_id": session.id},
            )
            await process_prompt(runner, session, prompt_text)

        await asyncio.sleep(2)


async def run_single(session_service, session, runner) -> None:
    """Run the swarm once and exit."""
    # Check for injected prompts first
    prompts = dequeue_prompts()
    if prompts:
        for entry in prompts:
            prompt_text = entry.get("prompt", "")
            user_id = entry.get("user_id", "cli_user")
            logger.info(
                f"Processing queued prompt from {user_id}: {prompt_text}",
                extra={"session_id": session.id},
            )
            await process_prompt(runner, session, prompt_text)
    else:
        logger.info(
            "No prompts in queue. Exiting single-run mode.",
            extra={"session_id": session.id},
        )


async def main():
    # Clear any stale shutdown sentinel from previous runs
    clear_shutdown()
    write_pid()

    try:
        # 1. Initialize services
        session_service = SQLiteSessionService(db_path="sessions.db")

        # 2. Create a session for the swarm
        session = await session_service.create_session(
            user_id="swarm_admin", app_name="CognitiveFoundry"
        )

        # Set observability context
        trace_id = os.getenv("TRACE_ID") or str(__import__("uuid").uuid4())
        set_trace_id(trace_id)
        set_session_id(session.id)
        logger.info("Cognitive Foundry Swarm Active", extra={"session_id": session.id})

        # 3. Initialize the Runner with the Orchestrator
        runner = Runner(
            agent=orchestrator_agent, app_name="CognitiveFoundry", session_service=session_service
        )
        runner.callbacks = [ObservabilityCallback()]

        logger.info("Cognitive Foundry Swarm Active (session=%s)", session.id)

        # Check for API Key (OpenRouter)
        if not os.getenv("OPENROUTER_API_KEY"):
            logger.error("OPENROUTER_API_KEY not found in environment.")
            return

        autonomous = os.getenv("AUTONOMOUS_MODE", "false").lower() == "true"

        if autonomous:
            logger.info("Running in autonomous loop mode. Use `swarm_cli stop` to exit.")
            await run_swarm_loop(session_service, session, runner)
        else:
            await run_single(session_service, session, runner)

    finally:
        clear_pid()
        clear_shutdown()
        logger.info("Swarm exited cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
