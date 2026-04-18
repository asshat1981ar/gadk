import asyncio
import json
import os

from google.adk.runners import Runner
from google.genai import types

from src.agents.orchestrator import orchestrator_agent
from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.config import Config
from src.mcp.sdlc_client import cancel_pending_tasks as _cancel_sdlc_tasks
from src.planner import run_planner
from src.services.retrieval_context import (
    PLANNING_RETRIEVAL_CAPABILITY,
    RetrievalQuery,
    retrieve_context,
    retrieve_planning_context,
)
from src.services.runtime_strategy import should_use_planner_for_autonomous_run
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


async def _planning_retrieval_handler(request: CapabilityRequest) -> CapabilityResult:
    query = RetrievalQuery.model_validate(request.arguments)
    payload = await asyncio.to_thread(retrieve_context, query)
    return CapabilityResult.ok(payload=payload, source_backend="retrieval")


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
from src.observability.litellm_callbacks import setup_callbacks
from src.observability.logger import configure_logging, get_logger, set_session_id, set_trace_id
from src.services import self_prompt as _self_prompt
from src.state import StateManager

logger = get_logger("main")
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    json_format=os.getenv("JSON_LOGS", "true").lower() == "true",
)


async def _self_prompt_tick(sm: StateManager, *, interval_sec: float | None = None) -> None:
    """Opt-in background coroutine that runs the self-prompt loop periodically.

    Exits cleanly when the shutdown sentinel or the self-prompt off-switch
    appears so it never blocks teardown. Default cadence is a minute — tight
    enough to pick up new gap signals, loose enough that rate-limited writes
    stay bounded.
    """
    if not Config.SELF_PROMPT_ENABLED:
        return
    effective_interval = (
        interval_sec if interval_sec is not None else Config.SELF_PROMPT_TICK_INTERVAL_SEC
    )
    logger.info("self_prompt.tick: enabled, interval=%.1fs", effective_interval)
    while not is_shutdown_requested() and not _self_prompt.off_switch_active():
        try:
            # run_once is synchronous and does blocking file I/O (state.json,
            # coverage.xml, prompt_queue.jsonl). Offload to a worker thread
            # so the swarm's event loop stays responsive.
            await asyncio.to_thread(_self_prompt.run_once, sm=sm)
        except Exception:
            logger.exception("self_prompt.tick: run_once crashed; continuing")
        await asyncio.sleep(effective_interval)
    logger.info("self_prompt.tick: stopped (shutdown or off-switch)")


AUTONOMOUS_SYSTEM_PROMPT = (
    "You are the Cognitive Foundry autonomous runtime. "
    "Use registered tools exactly as named. "
    "For remote GitHub repository exploration, use read_repo_file and list_repo_contents."
)


def _build_autonomous_prompt(repo_name: str) -> str:
    """Build the autonomous self-prompt for remote repository exploration."""
    return (
        f"First, use 'list_repo_contents' to explore the '{repo_name}' repository. "
        "Read key files in that repository with 'read_repo_file' to understand its current state. "
        "Then, identify high-priority improvements or missing features, "
        "create structured tasks for them, and start the proactive ideation process. "
        "Remember: You are the Cognitive Foundry swarm, and this repository is your development target."
    )


async def _run_autonomous_prompt_with_tools(user_prompt: str) -> str:
    """Run the autonomous self-prompt through the planner-backed tool loop."""
    return await run_planner(
        user_prompt=user_prompt,
        system_prompt=AUTONOMOUS_SYSTEM_PROMPT,
        max_iterations=8,
    )


def _should_fallback_to_planner(exc: BaseException) -> bool:
    """Return True when the ADK/native tool-call path failed on malformed JSON."""
    pending = [exc]
    seen: set[int] = set()

    while pending:
        current = pending.pop()
        current_id = id(current)
        if current_id in seen:
            continue
        seen.add(current_id)

        if isinstance(current, json.JSONDecodeError):
            return True

        message = str(current).lower()
        if (
            "tool" in message
            and "json" in message
            and any(token in message for token in ("decode", "malformed", "invalid", "parse"))
        ):
            return True

        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)

    return False


async def process_prompt(runner, session, user_query: str) -> None:
    """Process a single user prompt through the swarm."""
    content = types.Content(role="user", parts=[types.Part(text=user_query)])
    logger.info(f"Processing prompt: {user_query}", extra={"session_id": session.id})
    try:
        events = runner.run_async(session_id=session.id, user_id="swarm_admin", new_message=content)
        async for event in events:
            if hasattr(event, "content") and event.content and event.content.parts:
                text = event.content.parts[0].text
                if text:
                    print(f"Swarm: {text}")
                    logger.info(f"Swarm response: {text}", extra={"session_id": session.id})
    except Exception as e:
        if _should_fallback_to_planner(e):
            logger.warning(
                "ADK tool-call JSON failure detected; retrying prompt via planner",
                extra={"session_id": session.id},
            )
            try:
                fallback = await _run_autonomous_prompt_with_tools(user_query)
            except Exception as fallback_error:
                logger.exception(
                    "Planner fallback failed after ADK tool-call JSON failure",
                    extra={"session_id": session.id},
                )
                print(f"Error during planner fallback: {fallback_error}")
                return
            if fallback:
                print(f"Swarm: {fallback}")
                logger.info(f"Swarm response: {fallback}", extra={"session_id": session.id})
            else:
                logger.error(
                    "Planner fallback returned no response after ADK tool-call JSON failure",
                    extra={"session_id": session.id},
                )
                print("Error during planner fallback: no response produced")
            return
        logger.exception("Error during swarm execution")
        if "AttributeError" not in str(e):
            logger.error("Error during swarm execution: %s", e)


async def run_swarm_loop(session_service, session, runner) -> None:
    """Run the swarm in autonomous loop mode, checking for prompts and shutdown.

    Every loop iteration — including the initial prompt — is wrapped in a
    broad try/except so a transient handler crash (network hiccup, mock
    seam, LiteLLM blip) doesn't silently terminate the swarm. The only
    clean-exit paths are the shutdown sentinel and KeyboardInterrupt.
    """
    initial_query = _build_autonomous_prompt("project-chimera")
    try:
        if should_use_planner_for_autonomous_run(Config.OPENROUTER_MODEL):
            response = await _run_autonomous_prompt_with_tools(initial_query)
            if response:
                print(f"Swarm: {response}")
                logger.info(
                    f"Swarm response: {response}",
                    extra={"session_id": session.id},
                )
        else:
            await process_prompt(runner, session, initial_query)
    except Exception:
        logger.exception("initial prompt crashed; continuing into main loop")

    while True:
        try:
            if is_shutdown_requested():
                logger.info("Shutdown sentinel detected. Exiting swarm loop.")
                break
        except Exception:
            logger.exception("shutdown-check crashed; treating as not-requested")
            # Conservative: fall through and keep looping so we don't
            # exit on a transient os.path.exists failure.

        # Check for injected prompts. Any crash here (queue file I/O,
        # prompt handler) gets logged and the loop keeps going —
        # silently exiting on a transient error was the original bug.
        try:
            prompts = dequeue_prompts()
            for entry in prompts:
                prompt_text = entry.get("prompt", "")
                user_id = entry.get("user_id", "cli_user")
                logger.info(
                    f"Injected prompt from {user_id}: {prompt_text}",
                    extra={"session_id": session.id},
                )
                await process_prompt(runner, session, prompt_text)
        except Exception:
            logger.exception("swarm loop iteration crashed; continuing")

        await asyncio.sleep(Config.SWARM_LOOP_POLL_SEC)


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

    # Wire up LiteLLM observability callbacks
    setup_callbacks()

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
            sm = StateManager()
            self_prompt_task = asyncio.create_task(_self_prompt_tick(sm))
            try:
                await run_swarm_loop(session_service, session, runner)
            finally:
                self_prompt_task.cancel()
                try:
                    await self_prompt_task
                except (asyncio.CancelledError, Exception):
                    pass
        else:
            await run_single(session_service, session, runner)

    finally:
        await _cancel_sdlc_tasks()
        clear_pid()
        clear_shutdown()
        logger.info("Swarm exited cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
