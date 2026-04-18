from __future__ import annotations

import asyncio
from typing import Any

from src.tools.dispatcher import execute_capability


def get_swarm_status_view(
    state_file: str | None = None,
    events_file: str | None = None,
) -> dict[str, Any]:
    """Return a CLI-facing swarm status view backed by the shared capability."""
    arguments: dict[str, str] = {}
    if state_file:
        arguments["state_file"] = state_file
    if events_file:
        arguments["events_file"] = events_file

    result = asyncio.run(execute_capability("swarm.status", **arguments))
    payload = result.get("payload") or {}
    pid = payload.get("pid")

    return {
        "status": result.get("status", "error"),
        "error": result.get("error"),
        "source_backend": result.get("source_backend", "local"),
        "retryable": bool(result.get("retryable", False)),
        "pid": pid if pid is not None else "Not running",
        "shutdown_requested": bool(payload.get("shutdown_requested", False)),
        "queue_depth": int(payload.get("queue_depth", 0)),
        "total_tasks": int(payload.get("total_tasks", 0)),
        "planned": int(payload.get("planned", 0)),
        "completed": int(payload.get("completed", 0)),
        "stalled": int(payload.get("stalled", 0)),
        "health": payload.get("health", "UNKNOWN"),
    }
