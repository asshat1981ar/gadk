"""Pydantic models for the GADK webapp API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SwarmStatus(BaseModel):
    """Swarm-level status snapshot."""

    tasks_total: int = 0
    tasks_by_phase: dict[str, int] = {}
    tasks_by_status: dict[str, int] = {}
    health: str = "unknown"
    updated_at: str | None = None


class TaskSummary(BaseModel):
    """Lightweight task representation for list views."""

    id: str
    phase: str
    status: str
    created: str | None = None
    updated: str | None = None
    title: str | None = None


class Event(BaseModel):
    """An event from the event log."""

    timestamp: str
    type: str
    data: dict[str, Any] = {}


class MetricsSummary(BaseModel):
    """Aggregated agent and tool metrics."""

    agents: dict[str, Any] = {}
    tools: dict[str, Any] = {}
    costs: dict[str, Any] = {}
