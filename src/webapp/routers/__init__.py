"""Webapp routers package."""
from src.webapp.routers.events import router as events_router
from src.webapp.routers.metrics import router as metrics_router
from src.webapp.routers.swarm import router as swarm_router

__all__ = ["events_router", "metrics_router", "swarm_router"]