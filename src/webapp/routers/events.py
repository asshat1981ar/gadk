"""Events REST API router with SSE streaming.

Exposes event log API and real-time SSE streaming of new events.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

try:
    from fastapi import APIRouter, Request
except ImportError:
    APIRouter = None
    Request = None
try:
    from fastapi.responses import StreamingResponse
except ImportError:
    StreamingResponse = None

from src.webapp.services.sse_manager import SSEManager

router = APIRouter(prefix="/api/events", tags=["events"])

# Shared SSE manager — imported by server.py lifespan to start the tailer
sse_manager = SSEManager()

# Path to events.jsonl (in gadk root)
EVENTS_FILE = os.environ.get("EVENTS_FILE", "events.jsonl")


def _load_events(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """Load events from events.jsonl with pagination."""
    events: list[dict[str, Any]] = []
    if not os.path.exists(EVENTS_FILE):
        return events
    try:
        with open(EVENTS_FILE) as f:
            # Read all lines
            lines = [line.strip() for line in f if line.strip()]
            # Apply pagination
            start = offset
            end = offset + limit
            for line in lines[start:end]:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return events


@router.get("")
def list_events(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """List events with pagination."""
    events = _load_events(limit=limit, offset=offset)
    total = 0
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE) as f:
                total = sum(1 for line in f if line.strip())
        except OSError:
            pass
    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stream")
async def stream_events(request: Request):
    """SSE endpoint for real-time events."""
    q = sse_manager.add_client()

    async def event_generator():
        try:
            # Send initial connection message
            yield 'data: {"type": "connected"}\n\n'
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                try:
                    # Wait for events with timeout to allow disconnect check
                    event = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
        finally:
            sse_manager.remove_client(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
