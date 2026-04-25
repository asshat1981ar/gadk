"""Read-only state access wrapper.

Provides lightweight access to swarm state without importing the full
StateManager (which carries threading locks and write concerns).
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from src.webapp.models.schemas import Event, SwarmStatus, TaskSummary


class StateReader:
    """Read-only accessor for swarm state stored in state.json / events.jsonl."""

    def __init__(
        self,
        state_path: str = "state.json",
        events_path: str = "events.jsonl",
    ) -> None:
        self.state_path = state_path
        self.events_path = events_path

    # ------------------------------------------------------------------
    # State file helpers
    # ------------------------------------------------------------------

    def _read_state(self) -> dict[str, Any]:
        """Load and return the state dict, or an empty dict on error."""
        if not os.path.exists(self.state_path):
            return {}
        try:
            with open(self.state_path) as f:
                raw = f.read().strip()
            if not raw:
                return {}
            return json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return {}

    # ------------------------------------------------------------------
    # Swarm status
    # ------------------------------------------------------------------

    def get_status(self) -> SwarmStatus:
        """Return a SwarmStatus snapshot from state.json."""
        state = self._read_state()

        tasks: dict[str, Any] = state.get("tasks", {})
        if isinstance(state.get("data"), dict):
            tasks = state["data"].get("tasks", tasks)

        phase_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for task_data in tasks.values():
            if isinstance(task_data, dict):
                phase = task_data.get("phase", "unknown")
                status = task_data.get("status", "unknown")
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
                status_counts[status] = status_counts.get(status, 0) + 1

        updated_at: str | None = None
        if os.path.exists(self.state_path):
            try:
                mtime = os.path.getmtime(self.state_path)
                updated_at = datetime.fromtimestamp(mtime, tz=UTC).isoformat()
            except OSError:
                pass

        health = "healthy"
        if status_counts.get("blocked", 0) > 0:
            health = "degraded"
        if status_counts.get("failed", 0) > 0:
            health = "unhealthy"

        return SwarmStatus(
            tasks_total=len(tasks),
            tasks_by_phase=phase_counts,
            tasks_by_status=status_counts,
            health=health,
            updated_at=updated_at,
        )

    # ------------------------------------------------------------------
    # Task access
    # ------------------------------------------------------------------

    def get_tasks(
        self,
        status_filter: str | None = None,
    ) -> list[TaskSummary]:
        """Return all tasks as TaskSummary objects, optionally filtered by status.

        Args:
            status_filter: If provided, only return tasks whose status matches.

        Returns:
            List of TaskSummary objects (oldest first).
        """
        state = self._read_state()

        tasks: dict[str, Any] = state.get("tasks", {})
        if isinstance(state.get("data"), dict):
            tasks = state["data"].get("tasks", tasks)

        results: list[TaskSummary] = []
        for task_id, task_data in tasks.items():
            if not isinstance(task_data, dict):
                continue
            if status_filter is not None and task_data.get("status") != status_filter:
                continue
            results.append(
                TaskSummary(
                    id=task_id,
                    phase=task_data.get("phase", "unknown"),
                    status=task_data.get("status", "unknown"),
                    created=task_data.get("created"),
                    updated=task_data.get("updated"),
                    title=task_data.get("title"),
                )
            )

        # Sort by created timestamp (oldest first)
        results.sort(key=lambda t: t.created or "")
        return results

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def get_events(
        self,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Return recent events, optionally scoped to a specific task.

        Args:
            task_id: If provided, only return events for this task.
            limit: Maximum number of events to return (most recent first).

        Returns:
            List of Event objects.
        """
        if not os.path.exists(self.events_path):
            return []

        events: list[Event] = []
        try:
            with open(self.events_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if task_id is not None and entry.get("task_id") != task_id:
                        continue
                    events.append(
                        Event(
                            timestamp=entry.get("timestamp", ""),
                            type=entry.get("action", "unknown"),
                            data=entry,
                        )
                    )
        except OSError:
            pass

        # Most recent first, then apply limit
        events.reverse()
        return events[:limit]
