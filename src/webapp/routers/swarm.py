"""Swarm runtime REST API router.

Provides:
- GET  /api/swarm/status   — Full swarm status snapshot
- GET  /api/swarm/health   — Health check
- POST /api/swarm/stop     — Request graceful swarm shutdown
- POST /api/swarm/inject-prompt — Enqueue a prompt via prompt_queue.jsonl
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

try:
    from fastapi import APIRouter, HTTPException
except ImportError:
    APIRouter = None
    HTTPException = None

from src.cli.swarm_ctl import SENTINEL_PATH, enqueue_prompt, get_swarm_pid, is_shutdown_requested
from src.observability.metrics import registry
from src.webapp.models.schemas import SwarmStatus
from src.webapp.services.state_reader import StateReader

router = APIRouter(prefix="/api/swarm", tags=["swarm"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_reader() -> StateReader:
    return StateReader()


# ---------------------------------------------------------------------------
# GET /api/swarm/status
# ---------------------------------------------------------------------------


@router.get("/status", response_model=SwarmStatus)
def get_swarm_status() -> SwarmStatus:
    """Full swarm status snapshot.

    Returns tasks count, phase distribution, status distribution,
    overall health, and file-modification timestamp.
    """
    reader = _state_reader()
    return reader.get_status()


# ---------------------------------------------------------------------------
# GET /api/swarm/health
# ---------------------------------------------------------------------------


@router.get("/health")
def get_swarm_health() -> dict[str, Any]:
    """Swarm health check.

    Returns {status: "healthy"|"unhealthy"|"degraded", details: {...}}.
    """
    reader = _state_reader()
    status = reader.get_status()

    pid = get_swarm_pid()
    pid_alive = False
    if pid is not None:
        try:
            os.kill(pid, 0)  # Signal 0 = check if process exists
            pid_alive = True
        except OSError:
            pid_alive = False

    shutdown_requested = is_shutdown_requested()

    health = status.health
    if shutdown_requested:
        health = "shutting_down"
    elif not pid_alive and pid is not None:
        health = "stale_pid"

    # Build details
    details: dict[str, Any] = {
        "pid": pid,
        "pid_alive": pid_alive,
        "shutdown_requested": shutdown_requested,
        "tasks_total": status.tasks_total,
        "tasks_by_phase": status.tasks_by_phase,
        "tasks_by_status": status.tasks_by_status,
        "metrics_summary": registry.get_summary(),
    }

    # Determine overall status
    if health in ("unhealthy", "stale_pid"):
        overall = "unhealthy"
    elif health in ("degraded", "shutting_down"):
        overall = "degraded"
    else:
        overall = "healthy"

    return {"status": overall, "details": details}


# ---------------------------------------------------------------------------
# POST /api/swarm/stop
# ---------------------------------------------------------------------------


@router.post("/stop")
def stop_swarm() -> dict[str, Any]:
    """Request graceful swarm shutdown.

    Writes a timestamp to the .swarm_shutdown sentinel file. The swarm
    runtime checks this file and initiates a clean shutdown when it finds it.
    """
    if os.path.exists(SENTINEL_PATH):
        # Already requested — idempotent
        with open(SENTINEL_PATH) as f:
            existing = f.read().strip()
        return {
            "requested": True,
            "message": "Shutdown already requested",
            "existing_request_at": existing or None,
        }

    # Write sentinel with ISO timestamp
    with open(SENTINEL_PATH, "w") as f:
        f.write(datetime.now(UTC).isoformat())

    return {
        "requested": True,
        "message": "Shutdown sentinel written",
        "sentinel_path": os.path.abspath(SENTINEL_PATH),
    }


# ---------------------------------------------------------------------------
# POST /api/swarm/inject-prompt
# ---------------------------------------------------------------------------


@router.post("/inject-prompt")
def inject_prompt(prompt: str, user_id: str = "webapp") -> dict[str, Any]:
    """Enqueue a prompt for the swarm to process.

    Appends a JSON record to prompt_queue.jsonl. The swarm's prompt consumer
    reads this file and processes each entry in order.
    """
    if not prompt or not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    enqueue_prompt(prompt=prompt.strip(), user_id=user_id)

    return {
        "enqueued": True,
        "user_id": user_id,
        "prompt_length": len(prompt.strip()),
    }
