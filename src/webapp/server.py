"""GADK Webapp FastAPI server.

Provides a REST API for read-only monitoring of the Cognitive Foundry swarm.
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager

# Ensure src. is on the path for imports
_SRC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

import hmac

try:
    from fastapi import FastAPI, HTTPException, Request  # noqa: I001
except ImportError:
    FastAPI = None
    HTTPException = None
    Request  # noqa: I001 = None
try:
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    CORSMiddleware = None
try:
    from fastapi.responses import JSONResponse
except ImportError:
    JSONResponse = None

from src.webapp.routers import events_router, metrics_router, swarm_router

# ---------------------------------------------------------------------------
# Token authentication
# ---------------------------------------------------------------------------

_WEBAPP_TOKEN = os.getenv("WEBAPP_TOKEN", "")
_PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/api/metrics/summary",
        "/api/metrics/costs",
        "/api/metrics/tokens",
        "/api/swarm/health",
    }
)


def _require_token(request: Request) -> None:
    """Validate the X-Token header against WEBAPP_TOKEN env var.

    Raises HTTPException 401 on mismatch or missing token.
    """
    if not _WEBAPP_TOKEN:
        return  # Token auth disabled when env var is not set
    token = request.headers.get("X-Token", "")
    if not hmac.compare_digest(token, _WEBAPP_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup / shutdown."""
    # Startup: start the SSE event tailer as a background task
    from src.webapp.routers.events import sse_manager
    from src.webapp.services.event_tailer import EventTailer

    tailer = EventTailer()
    stop_event = asyncio.Event()

    async def feed_events():
        """Poll events.jsonl and broadcast new ones to all SSE clients."""
        while not stop_event.is_set():
            async for event in tailer.tail():
                await sse_manager.broadcast(event)
            await asyncio.sleep(0.5)

    feed_task = asyncio.create_task(feed_events())
    yield
    # Shutdown: stop the tailer
    stop_event.set()
    feed_task.cancel()
    try:
        await feed_task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="GADK Webapp",
        description="Read-only REST API for the Cognitive Foundry swarm",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — allow Vite dev server (localhost:5173)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Token auth middleware on all /api/ routes except public paths
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in _PUBLIC_PATHS:
            try:
                _require_token(request)
            except HTTPException:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized"},
                )
        return await call_next(request)

    # Register routers
    app.include_router(events_router)
    app.include_router(metrics_router)
    app.include_router(swarm_router)

    # Health endpoint (no auth)
    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Swarm status endpoint (protected by token)
    @app.get("/api/status")
    def get_status(request: Request):
        _require_token(request)
        from src.webapp.services.state_reader import StateReader

        reader = StateReader()
        return reader.get_status().model_dump()

    # Tasks endpoint (protected by token)
    @app.get("/api/tasks")
    def get_tasks(request: Request, status: str | None = None):
        _require_token(request)
        from src.webapp.services.state_reader import StateReader

        reader = StateReader()
        tasks = reader.get_tasks(status_filter=status)
        return [t.model_dump() for t in tasks]

    # Events endpoint (protected by token)
    @app.get("/api/events")
    def get_events(request: Request, task_id: str | None = None, limit: int = 100):
        _require_token(request)
        from src.webapp.services.state_reader import StateReader

        reader = StateReader()
        events = reader.get_events(task_id=task_id, limit=limit)
        return [e.model_dump() for e in events]

    return app


# ---------------------------------------------------------------------------
# Uvicorn runner
# ---------------------------------------------------------------------------


def run(
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """Start the webapp server with uvicorn."""
    try:
        import uvicorn
    except ImportError:
        raise SystemExit(
            f"Webapp requires uvicorn.\nInstall with: {sys.executable} -m pip install uvicorn"
        )
    app = create_app()
    print(f"  GADK Webapp → http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()
