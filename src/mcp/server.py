from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from src.capabilities.registry import CapabilityRegistry
from src.capabilities.service import CapabilityService
from src.cli.swarm_ctl import get_swarm_pid, is_shutdown_requested, peek_prompts
from src.state import StateManager
from src.tools.filesystem import list_directory, read_file


def _build_swarm_status_payload() -> dict[str, Any]:
    """Return a low-risk snapshot of the local swarm state."""
    tasks = StateManager().get_all_tasks()
    total_tasks = len(tasks)
    stalled_tasks = sum(1 for task in tasks.values() if task.get("status") == "STALLED")
    planned_tasks = sum(1 for task in tasks.values() if task.get("status") == "PLANNED")
    completed_tasks = sum(1 for task in tasks.values() if task.get("status") == "COMPLETED")

    return {
        "pid": get_swarm_pid(),
        "shutdown_requested": is_shutdown_requested(),
        "queue_depth": len(peek_prompts()),
        "total_tasks": total_tasks,
        "planned_tasks": planned_tasks,
        "completed_tasks": completed_tasks,
        "stalled_tasks": stalled_tasks,
        "health": "DEGRADED" if stalled_tasks > 0 else "HEALTHY",
    }


def _build_result_envelope(result: Any) -> dict[str, Any]:
    """Serialize the shared capability result shape for MCP clients."""
    return {
        "status": result.status,
        "payload": result.payload,
        "error": result.error,
        "source_backend": result.source_backend,
        "retryable": result.retryable,
    }


def build_registry() -> CapabilityRegistry:
    """Build the narrow Phase 1 capability registry for the local MCP server."""
    registry = CapabilityRegistry()
    registry.register(
        name="swarm.status",
        description="Read a low-risk snapshot of local swarm status.",
        backend="local",
        handler=lambda request: _build_swarm_status_payload(),
    )
    registry.register(
        name="repo.read_file",
        description="Read a repository file using existing filesystem guardrails.",
        backend="local",
        handler=lambda request: {
            "path": request.arguments["path"],
            "content": read_file(request.arguments["path"]),
        },
    )
    registry.register(
        name="repo.list_directory",
        description="List repository entries using existing filesystem guardrails.",
        backend="local",
        handler=lambda request: {
            "path": request.arguments.get("path", "."),
            "entries": list_directory(request.arguments.get("path", ".")),
        },
    )
    return registry


def build_mcp_server() -> FastMCP:
    """Build the repo-local stdio MCP server as a thin capability adapter."""
    service = CapabilityService(build_registry())
    server = FastMCP("workflow-tooling")
    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
    )

    @server.tool(
        name="swarm_status",
        description="Read local swarm status through the shared capability layer.",
        annotations=read_only,
    )
    async def swarm_status() -> dict[str, Any]:
        return _build_result_envelope(await service.execute("swarm.status"))

    @server.tool(
        name="repo_read_file",
        description="Read a repository file through the shared capability layer.",
        annotations=read_only,
    )
    async def repo_read_file(path: str) -> dict[str, Any]:
        return _build_result_envelope(await service.execute("repo.read_file", path=path))

    @server.tool(
        name="repo_list_directory",
        description="List repository entries through the shared capability layer.",
        annotations=read_only,
    )
    async def repo_list_directory(path: str = ".") -> dict[str, Any]:
        return _build_result_envelope(
            await service.execute("repo.list_directory", path=path)
        )

    return server


if __name__ == "__main__":
    build_mcp_server().run(transport="stdio")
