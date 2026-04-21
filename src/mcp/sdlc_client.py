"""Thin client for the external SDLC MCP server.

The external server (outside this repo) exposes ``chimera_adr_create``,
``chimera_sprint_open``, ``sdlc_phase_commit``, and ``sdlc_quality_gate_pr``.
This module is a minimal **dormant** adapter: it only activates when
``Config.SDLC_MCP_ENABLED`` is True, it does not maintain a persistent
connection, and every call is a best-effort invocation with an explicit
timeout + structured logging.

Transport: delegates to ``src.tools.smithery_bridge.call_smithery_tool``
if present so we don't duplicate the MCP subprocess dance. If that
module is unavailable we fall back to a recorded no-op so local and
CI runs never crash because an external service is missing.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.config import Config
from src.observability.logger import get_logger

logger = get_logger("sdlc_client")

#: Logical names for the external MCP tools we care about. Kept here so
#: callers can refer to them without hard-coding strings and so tests can
#: assert against the expected surface.
TOOL_ADR_CREATE = "chimera_adr_create"
TOOL_SPRINT_OPEN = "chimera_sprint_open"
TOOL_PHASE_COMMIT = "sdlc_phase_commit"
TOOL_QUALITY_GATE_PR = "sdlc_quality_gate_pr"

#: Module-level set of in-flight tasks created by :func:`submit_gate_decision`.
#: Each entry is removed by a ``done_callback`` when the task completes or is
#: cancelled, so the set only ever holds truly live tasks.  On swarm shutdown
#: call :func:`cancel_pending_tasks` to drain the set gracefully.
_pending_tasks: set[asyncio.Task] = set()


def _is_enabled() -> bool:
    return bool(getattr(Config, "SDLC_MCP_ENABLED", False))


async def _invoke(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call through the smithery bridge, if available."""
    if not _is_enabled():
        return {"status": "skipped", "reason": "SDLC_MCP_ENABLED=false"}

    try:
        from src.tools.smithery_bridge import call_smithery_tool  # type: ignore
    except ImportError as exc:
        logger.debug("smithery_bridge unavailable: %s", exc)
        return {"status": "skipped", "reason": "smithery_bridge unavailable"}

    try:
        result = await asyncio.wait_for(
            call_smithery_tool(
                server_id="sdlc",
                tool_name=tool_name,
                tool_args=payload,
            ),
            timeout=30.0,
        )
    except TimeoutError:
        logger.warning("sdlc_mcp timeout on %s", tool_name)
        return {"status": "timeout", "tool": tool_name}
    except Exception as exc:
        logger.error("sdlc_mcp %s failed: %s", tool_name, exc, exc_info=True)
        return {"status": "error", "tool": tool_name, "error": str(exc)}

    return {"status": "ok", "tool": tool_name, "result": result}


async def create_adr(
    *,
    task_id: str,
    title: str,
    context: str,
    decision: str,
    consequences: list[str],
) -> dict[str, Any]:
    """Invoke ``chimera_adr_create`` on the external MCP server."""
    return await _invoke(
        TOOL_ADR_CREATE,
        {
            "task_id": task_id,
            "title": title,
            "context": context,
            "decision": decision,
            "consequences": consequences,
        },
    )


async def commit_phase(task_id: str, from_phase: str, to_phase: str, reason: str) -> dict[str, Any]:
    """Invoke ``sdlc_phase_commit`` for an audit-logged phase transition."""
    return await _invoke(
        TOOL_PHASE_COMMIT,
        {
            "task_id": task_id,
            "from_phase": from_phase,
            "to_phase": to_phase,
            "reason": reason,
        },
    )


async def submit_quality_gate(pr_number: int, gates: list[dict[str, Any]]) -> dict[str, Any]:
    """Invoke ``sdlc_quality_gate_pr`` with aggregated gate results."""
    return await _invoke(
        TOOL_QUALITY_GATE_PR,
        {"pr_number": pr_number, "gates": gates},
    )


def submit_gate_decision(task_id: str, verdict: dict[str, Any]) -> dict[str, Any]:
    """Sync-friendly entrypoint used by ``Governor.register_external_gate``.

    Governor runs inside ADK's synchronous tool surface for some call
    sites, so this wraps the async invocation in a safe fallback:
    - If an event loop is running, schedule the coroutine and return a
      pending marker (callers log and move on).
    - If no loop is running, run synchronously via ``asyncio.run``.
    """
    payload = {"task_id": task_id, "verdict": verdict}
    if not _is_enabled():
        return {"status": "skipped", "reason": "SDLC_MCP_ENABLED=false"}

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is None:
        return asyncio.run(_invoke(TOOL_QUALITY_GATE_PR, payload))

    # Inside a running loop: schedule and track so the task survives until
    # the loop shuts down and can be cancelled cleanly via cancel_pending_tasks.
    task = loop.create_task(_invoke(TOOL_QUALITY_GATE_PR, payload))
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)
    return {"status": "scheduled", "tool": TOOL_QUALITY_GATE_PR}


async def cancel_pending_tasks(timeout: float = 5.0) -> None:
    """Cancel all in-flight gate-decision tasks and wait for them to finish.

    Should be called during swarm shutdown (after the shutdown sentinel is
    detected) so no tasks are GC'd mid-flight with unhandled exceptions.
    Tasks that do not finish within *timeout* seconds are logged as warnings.
    """
    if not _pending_tasks:
        return
    tasks = list(_pending_tasks)
    for t in tasks:
        t.cancel()
    _done, pending = await asyncio.wait(tasks, timeout=timeout)
    for t in pending:
        logger.warning("sdlc_client: task %s did not finish within %.1fs drain timeout", t, timeout)


__all__ = [
    "TOOL_ADR_CREATE",
    "TOOL_PHASE_COMMIT",
    "TOOL_QUALITY_GATE_PR",
    "TOOL_SPRINT_OPEN",
    "cancel_pending_tasks",
    "commit_phase",
    "create_adr",
    "submit_gate_decision",
    "submit_quality_gate",
]
