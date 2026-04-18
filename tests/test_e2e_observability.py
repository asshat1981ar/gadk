"""
End-to-end test for observability features 1-4.

This test exercises the full pipeline:
1. Structured logging with correlation IDs
2. StateManager event audit trail
3. Metrics registry and decorators
4. Dashboard rendering
"""

import asyncio
import json
import logging
import os
import tempfile

import pytest

from src.cli.dashboard import Dashboard
from src.observability.logger import (
    configure_logging,
    get_logger,
    get_session_id,
    get_task_id,
    get_trace_id,
    set_session_id,
    set_task_id,
    set_trace_id,
)
from src.observability.metrics import agent_timer, registry, tool_timer
from src.state import StateManager


@pytest.fixture
def temp_state_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "state.json")
        events_file = os.path.join(tmpdir, "events.jsonl")
        yield state_file, events_file


class TestEndToEndObservability:
    def test_full_pipeline(self, temp_state_files, capsys):
        state_file, events_file = temp_state_files

        # 1. Configure structured logging (JSON mode for parsing)
        configure_logging(level=logging.DEBUG, json_format=True)
        logger = get_logger("e2e_test")

        # 2. Set trace context
        set_trace_id("e2e-trace-123")
        set_session_id("e2e-session-456")
        set_task_id("e2e-task-789")

        # Verify context vars propagate
        assert get_trace_id() == "e2e-trace-123"
        assert get_session_id() == "e2e-session-456"
        assert get_task_id() == "e2e-task-789"

        # 3. Create state manager and perform operations
        sm = StateManager(storage_type="json", filename=state_file, event_filename=events_file)

        sm.set_task("task-1", {"status": "PLANNED", "source": "Ideator"}, agent="Ideator")
        sm.set_task("task-1", {"status": "COMPLETED", "source": "Ideator"}, agent="Builder")
        sm.set_task("task-2", {"status": "STALLED", "source": "Critic"}, agent="Critic")

        # 4. Verify JSON persistence
        assert os.path.exists(state_file)
        with open(state_file) as f:
            data = json.load(f)
        assert data["task-1"]["status"] == "COMPLETED"
        assert data["task-2"]["status"] == "STALLED"

        # 5. Verify audit trail
        history = sm.get_task_history("task-1")
        assert len(history) == 2
        assert history[0]["action"] == "SET"
        assert history[0]["agent"] == "Ideator"
        assert history[1]["diff"]["status"]["old"] == "PLANNED"
        assert history[1]["diff"]["status"]["new"] == "COMPLETED"

        all_events = sm.get_all_events()
        assert len(all_events) == 3

        # 6. Verify metrics registry with decorators
        registry.reset()

        @agent_timer("E2EAgent")
        async def mock_agent_work():
            await asyncio.sleep(0.01)
            return "agent-done"

        @tool_timer("E2ETool")
        async def mock_tool_work():
            return "tool-done"

        asyncio.run(mock_agent_work())
        asyncio.run(mock_tool_work())

        summary = registry.get_summary()
        assert summary["agents"]["E2EAgent"]["calls_total"] == 1
        assert summary["agents"]["E2EAgent"]["avg_duration_seconds"] > 0
        assert summary["tools"]["E2ETool"]["calls_total"] == 1

        # Record token usage
        registry.record_tokens("E2EAgent", 150)
        summary = registry.get_summary()
        assert summary["token_usage"]["E2EAgent"] == 150

        # 7. Verify dashboard renders without error
        dashboard = Dashboard(sm, refresh_rate=0.1)
        layout = dashboard._render()
        assert layout is not None

        # Verify dashboard metrics reflect our registry state
        metrics_table = dashboard._make_metrics_table()
        assert metrics_table.title == "Metrics"

        tasks_table = dashboard._make_tasks_table()
        assert tasks_table.title == "Active Tasks"

        # 8. Verify structured log output
        logger.info("E2E test complete", extra={"agent": "E2EAgent"})
        captured = capsys.readouterr()
        log_lines = [line for line in captured.out.split("\n") if line.strip()]
        last_log = json.loads(log_lines[-1])
        assert last_log["message"] == "E2E test complete"
        assert last_log["trace_id"] == "e2e-trace-123"
        assert last_log["session_id"] == "e2e-session-456"
        assert last_log["task_id"] == "e2e-task-789"
        assert last_log["agent"] == "E2EAgent"

    def test_dashboard_from_project_root(self, temp_state_files):
        """Verify dashboard can be imported and instantiated when run from project root."""
        state_file, events_file = temp_state_files
        sm = StateManager(storage_type="json", filename=state_file, event_filename=events_file)
        sm.set_task("dash-task", {"status": "PENDING"})

        dashboard = Dashboard(sm)
        assert dashboard.running is True
        dashboard.handle_input("q")
        assert dashboard.running is False
