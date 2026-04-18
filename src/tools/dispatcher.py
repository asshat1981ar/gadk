import asyncio
from collections.abc import Callable
from typing import Any

from src.capabilities.contracts import CapabilityRequest, CapabilityResult
from src.capabilities.registry import CapabilityRegistry
from src.capabilities.service import CapabilityService
from src.cli.swarm_ctl import get_swarm_pid, is_shutdown_requested, peek_prompts
from src.observability.logger import get_logger
from src.state import StateManager
from src.tools.filesystem import list_directory, read_file

logger = get_logger("dispatcher")

# Tool Registry to avoid circular imports and allow dynamic lookups
_TOOL_REGISTRY: dict[str, Callable[..., Any]] = {}

# Global concurrency limit for tools to prevent resource exhaustion
MAX_CONCURRENCY = 10
_semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

_CAPABILITY_REGISTRY = CapabilityRegistry()
_CAPABILITY_SERVICE = CapabilityService(_CAPABILITY_REGISTRY)


def register_tool(name: str, func: Callable[..., Any]) -> None:
    """Register a function as an available tool for the dispatcher."""
    _TOOL_REGISTRY[name] = func


def _build_state_manager(arguments: dict[str, Any]) -> StateManager:
    """Build a state manager using optional file overrides for focused tests."""
    state_kwargs: dict[str, Any] = {}
    state_file = arguments.get("state_file")
    events_file = arguments.get("events_file")

    if state_file or events_file:
        state_kwargs["storage_type"] = "json"
    if state_file:
        state_kwargs["filename"] = state_file
    if events_file:
        state_kwargs["event_filename"] = events_file

    return StateManager(**state_kwargs)


def _swarm_status_handler(request: CapabilityRequest) -> dict[str, Any]:
    """Return a runtime status snapshot via the capability layer."""
    state_manager = _build_state_manager(request.arguments)
    tasks = state_manager.get_all_tasks()
    stalled = sum(1 for task in tasks.values() if task.get("status") == "STALLED")
    planned = sum(1 for task in tasks.values() if task.get("status") == "PLANNED")
    completed = sum(1 for task in tasks.values() if task.get("status") == "COMPLETED")

    return {
        "pid": get_swarm_pid(),
        "shutdown_requested": is_shutdown_requested(),
        "queue_depth": len(peek_prompts()),
        "total_tasks": len(tasks),
        "planned": planned,
        "completed": completed,
        "stalled": stalled,
        "health": "DEGRADED" if stalled else "HEALTHY",
    }


def _repo_read_file_handler(request: CapabilityRequest) -> dict[str, str]:
    return {"content": read_file(str(request.arguments["path"]))}


def _repo_list_directory_handler(request: CapabilityRequest) -> dict[str, Any]:
    return {"entries": list_directory(str(request.arguments.get("path", ".")))}


def _smithery_tool_handler(request: CapabilityRequest) -> dict[str, Any]:
    return {
        "server_id": request.arguments["server_id"],
        "tool_name": request.arguments["tool_name"],
        "tool_args": request.arguments.get("tool_args", {}),
    }


def _register_capability(
    name: str,
    description: str,
    backend: str,
    handler: Callable[[CapabilityRequest], Any],
) -> None:
    try:
        _CAPABILITY_REGISTRY.get(name)
    except KeyError:
        _CAPABILITY_REGISTRY.register(
            name=name,
            description=description,
            backend=backend,
            handler=handler,
        )


def register_runtime_capabilities() -> None:
    """Register the narrow capability-backed runtime surface."""
    _register_capability(
        name="swarm.status",
        description="Read runtime swarm status",
        backend="local",
        handler=_swarm_status_handler,
    )
    _register_capability(
        name="repo.read_file",
        description="Read a repository file with filesystem guardrails",
        backend="local",
        handler=_repo_read_file_handler,
    )
    _register_capability(
        name="repo.list_directory",
        description="List a repository directory with filesystem guardrails",
        backend="local",
        handler=_repo_list_directory_handler,
    )
    _register_capability(
        name="smithery.call_tool",
        description="Execute a Smithery tool through the capability layer",
        backend="smithery",
        handler=_smithery_tool_handler,
    )


def _capability_result_to_dict(result: CapabilityResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "payload": result.payload,
        "error": result.error,
        "source_backend": result.source_backend,
        "retryable": result.retryable,
    }


async def execute_capability(name: str, **arguments: object) -> dict[str, Any]:
    """Execute a shared runtime capability and return the standard envelope."""
    register_runtime_capabilities()
    result = await _CAPABILITY_SERVICE.execute(name, **arguments)
    return _capability_result_to_dict(result)


async def batch_execute(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Execute multiple tool calls concurrently with resource protection.

    Args:
        requests: List of dicts, each containing 'tool_name' and 'args'.
    """

    async def run_task(req: dict[str, Any]) -> dict[str, Any]:
        name = req.get("tool_name")
        args = req.get("args", {})

        if name not in _TOOL_REGISTRY:
            logger.error(f"Tool not found: {name}")
            return {"status": "error", "message": f"Tool '{name}' not found."}

        async with _semaphore:
            logger.debug(f"Executing batched tool: {name}", extra={"tool": name})
            try:
                func = _TOOL_REGISTRY[name]
                if asyncio.iscoroutinefunction(func):
                    result = await func(**args)
                else:
                    result = func(**args)
                logger.debug(f"Batched tool success: {name}", extra={"tool": name})
                return {"status": "success", "output": result}
            except Exception as exc:
                logger.exception(f"Batched tool error: {name}", extra={"tool": name})
                return {"status": "error", "message": str(exc)}

    logger.info(f"Dispatching batch of {len(requests)} tool calls.")
    results = await asyncio.gather(*(run_task(request) for request in requests))

    success_count = sum(1 for result in results if result["status"] == "success")
    logger.info(f"Batch completed: {success_count}/{len(requests)} successful.")

    return list(results)


register_runtime_capabilities()
register_tool("execute_capability", execute_capability)
